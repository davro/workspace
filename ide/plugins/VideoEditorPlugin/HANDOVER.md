# VideoEditorPlugin — Developer Handover

**Last updated:** 2025  
**Plugin path:** `ide/plugins/VideoEditorPlugin/`  
**Status:** Whisper transcription, live subtitle preview, subtitle burn-in, project
persistence, CUDA device selection — all implemented and tested.

---

## Plugin Overview

A non-linear video editor embedded in the Workspace IDE as a plugin. Built entirely
with PyQt6 and FFmpeg. No external video editing libraries.

### Entry point

```
VideoEditorPlugin.py      ← plugin loader, calls get_widget()
VideoEditorPlugin/
    __init__.py
    VideoEditorWidget.py  ← top-level QWidget, owns all panels
    ...
```

---

## Architecture

```
VideoEditorWidget
├── Toolbar  New / Open / Save / Import / URL Import / 🎙 Transcribe / 💬 Subtitles / ▶ Export
├── QSplitter (horizontal)  [_upper_splitter]
│   ├── MediaBin          — left panel, imported clips + thumbnails
│   ├── PreviewWidget     — video playback (SOURCE + TIMELINE modes)
│   │   ├── QGraphicsView (_view)
│   │   │   ├── QGraphicsVideoItem  (video, z=0)
│   │   │   ├── QGraphicsRectItem   (_sub_bg, z=1, subtitle background box)
│   │   │   └── QGraphicsTextItem   (_sub_text, z=2, subtitle text)
│   │   └── QLabel no_media_label   (shown when no clip loaded)
│   └── TranscriptPanel   — right panel (hidden until first transcription)
│       buttons: 📋 Copy | 💾 Export… | 🎨 Style | ✕ Clear | [title ✕]
│       search:  🔍 Search transcript… [count label]
└── TimelineWidget        — bottom, track editor
```

### Key state on VideoEditorWidget

| Attribute | Type | Purpose |
|---|---|---|
| `_whisper_workers` | `list[WhisperWorker]` | Keeps workers alive against GC |
| `_subtitle_segments` | `list[TranscriptSegment]` | Last completed transcription; passed to ExportDialog |
| `_subtitle_style` | `SubtitleStyle` | Current style; shared between preview scene + burn |
| `_subs_visible` | `bool` | Subtitle toggle state; synced with `btn_subs.isChecked()` |
| `_project_path` | `str \| None` | Current `.vep` file path; sidecar path derived from this |

---

## Video Rendering — Important Architecture Note

**`QVideoWidget` is NOT used.** Early versions tried overlaying a subtitle widget on
top of `QVideoWidget` but Qt6's FFmpeg multimedia backend renders video via a native
OpenGL surface that sits above all Qt child widgets in the X11 compositor, regardless
of z-order tricks (`raise_()`, `QStackedLayout`, tool windows — all fail).

**Solution:** `PreviewWidget` uses `QGraphicsVideoItem` inside a `QGraphicsScene`.
Everything is in Qt's software compositor, so `QGraphicsTextItem` subtitles render
reliably above the video on all backends and platforms.

```python
# In PreviewWidget._build_ui():
self._scene = QGraphicsScene(self)
self.video_item = QGraphicsVideoItem()           # z=0
self._sub_bg    = QGraphicsRectItem()            # z=1
self._sub_text  = QGraphicsTextItem()            # z=2
self._scene.addItem(self.video_item)
self._scene.addItem(self._sub_bg)
self._scene.addItem(self._sub_text)
self.player.setVideoOutput(self.video_item)      # not a QVideoWidget
```

Do not reintroduce `QVideoWidget` — the z-order problem is fundamental to the backend.

---

## Files — Current State

### `WhisperWorker.py`
QThread wrapper around `faster-whisper`.

**Class:** `WhisperWorker(QThread)`

| Signal | Args | Fired when |
|---|---|---|
| `segment_ready` | `(float, float, str)` | Each segment recognised |
| `progress` | `(float)` | 0.0–1.0 as segments stream in |
| `finished` | `(list[TranscriptSegment])` | All segments done |
| `error` | `(str)` | Any failure |

**Constructor params:**

| Param | Default | Notes |
|---|---|---|
| `source_path` | required | Video or audio file |
| `model_size` | `"base"` | `tiny/base/small/medium/large-v3` |
| `language` | `None` | ISO code or `None` for auto-detect |
| `device` | `"cpu"` | `"cpu"` or `"cuda:0"` etc — set from `WhisperDialog` |
| `compute_type` | `"int8"` | `"int8"` / `"float16"` / `"int8_float16"` — set from `WhisperDialog` |
| `source_duration` | `0.0` | For progress reporting only |

**`vad_filter` attribute:** Set as `worker.vad_filter = bool` after construction.
Defaults `False`. VAD kills all segments on music/short clips — leave off by default.

**Audio extraction:** For video files, runs `ffmpeg -ar 16000 -ac 1 -f wav` to a
temp file before passing to Whisper. Temp file deleted in `finally`.

**`TranscriptSegment` dataclass:**
```python
@dataclass
class TranscriptSegment:
    start: float
    end:   float
    text:  str
    words: list           # word-level timestamps (populated but not yet used in UI)

    def to_srt_block(self, index: int) -> str
    def to_vtt_block(self) -> str
```

**Important:** Always `_whisper_workers.append(worker)` in the caller — Python GC
kills QThreads without a live reference.

---

### `WhisperDialog.py`
Modal dialog for transcription settings, including CUDA device auto-detection.

**Class:** `WhisperDialog(QDialog)`

**Device detection — `detect_devices()` function:**

Called at import time, cached in `_DEVICES`. Probes `torch.cuda` for available GPUs.
Returns `list[(label, device_str, compute_type)]`. CPU is always the last entry.

Compute type is chosen automatically per GPU compute capability:
- `major >= 7` and `>= 3 GB VRAM` → `"float16"` (Volta, Turing, Ampere, Ada)
- Otherwise → `"int8_float16"` (Pascal GTX 10xx and older, low-VRAM cards)
- CPU → `"int8"`

**Output attributes** (read after `exec() == Accepted`):

| Attribute | Type | Notes |
|---|---|---|
| `selected_model` | `str` | e.g. `"base"` |
| `selected_language` | `str \| None` | ISO code or `None` |
| `selected_source` | `str` | File path |
| `selected_vad` | `bool` | VAD filter state |
| `selected_device` | `str` | e.g. `"cuda:0"` or `"cpu"` |
| `selected_compute_type` | `str` | e.g. `"float16"` or `"int8"` |

All six attributes are passed through to `WhisperWorker` in `VideoEditorWidget._transcribe()`.

---

### `TranscriptPanel.py`
Scrollable dockable panel, hidden until first transcription.

**Class:** `TranscriptPanel(QWidget)`

| Signal | Args | Fired when |
|---|---|---|
| `seek_requested` | `(float)` | User clicks a timestamp or presses Enter in search |
| `close_requested` | `()` | User clicks ✕ in title bar |
| `style_requested` | `()` | User clicks 🎨 Style |

**Public API:**
```python
add_segment(start, end, text)     # connect to WhisperWorker.segment_ready
set_segments(list)                # replace all at once (used by sidecar load)
set_progress(float)               # 0.0–1.0, hides bar at 1.0
set_status(str)
clear(keep_status=False)
```

**Search feature:** `QLineEdit` above the segment list. `textChanged` filters
`SegmentRow` visibility and highlights the matching substring in each visible row
using Qt rich text (`<span style="background:...">` inline). `returnPressed` emits
`seek_requested` with the first visible match's start time.

**Export formats:** `.srt`, `.vtt`, `.txt` via `QFileDialog`.

**Splitter reveal pattern** (Qt6 quirk): The panel starts hidden with 0px in the
splitter. To reveal it, call `.show()` then defer `setSizes()` via
`QTimer.singleShot(0, ...)` — Qt6 ignores `setSizes` on hidden widgets within the
same event loop tick.

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
Shared dataclass — single source of truth for subtitle appearance used by both the
live preview scene (`PreviewWidget`) and FFmpeg export (`SubtitleBurnWorker`).

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

**Position presets** (7 options): `Bottom Centre / Bottom Left / Bottom Right /
Top Centre / Top Left / Top Right / Centre`

**FFmpeg helpers:** `ffmpeg_fontcolor()`, `ffmpeg_bordercolor()`, `ffmpeg_boxcolor()`
return `0xRRGGBBAA` strings (unused now that burn uses ASS — kept for reference).
`ffmpeg_x()`, `ffmpeg_y()` return drawtext expression strings (also unused).

---

### `SubtitleStyleDialog.py`
Visual style editor with a live mini-preview swatch (`_PreviewLabel` subclass).

**Class:** `SubtitleStyleDialog(QDialog)`

**Constructor:** `SubtitleStyleDialog(initial: SubtitleStyle | None, parent)`

**Output:** `dialog.style` → `SubtitleStyle` (read after `exec() == Accepted`)

Works on a copy of the initial style — Cancel discards all changes.

---

### `PreviewWidget.py`
Video preview panel. SOURCE mode plays a single bin clip; TIMELINE mode plays the
assembled sequence.

**Subtitle scene items** (all live in `self._scene`):

| Item | Z-value | Purpose |
|---|---|---|
| `self.video_item` | 0 | `QGraphicsVideoItem` — video output |
| `self._sub_bg` | 1 | `QGraphicsRectItem` — optional background box |
| `self._sub_text` | 2 | `QGraphicsTextItem` — subtitle text |

**Internal subtitle methods:**

| Method | Purpose |
|---|---|
| `_update_subtitle(seconds)` | Called on every position tick; finds active segment and updates `_sub_text` |
| `_apply_subtitle_style()` | Applies `SubtitleStyle` to font, colour, text width |
| `_position_sub_items()` | Positions text and background box per `SubtitleStyle.position` |
| `_layout_scene()` | Called from `resizeEvent`; resizes scene rect and `video_item` to fill view |

**Public subtitle API (called from VideoEditorWidget):**
```python
set_subtitle_segments(segments: list)
set_subtitle_style(style: SubtitleStyle)
clear_subtitles()
set_subtitles_visible(visible: bool)
```

**`_show_video(visible: bool)`** — swaps `_view` and `no_media_label` visibility.
`no_media_label` is a root layout sibling of `_view`, NOT inside it — this ensures
`_view` is exactly the video area size with no padding from a hidden label.

**Position update call sites** — `_update_subtitle(seconds)` is called in three places:
- `_on_player_position_changed` (SOURCE mode)
- `_tl_tick` (TIMELINE mode playback tick)
- `_tl_seek` (TIMELINE mode seek)

**`player` and `audio_output`** are public attributes — `VideoEditorWidget` accesses
`self.preview.player` for error signal connection and `self.preview.audio_output` for
volume preservation on audio reconnect.

---

### `FFmpegWorker.py`
**`SubtitleBurnWorker(QThread)`** — burns subtitles into an exported video.

| Signal | Args |
|---|---|
| `progress` | `(float)` 0.0–1.0 |
| `finished` | `(str)` output path |
| `error` | `(str)` |
| `log` | `(str)` ffmpeg output line |

**Burn approach — ASS filter:**

`drawtext` with per-segment `enable='between(t,...)'` was abandoned — FFmpeg's
filtergraph parser mangles the escaping with 10+ chained filters.

Instead, `_write_ass()` generates a temp `.ass` (Advanced SubStation Alpha) file:
- `[Script Info]` includes `PlayResX/PlayResY` probed via `_probe_resolution()` —
  without this libass assumes 384×288 and scales font size up ~5×
- `[V4+ Styles]` maps all `SubtitleStyle` fields (colours in `&HAABBGGRR`, alignment
  in numpad layout)
- `[Events]` has one `Dialogue:` line per segment

FFmpeg command: `ffmpeg -vf ass=/tmp/tmpXXX.ass -c:v libx264 -crf 18 -preset fast -c:a copy`

Temp `.ass` deleted in `finally` regardless of success/failure.

**Cancel path:** `_run_ffmpeg_burn` calls `process.terminate()` then `process.wait()`
before deleting the partial output file. The `wait()` is important — terminate is
async and the file handle may still be open without it.

---

### `VideoEditorWidget.py`
**Key methods added this session:**

| Method | Purpose |
|---|---|
| `_transcribe()` | Import check → `WhisperDialog` → `WhisperWorker` → reveal panel |
| `_on_whisper_finished(segments)` | Store segments, push to preview scene, enable subtitle button |
| `_on_whisper_error(msg)` | Show status + `QMessageBox` |
| `_toggle_subtitles()` | Toggle `_subs_visible`, sync `btn_subs`, call `preview.set_subtitles_visible()` |
| `_open_subtitle_style()` | `SubtitleStyleDialog` → update `_subtitle_style` → push to preview |
| `_hide_transcript_panel()` | Collapse panel in splitter |
| `_on_player_error(error, msg)` | Handle `ResourceError` (suspend/resume audio loss) |
| `_reconnect_audio()` | Create fresh `QAudioOutput`, reattach to player — called 1s after error |
| `_save_sidecar(path)` | Write `<project>.vep.meta` JSON alongside project file |
| `_load_sidecar(path)` | Restore segments, style, panel visibility from sidecar |

**Subtitle toggle button (`btn_subs`):**
- `setCheckable(True)` — Qt handles pressed/released visual state
- Starts `setEnabled(False)` — enabled in `_on_whisper_finished` and `_load_sidecar`
- `T` keyboard shortcut wired via `QShortcut`; the shortcut handler checks
  `self.sender() is not self.btn_subs` to distinguish shortcut from button click

**`_export()` passes** `subtitle_segments` and `subtitle_style` to `ExportDialog`,
which owns the two-pass export pipeline (timeline render → subtitle burn).

---

## Project Persistence — Sidecar File

The `.vep` project file format is unchanged. Subtitle/transcript state is saved to a
companion JSON sidecar at `<project_path>.meta` (e.g. `project-sunglasses.vep.meta`).

**Sidecar schema (version 1):**
```json
{
  "version": 1,
  "subtitle_segments": [
    {"start": 0.0, "end": 5.2, "text": "I wear my sunglasses at night"}
  ],
  "subtitle_style": {
    "font_size": 22, "font_weight": "Bold", "font_family": "Arial",
    "text_color": [255, 255, 255, 255],
    "outline_color": [0, 0, 0, 255],
    "bg_color": [0, 0, 0, 140],
    "outline_width": 2, "bg_enabled": false,
    "position": "Bottom Centre", "margin": 40
  },
  "transcript_visible": true,
  "subs_visible": true
}
```

The sidecar is optional — if missing or corrupt, the project opens normally without
subtitles and no error is raised. If you rename the `.vep` file without renaming the
`.meta` file, the sidecar will not be found on next open.

---

## Environment Setup (`ide.sh`)

`torch` is installed separately from the main `REQUIREMENTS` array to ensure the
correct CUDA build is selected. **Do NOT add `torch` back to `REQUIREMENTS`** — the
PyPI default is CPU-only and silently breaks GPU transcription.

`install_torch()` detects GPU compute capability via
`nvidia-smi --query-gpu=compute_cap` and maps it to the correct PyTorch wheel:

| Compute capability | GPU family | PyTorch wheel |
|---|---|---|
| sm_6x (≤62) | Pascal — GTX 10xx, 1080 Ti | `cu118` |
| sm_7x (≤72) | Volta — V100 | `cu118` |
| sm_75 | Turing — RTX 20xx, GTX 16xx | `cu121` |
| sm_8x (≤86) | Ampere — RTX 30xx, A100 | `cu124` |
| sm_89 | Ada Lovelace — RTX 40xx | `cu124` |
| sm_90+ | Hopper / Blackwell — H100, RTX 50xx | `cu128` |
| No GPU | — | `cpu` |

**Why compute capability not driver CUDA version:** Driver CUDA version reflects the
maximum CUDA the driver *supports*, not what the GPU can run. A 1080 Ti (sm_61) with
a CUDA 13.0 driver would incorrectly get a cu128 wheel that drops sm_61 support.
Compute capability is the correct discriminator.

---

## Audio Recovery — Suspend/Resume

Qt6 + PipeWire crashes with `QSocketNotifier: Socket notifiers cannot be enabled or
disabled from another thread` after system suspend/resume. Root cause: PipeWire drops
the audio connection; Qt's multimedia thread panics trying to re-enable socket
notifiers on wake.

**Fix in `VideoEditorWidget`:**
```python
self.preview.player.errorOccurred.connect(self._on_player_error)
```

On `QMediaPlayer.Error.ResourceError` → stop player cleanly → 1-second delay →
create fresh `QAudioOutput` and reattach. The delay gives PipeWire time to recover.
This doesn't suppress the log warnings but prevents the segfault.

---

## Dependencies

### Core (in `REQUIREMENTS`)
```bash
pip install faster-whisper
```

faster-whisper downloads Whisper model weights from HuggingFace on first use.
Cached in `~/.cache/huggingface/hub/`. Model sizes: tiny ~39MB, base ~74MB,
small ~244MB, medium ~769MB, large-v3 ~1.5GB.

### Installed separately
```bash
bash ide.sh install   # detects GPU, installs correct torch wheel automatically
```

### Pre-existing
- `ffmpeg` + `ffprobe` on PATH (Ubuntu: `sudo apt install ffmpeg`)
- `libass` — included in the Ubuntu `ffmpeg` package (`--enable-libass` confirmed)
- PyQt6, PyQt6-Qt6, PyQt6-sip, PyQt6-WebEngine

---

## Known Issues / Testing Notes

### Tested and working
- CUDA GPU auto-detection in `WhisperDialog` (Pascal/GTX 10xx picks cu118 correctly)
- Transcription of music/singing clips (VAD off by default)
- Transcript panel reveal/collapse with correct splitter sizing
- Transcript search — filter, highlight, seek on Enter
- Live subtitle preview via `QGraphicsTextItem` in SOURCE and TIMELINE modes
- Subtitle toggle button + `T` keyboard shortcut
- Export → subtitle burn two-pass pipeline (ASS filter approach)
- `.srt` / `.vtt` / `.txt` export from transcript panel
- Clickable timestamps seeking preview
- Style dialog live preview swatch
- Project sidecar save/load — segments, style, panel state all restored on reopen
- Audio reconnect after suspend/resume (no more segfault)

### Not yet tested / known gaps
- **Multi-clip timelines** — `_subtitle_segments` holds transcription for one clip
  at a time. No timestamp offset is applied for clips that don't start at t=0 on the
  timeline. For a multi-clip export the burn will show subtitles at the source clip's
  timestamps, not the timeline position.
- **Long files on CPU** — VAD off means Whisper processes full audio; large files are
  slow without a GPU. CUDA device selector is implemented but requires correct PyTorch
  wheel (run `bash ide.sh install`).
- **Font availability** — `SubtitleStyleDialog` uses `QFontComboBox` (system fonts).
  ASS burn uses `fontconfig` to find the closest match; exotic fonts may not render
  identically in burned output vs preview.
- **Sidecar file rename** — renaming the `.vep` without renaming the `.meta` loses
  the sidecar. Could be addressed by embedding sidecar data inside the `.vep` format.
- **Word-level timestamps** — `TranscriptSegment.words` is populated by faster-whisper
  when `word_timestamps=True` is passed to `model.transcribe()`. Currently set to
  `False` in `WhisperWorker`. Enabling it would unlock karaoke-style word
  highlighting in the preview scene.

### Suggested next steps
1. **Multi-clip subtitle offset** — apply timeline clip start time to segment
   timestamps before burn. Requires reading `TimelineWidget`'s clip model to get
   each clip's timeline position and shifting segment start/end accordingly.
2. **Word-level karaoke highlighting** — set `word_timestamps=True` in
   `WhisperWorker`, wire `TranscriptSegment.words` to `_update_subtitle()` in
   `PreviewWidget` to highlight the active word in `_sub_text` using HTML markup.
3. **Confidence colouring in TranscriptPanel** — `faster-whisper` exposes
   `avg_logprob` and `no_speech_prob` per segment. Map to amber/red colouring in
   `SegmentRow` so users know where to double-check.
4. **Persist default `SubtitleStyle`** across sessions (not per-project) — save to
   a global preferences file in the IDE config directory.
5. **Sidecar embedded in `.vep`** — move meta into the project file to make rename
   safe, requires changes to `ClipModel.Project.save/load`.

---

## Deleted Files

- **`SubtitleOverlay.py`** — removed. Subtitle rendering moved into `PreviewWidget`
  using `QGraphicsTextItem` within `QGraphicsScene`. The previous approach of
  overlaying a transparent widget on `QVideoWidget` failed on Qt6's FFmpeg backend
  due to native OpenGL surface z-order. The file is gone — do not recreate it.