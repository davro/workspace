# VideoEditorPlugin — Developer Handover

**Last updated:** 2025  
**Plugin path:** `ide/plugins/VideoEditorPlugin/`  
**Status:** Whisper transcription + subtitle burn-in implemented and smoke-tested. Ready for broader testing and iteration.

---

## Plugin Overview

A non-linear video editor embedded in the Workspace IDE as a plugin. Built entirely with PyQt6 and FFmpeg. No external video editing libraries.

### Entry point

```
VideoEditorPlugin.py   ← plugin loader, calls get_widget()
VideoEditorPlugin/
    __init__.py
    VideoEditorWidget.py   ← top-level QWidget, owns all panels
    ...
```

---

## Architecture

```
VideoEditorWidget
├── Toolbar (New / Open / Save / Import / URL Import / 🎙 Transcribe / ▶ Export)
├── QSplitter (horizontal)
│   ├── MediaBin          — left panel, imported clips + thumbnails
│   ├── PreviewWidget     — video playback (SOURCE + TIMELINE modes)
│   │   └── SubtitleOverlay  — transparent overlay, renders live subtitles
│   └── TranscriptPanel   — right panel (hidden until first transcription)
│       buttons: 📋 Copy | 💾 Export… | 🎨 Style | ✕ Clear | [title ✕]
└── TimelineWidget        — bottom, track editor
```

### Key state on VideoEditorWidget

| Attribute | Type | Purpose |
|---|---|---|
| `_whisper_workers` | `list[WhisperWorker]` | Keeps workers alive against GC |
| `_subtitle_segments` | `list[TranscriptSegment]` | Last completed transcription; passed to ExportDialog |
| `_subtitle_style` | `SubtitleStyle` | Current style; shared between overlay + burn |

---

## Files Added This Session

### `WhisperWorker.py`
QThread wrapper around `faster-whisper`.

**Class:** `WhisperWorker(QThread)`

| Signal | Args | Fired when |
|---|---|---|
| `segment_ready` | `(float, float, str)` | Each segment recognised |
| `progress` | `(float)` | 0.0–1.0 as segments stream in |
| `finished` | `(list[TranscriptSegment])` | All segments done |
| `error` | `(str)` | Any failure |

**Key params:**
- `model_size` — `tiny / base / small / medium / large-v3`
- `language` — ISO code or `None` for auto-detect
- `vad_filter` — set as attribute after construction; defaults `False` (VAD kills all segments on music/short clips)
- `source_duration` — float, used for progress reporting only

**Audio extraction:** For video files, runs `ffmpeg -ar 16000 -ac 1 -f wav` to a temp file before passing to Whisper. Temp file deleted in `finally`.

**`TranscriptSegment` dataclass:**
```python
@dataclass
class TranscriptSegment:
    start: float
    end:   float
    text:  str
    words: list           # word-level timestamps (currently unused)

    def to_srt_block(self, index: int) -> str
    def to_vtt_block(self) -> str
```

**Important:** Always `_whisper_workers.append(worker)` in the caller — Python GC kills QThreads without a live reference.

---

### `WhisperDialog.py`
Modal dialog for transcription settings.

**Class:** `WhisperDialog(QDialog)`

**Constructor params:**
- `bin_path: str | None` — currently selected clip path
- `bin_name: str | None` — display name

**Output attributes** (read after `exec() == Accepted`):
- `selected_model: str` — e.g. `"base"`
- `selected_language: str | None` — ISO code or `None`
- `selected_source: str` — file path to transcribe
- `selected_vad: bool` — whether VAD filter is enabled

**VAD checkbox:** Unchecked by default with warning label. Only enable for long speech recordings with extended silences.

---

### `TranscriptPanel.py`
Scrollable dockable panel, hidden until first transcription.

**Class:** `TranscriptPanel(QWidget)`

| Signal | Args | Fired when |
|---|---|---|
| `seek_requested` | `(float)` | User clicks a timestamp |
| `close_requested` | `()` | User clicks ✕ in title bar |
| `style_requested` | `()` | User clicks 🎨 Style |

**Public API:**
```python
add_segment(start, end, text)     # connect to WhisperWorker.segment_ready
set_segments(list)                # replace all at once
set_progress(float)               # 0.0–1.0, hides bar at 1.0
set_status(str)
clear(keep_status=False)
```

**Export formats:** `.srt`, `.vtt`, `.txt` via `QFileDialog`.

**Splitter reveal pattern** (Qt6 quirk): The panel starts hidden with 0px in the splitter. To reveal it, call `.show()` then defer `setSizes()` via `QTimer.singleShot(0, ...)` — Qt6 ignores `setSizes` on hidden widgets within the same event loop tick.

```python
self.transcript_panel.show()
def _resize():
    sizes = self._upper_splitter.sizes()
    total = sum(sizes)
    panel_w = min(300, max(240, total // 4))
    self._upper_splitter.setSizes([sizes[0], total - sizes[0] - panel_w, panel_w])
QTimer.singleShot(0, _resize)
```

---

### `SubtitleStyle.py`
Shared dataclass — single source of truth for subtitle appearance used by both live overlay and FFmpeg export.

```python
@dataclass
class SubtitleStyle:
    font_size:    int   = 22
    font_weight:  str   = "Bold"
    font_family:  str   = "Arial"
    text_color:   tuple = (255, 255, 255, 255)   # RGBA 0-255
    outline_color:tuple = (0, 0, 0, 255)
    bg_color:     tuple = (0, 0, 0, 140)
    outline_width:int   = 2
    bg_enabled:   bool  = False
    position:     str   = "Bottom Centre"
    margin:       int   = 40
```

**Position presets** (9 options): `Bottom Centre / Bottom Left / Bottom Right / Top Centre / Top Left / Top Right / Centre`

**FFmpeg helpers:** `ffmpeg_fontcolor()`, `ffmpeg_bordercolor()`, `ffmpeg_boxcolor()` return `0xRRGGBBAA` strings. `ffmpeg_x()`, `ffmpeg_y()` return drawtext expression strings for the position preset.

---

### `SubtitleStyleDialog.py`
Visual style editor with a live mini-preview swatch (`_PreviewLabel` subclass).

**Class:** `SubtitleStyleDialog(QDialog)`

**Constructor:** `SubtitleStyleDialog(initial: SubtitleStyle | None, parent)`

**Output:** `dialog.style` → `SubtitleStyle` (read after `exec() == Accepted`)

Controls: font family (QFontComboBox), size (18–72), bold/normal, text/outline/background colour pickers (QColorDialog with alpha support), outline width (0–8px), background box toggle, position preset dropdown.

Works on a copy of the initial style — Cancel discards all changes.

---

### `SubtitleOverlay.py`
Transparent `QWidget` parented to `PreviewWidget.video_widget`. Renders the active subtitle using `QPainterPath` for proper outline strokes with word-wrap at 85% of widget width.

**Class:** `SubtitleOverlay(QWidget)`

**Public API:**
```python
set_style(style: SubtitleStyle)
set_segments(segments: list[TranscriptSegment])
clear_segments()
set_subtitles_visible(visible: bool)
update_position(seconds: float)   # call on every position_changed tick
```

**Instantiation** (in `PreviewWidget._build_ui`):
```python
self._subtitle_overlay = SubtitleOverlay(self.video_widget)
self._subtitle_overlay.resize(self.video_widget.size())
self._subtitle_overlay.show()
```

Resized in `PreviewWidget.resizeEvent` to always cover `video_widget`.

---

## Files Modified This Session

### `FFmpegWorker.py`
**Added:** `SubtitleBurnWorker(QThread)`

| Signal | Args |
|---|---|
| `progress` | `(float)` 0.0–1.0 |
| `finished` | `(str)` output path |
| `error` | `(str)` |
| `log` | `(str)` ffmpeg output line |

**Constructor:**
```python
SubtitleBurnWorker(
    input_path:     str,
    output_path:    str,
    segments:       list[TranscriptSegment],
    style:          SubtitleStyle,
    total_duration: float = 0.0,
    parent=None,
)
```

**Burn approach — ASS filter (not drawtext):**

`drawtext` with per-segment `enable='between(t,...)'` expressions was abandoned — FFmpeg's filtergraph parser mangles the escaping when passed via subprocess with 10+ chained filters.

Instead, `_write_ass()` generates a temp `.ass` (Advanced SubStation Alpha) file:
- `[Script Info]` includes `PlayResX/PlayResY` probed from the input via `ffprobe` — without this libass assumes 384×288 and scales font size up ~5× 
- `[V4+ Styles]` maps all `SubtitleStyle` fields to ASS format (colours in `&HAABBGGRR`, alignment in numpad layout)
- `[Events]` has one `Dialogue:` line per segment

FFmpeg command: `ffmpeg -vf ass=/tmp/tmpXXX.ass -c:v libx264 -crf 18 -preset fast -c:a copy`

Temp `.ass` file deleted in `finally` block regardless of success/failure.

**`_probe_resolution()`** — runs `ffprobe -show_streams -select_streams v:0` on the input, returns `(width, height)`, defaults to `(1920, 1080)` on any error.

---

### `ExportDialog.py`
**Added:** "Subtitles" `QGroupBox` with `chk_burn_subs` checkbox.
- Auto-enabled (checked + enabled) when `subtitle_segments` is passed in
- Greyed out with explanatory label if no transcript exists

**Constructor new params:**
```python
ExportDialog(
    project,
    parent             = None,
    subtitle_segments  = None,   # list[TranscriptSegment] or None
    subtitle_style     = None,   # SubtitleStyle or None
)
```

**Two-pass export flow:**
1. `ExportWorker` renders the timeline → output path (`_on_export_done`)
2. If burn checkbox is ticked: `SubtitleBurnWorker` burns subtitles from output path → temp file → `shutil.move` replaces original (`_on_burn_done`)
3. `_on_finished` called either way

Both workers are cancelled in `_on_cancel` and `closeEvent`.

---

### `PreviewWidget.py`
**Added imports:** `SubtitleOverlay`, `SubtitleStyle`

**Added state:** `self._subtitle_overlay: SubtitleOverlay | None = None`

**Added after `video_widget` creation:**
```python
self._subtitle_overlay = SubtitleOverlay(self.video_widget)
self._subtitle_overlay.resize(self.video_widget.size())
self._subtitle_overlay.show()
```

**`update_position` calls added** in three places:
- `_on_player_position_changed` (SOURCE mode)
- `_tl_tick` (TIMELINE mode playback tick)
- `_tl_seek` (TIMELINE mode seek)

**Added `resizeEvent`** to keep overlay sized to `video_widget`.

**New public methods:**
```python
set_subtitle_segments(segments: list)
set_subtitle_style(style)
clear_subtitles()
set_subtitles_visible(visible: bool)
```

---

### `VideoEditorWidget.py`
**New imports:** `WhisperWorker`, `WhisperDialog`, `TranscriptPanel`, `SubtitleStyle`, `SubtitleStyleDialog`

**New toolbar button:** `🎙 Transcribe` (between URL Import and Export)

**New panel:** `TranscriptPanel` as third pane in `self._upper_splitter` (stored as `self._upper_splitter` not a local — needed for deferred `setSizes`)

**New signal connections:**
```python
transcript_panel.seek_requested  → _on_seek
transcript_panel.close_requested → _hide_transcript_panel
transcript_panel.style_requested → _open_subtitle_style
```

**New methods:**

| Method | Purpose |
|---|---|
| `_transcribe()` | faster-whisper import check → `WhisperDialog` → `WhisperWorker` → reveal panel |
| `_on_whisper_finished(segments)` | Store `_subtitle_segments`, push to overlay |
| `_on_whisper_error(msg)` | Show status + `QMessageBox` |
| `_open_subtitle_style()` | `SubtitleStyleDialog` → update `_subtitle_style` → push to overlay |
| `_hide_transcript_panel()` | Collapse panel in splitter, `setSizes` to give space back to preview |

**`_export()` updated:** passes `subtitle_segments` and `subtitle_style` to `ExportDialog`.

**`cleanup()` updated:** cancels and joins all `_whisper_workers`.

---

## Known Issues / Testing Notes

### Tested and working
- Transcription of short music/singing clips (VAD off by default)
- Transcript panel reveal/collapse with correct splitter sizing
- Live subtitle overlay during SOURCE and TIMELINE playback
- Export → subtitle burn two-pass pipeline
- `.srt` / `.vtt` / `.txt` export from transcript panel
- Clickable timestamps seeking preview
- Style dialog live preview swatch

### Not yet tested / known gaps
- **Multi-clip timelines** — `_subtitle_segments` holds transcription for one clip at a time; no timestamp offset is applied for clips that don't start at t=0 on the timeline. For a multi-clip export the burn will show subtitles at the source clip's timestamps, not the timeline position.
- **Long files** — VAD off means Whisper processes the full audio; large files may be slow on CPU. Exposing a device selector (CPU/CUDA) in `WhisperDialog` would help.
- **Overlay resize on splitter drag** — `resizeEvent` on `PreviewWidget` resizes the overlay, but Qt doesn't always fire `resizeEvent` on splitter handle drags. May need an event filter on `video_widget` instead.
- **Font availability** — `SubtitleStyleDialog` uses `QFontComboBox` which lists system fonts. ASS burn uses `fontconfig` to find the closest match; exotic fonts may not render the same in the burned output vs the overlay preview.
- **Cancel during burn** — `SubtitleBurnWorker.cancel()` sets a flag that is checked between subprocess output lines. FFmpeg is terminated via `process.terminate()`. The temp output file is not cleaned up on cancel — could leave orphaned files in `/tmp`.
- **Emoji/Unicode in filenames** — FFmpeg on Linux handles these fine (confirmed in logs), but the ASS `text` field should be monitored for any characters that break libass rendering.

### Suggested next steps
1. Multi-clip subtitle offset support — apply timeline clip start time to segment timestamps before burn
2. Word-level timestamps — `word_timestamps=True` in `WhisperWorker` already has the field; wire to `SubtitleOverlay` for karaoke-style highlighting
3. CUDA device selector in `WhisperDialog`
4. Subtitle preview toggle button in toolbar (show/hide overlay without clearing)
5. Persist `SubtitleStyle` to the project save file

---

## Dependencies

### New (this session)
```bash
pip install faster-whisper
```

faster-whisper downloads Whisper model weights from HuggingFace on first use (~74MB for `base`). Models are cached in `~/.cache/huggingface/hub/`.

### Pre-existing
- `ffmpeg` + `ffprobe` on PATH (Ubuntu: `sudo apt install ffmpeg`)
- `libass` — included in the Ubuntu `ffmpeg` package (confirmed: `--enable-libass` in build flags)
- PyQt6, PyQt6-Qt6, PyQt6-sip

---

## Commit Suggestion

```
feat(VideoEditorPlugin): add Whisper transcription + subtitle burn-in

New files:
  WhisperWorker.py       — faster-whisper QThread, streams TranscriptSegments
  WhisperDialog.py       — model/language/VAD picker dialog
  TranscriptPanel.py     — live scrollable transcript with seek, copy, export
  SubtitleStyle.py       — shared style dataclass (font, colour, position)
  SubtitleStyleDialog.py — visual style editor with live preview swatch
  SubtitleOverlay.py     — transparent QPainter overlay on QVideoWidget

Modified:
  FFmpegWorker.py   — SubtitleBurnWorker (ASS filter approach, ffprobe resolution)
  ExportDialog.py   — subtitle burn checkbox, two-pass export pipeline
  PreviewWidget.py  — SubtitleOverlay wiring, position_changed hooks
  VideoEditorWidget.py — Transcribe toolbar button, transcript/style state

Fixes:
  - VAD disabled by default (was silently dropping all music segments)
  - Qt6 splitter reveal requires deferred setSizes via QTimer.singleShot
  - ASS PlayResX/PlayResY from ffprobe prevents libass 384x288 assumption
  - Default font size 22px (was 36px, appeared oversized without PlayRes)
```