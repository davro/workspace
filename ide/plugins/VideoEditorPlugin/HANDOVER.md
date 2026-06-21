# VideoEditorPlugin — Developer Handover Document

**Version:** 0.3.0
**Status:** Beta — included in main Workspace IDE release
**Last Updated:** June 2026

---

## What This Is

A professional non-linear video editor (NLE) built entirely as a Workspace IDE plugin.
It follows the standard IDE plugin contract (`PLUGIN_NAME`, `get_widget()`, `initialize()`,
`cleanup()`) and drops into `ide/plugins/` like any other plugin.

The stack is: **PyQt6 UI → FFmpeg engine → yt-dlp downloader → faster-whisper (next)**

All heavy operations run in `QThread` workers — the UI never blocks.

---

## Directory Layout

```
ide/plugins/
├── VideoEditorPlugin.py              # Entry point — IDE loader picks this up
└── VideoEditorPlugin/
    ├── CONTEXT.md                    # Architecture & technical reference
    ├── HANDOVER.md                   # This file
    ├── __init__.py                   # Package marker
    ├── VideoEditorWidget.py          # Top-level QWidget — wires everything together
    ├── PreviewWidget.py              # Dual-mode video monitor (Source + Timeline)
    ├── TimelineWidget.py             # Multi-track QGraphicsView NLE timeline
    ├── MediaBin.py                   # Left panel — clip library + async thumbnails
    ├── ClipModel.py                  # Pure data layer: Clip, Track, Project (no Qt)
    ├── FFmpegWorker.py               # All FFmpeg/ffprobe ops in QThreads
    ├── ExportDialog.py               # Export settings + real-time progress dialog
    ├── DownloadWorker.py             # yt-dlp download + metadata fetch in QThreads
    └── DownloadDialog.py             # URL import dialog (YouTube, Kick, TikTok, etc.)
```

---

## System Dependencies

Must be installed on the host system, not via pip:

```bash
sudo apt install ffmpeg          # video engine — ffmpeg + ffprobe
sudo apt install yt-dlp          # URL import (or: pip install yt-dlp for latest)
```

Python deps (all in the IDE venv via `ide.sh install`):

```
PyQt6
PyQt6-Multimedia    # QMediaPlayer, QVideoWidget, QAudioOutput
```

The `ide.sh` script already includes `yt-dlp` in its REQUIREMENTS array.
`PyQt6-Multimedia` is installed as `PyQt6-Qt6Multimedia` on some distros —
if `QMediaPlayer` import fails, try: `pip install PyQt6-Qt6Multimedia`.

### PyQt6 import gotchas (learned the hard way)

In PyQt6 several classes moved out of `QtWidgets` compared to PyQt5:

| Class | Wrong (PyQt5) | Correct (PyQt6) |
|-------|--------------|-----------------|
| `QAction` | `QtWidgets` | `QtGui` |
| `QShortcut` | `QtWidgets` | `QtGui` |
| `QFileSystemModel` | `QtWidgets` | `QtGui` |
| `QInputDialog` | — | stays in `QtWidgets` |

`event.screenPos()` returns a `QPoint` directly in PyQt6 — do not call `.toPoint()` on it.

---

## How the Plugin Loads

The IDE scans `ide/plugins/` for `.py` files, imports each, finds a class
matching the filename, and calls `initialize()` then `get_widget()`.

```python
# VideoEditorPlugin.py (entry point)
class VideoEditorPlugin:
    PLUGIN_NAME = "Video Editor"
    PLUGIN_VERSION = "0.3.0"
    PLUGIN_HAS_UI = True

    def initialize(self): ...
    def get_widget(self, parent=None): ...
    def cleanup(self): ...
```

`get_widget()` lazy-imports `VideoEditorWidget` so startup is fast even if
PyQt6-Multimedia isn't installed yet.

---

## Data Model (ClipModel.py)

Zero Qt dependencies. All pure Python dataclasses — easy to test in isolation.

```
Project
├── name, width, height, fps
├── tracks: list[Track]
│   └── Track: track_id, name, track_type (video|audio), muted, locked
├── clips: list[Clip]
│   └── Clip: clip_id, source_path, track_index, track_type,
│             in_point, out_point, media_duration,
│             timeline_position, label, color
└── media_bin: list[str]   # source file paths

Project.save(path)         → .vep JSON file
Project.load(path)         → Project instance
Project.split_clip(id, t)  → new right-half Clip (inserted into clips list)
```

**Critical:** `Clip.source_duration = out_point - in_point`. Never leave
`out_point = 0.0` — the position calculation `clip.timeline_end = timeline_position + source_duration`
will break and all subsequent clips will stack at position 0. Always set
`out_point = media_duration` explicitly when creating clips.

### Trim methods (added v0.3.0)

```python
clip.trim_start(new_in_point)   # moves left edge; timeline_position adjusts so right edge stays fixed
clip.trim_end(new_out_point)    # moves right edge; timeline_position unchanged
```

Both clamp against `Clip.MIN_CLIP_DURATION = 0.1` seconds — a clip can never
be trimmed to zero length.

### Split method (added v0.3.0)

```python
right = project.split_clip(clip_id, split_seconds)
```

`split_seconds` is a **timeline position** (not a media offset). The method:
1. Calculates `media_split = clip.in_point + (split_seconds - clip.timeline_position)`
2. Mutates the left half in-place: `clip.out_point = media_split`
3. Creates a right half with `in_point=media_split`, `timeline_position=split_seconds`
4. Inserts the right half immediately after the left in `project.clips`
5. Returns the right half, or `None` if the split point is outside the clip or within
   `MIN_CLIP_DURATION` of either edge

---

## Timeline UI (TimelineWidget.py)

Built on `QGraphicsScene` / `QGraphicsView`.

**Track ordering (top → bottom in scene):** V tracks reversed (V2 above V1),
then A tracks in order. This matches standard NLE convention where higher
V-track numbers = overlay layers rendered on top.

```python
track_order = list(reversed(v_tracks)) + a_tracks
```

### ClipItem (v0.3.0 — rewritten)

`ClipItem` (`QGraphicsRectItem`) now has three drag modes:

| Mode | Trigger | Effect |
|------|---------|--------|
| `_MODE_MOVE` | Drag anywhere except the trim zones | Updates `clip.timeline_position`; vertical drag snaps to valid track |
| `_MODE_TRIM_START` | Drag left 8px of clip | Calls `clip.trim_start()` — left edge moves, right stays fixed |
| `_MODE_TRIM_END` | Drag right 8px of clip | Calls `clip.trim_end()` — right edge moves |

Cursor changes to `SizeHorCursor` when hovering over a trim zone (`TRIM_ZONE_PX = 8`).

**Right-click context menu** on any clip shows:
- Non-clickable info rows: clip name, media type, source duration, in/out points, trimmed duration, timeline position, track
- `✂ Split here (HH:MM:SS)` — splits at the exact right-click X position; also moves the playhead to that point so the preview re-evaluates immediately
- `✂ Split at playhead (HH:MM:SS)` — splits at the current playhead position
- `✏ Rename clip…` — `QInputDialog.getText` pre-filled with current label
- `🗑 Delete clip`

Both split options are disabled if the split position is within 0.1s of either edge.

### Signals (TimelineScene)

```python
clip_selected  = pyqtSignal(object)    # Clip — user clicked a clip
clip_moved     = pyqtSignal(object)    # Clip — drag released or rename
clip_split     = pyqtSignal(object)    # Clip — the new right-half after split
seek_requested = pyqtSignal(float)     # seconds — ruler click or split-here
track_changed  = pyqtSignal()          # any track add/remove/mute/lock/delete
```

### Split at playhead

```python
timeline.scene.split_at_playhead()   # splits all clips under the playhead
timeline._split_at_playhead()        # public slot — also calls _on_project_changed()
```

Bound to the `✂ Split` toolbar button and the `[S]` keyboard shortcut
(registered in `VideoEditorWidget._setup_shortcuts`).

**Per-track header widget** embedded via `QGraphicsProxyWidget`:
- 🔊/🔇 mute toggle
- 🔓/🔒 lock toggle (wired; drag prevention TODO)
- ✕ remove (keeps minimum 1 V and 1 A track)

**Adding tracks:** `TimelineScene.add_track(track_type)` — appends to
`project.tracks` and calls `redraw()`.

**Scene rect expansion:** `_on_project_changed()` recalculates `scene_w` from
`project.duration + 10s` buffer on every clip move, split, or delete. This
ensures the scrollable canvas grows when clips are dragged right past the
original project end.

---

## Preview Widget (PreviewWidget.py)

Two modes toggled by SOURCE / TIMELINE pill buttons above the video area.

**SOURCE mode:**
- `load_source(path)` → loads file into `QMediaPlayer`
- Scrubber = that file's duration
- Used when clicking a clip in the Media Bin

**TIMELINE mode:**
- Driven by `QTimer` (80ms tick = `_tl_tick()`)
- `_tl_position` = virtual playhead in project seconds
- `_clip_at(seconds)` finds the topmost video clip covering that position
  (highest `track_index` wins — V2 over V1)
- Gaps show `◼ Gap` placeholder; player is `stop()`-ed (not paused)
- Clicking the timeline ruler calls `preview.timeline_seek(seconds)` which
  switches to TIMELINE mode automatically

**Key wiring** (in VideoEditorWidget):
```python
self.preview.set_project(project)          # call whenever project changes
self.preview.position_changed → timeline.set_playhead   # sync playhead
self.timeline.seek_requested → preview.timeline_seek    # ruler click / split-here
```

### Critical preview internals (v0.3.0 fixes)

**`_UNSET` sentinel:**
```python
_UNSET = object()   # module-level singleton
self._tl_clip = _UNSET   # initial state and after every seek
```
`_tl_clip` uses `_UNSET` (not `None`) to mean "never evaluated". This
matters because when the playhead is in a gap `clip_now = None`, and if
`_tl_clip` were also `None` then `clip_now is not _tl_clip` would be `False`
and the gap would never be displayed. The sentinel is always unequal to
`None` or any `Clip`, so the transition fires correctly on the first tick
after every seek or play-start.

**`_live_duration()`:**
```python
def _live_duration(self) -> float:
    if self._project:
        return self._project.duration
    return self._tl_duration
```
`_tl_duration` was historically set once on `set_project()` and never
updated. After a drag that creates a gap, `project.duration` grows but
`_tl_duration` stayed stale — the playhead would hard-stop at the old end.
All clamping and end-of-timeline checks now call `_live_duration()`.

**`_current_source` gap reset:**
When entering a gap (in `_tl_tick`, `_tl_seek`, `_tl_play`):
```python
self.player.stop()
self._current_source = None   # CRITICAL — see below
```
Without this, when the next clip shares the same source file (always true
for splits), `_load_clip` sees `_current_source == clip.source_path` and
skips `setSource`, calling `setPosition` on a stopped player instead.
`setPosition` on a stopped Qt media player is silently ignored — playback
starts from position 0. Clearing `_current_source` forces `setSource` to
be called, which triggers the `BufferedMedia` seek path.

**`BufferedMedia` vs `LoadedMedia`:**
```python
def _on_media_status_changed(self, status):
    if status == QMediaPlayer.MediaStatus.BufferedMedia:   # NOT LoadedMedia
        if self._pending_seek_ms is not None:
            self.player.setPosition(self._pending_seek_ms)
            ...
```
`LoadedMedia` fires when the source URL is accepted but before any data is
buffered — `setPosition` at that point is ignored. `BufferedMedia` fires
once Qt has enough data to honour a seek. Always use `BufferedMedia` for
post-source-change seeks.

**`_pending_play` flag:**
`_load_clip` saves `self._pending_play = self._tl_playing` at load time.
`_on_media_status_changed` reads it back to decide whether to call
`player.play()` after seeking — needed because the seek is asynchronous.

---

## Keyboard Shortcuts (VideoEditorWidget)

| Key | Action |
|-----|--------|
| `Space` | Play / pause |
| `S` | Split at playhead |
| `Delete` | Delete selected clip |
| `Backspace` | Delete selected clip |
| `Ctrl+S` | Save project |

---

## Media Bin (MediaBin.py)

- Import dialog opens at `~/Videos` by default (falls back to `~` if not found)
- File filter pre-selected: `All Files (*)` — user can switch to specific types
- Supported formats: MP4, MOV, AVI, MKV, WEBM, M4V, MPG, MPEG, WMV, FLV, MP3,
  WAV, AAC, M4A, FLAC, OGG, OPUS, JPG, JPEG, PNG, BMP, GIF, TIFF, WEBP
- Right-click context menu: Add to Timeline, Remove from Bin

---

## Export Pipeline (FFmpegWorker.py)

Multi-track compositing model:

```
For each V track (sorted by track_index):
    Build a segment list: [clip, gap, clip, gap, ...]
    Trailing gap fills to total project duration

    V1 (base):    gaps → opaque black (color lavfi source)
    V2+ (overlay): gaps → transparent (colorchannelmixer=aa=0.0)

    Real clips:   scale+pad to canvas → format=yuv420p (base)
                                      → format=yuva420p (overlay)
    Concat all segments → [vtrackN]

Stack tracks:
    [vtrack0][vtrack1]overlay=0:0:format=auto,format=yuv420p[vstack1]
                                              ^^^^^^^^^^^^^^
                        CRITICAL: force yuv420p here or libx264 picks
                        yuv444p "High 4:4:4 Predictive" profile which
                        Qt's h264 decoder renders as blank/audio-only video.

For each A track (non-muted) + embedded audio from each V track:
    Build segment list with anullsrc silence in gaps
    Concat → [atrackN]

Mix all audio: amix=inputs=N:duration=longest:normalize=0

Output: -map [vout] -map [aout] -c:v libx264 -c:a aac
```

**Worker signals:**
```python
ExportWorker.progress(float)    # 0.0–1.0, connect to progress bar
ExportWorker.finished(str)      # output path on success
ExportWorker.error(str)         # human-readable error
ExportWorker.log(str)           # raw ffmpeg output line
```

---

## URL Import (DownloadWorker.py + DownloadDialog.py)

Two-stage process:

**Stage 1 — MetadataWorker:**
- `yt-dlp --dump-json --no-download URL`
- Returns title, duration, platform, available quality formats
- Populates the dialog's metadata card before any download starts

**Stage 2 — DownloadWorker:**
- Format selection: always appends `+bestaudio` to video-only format IDs
- Key flags:
  ```
  --recode-video mp4
  --postprocessor-args "ffmpeg:-c:v libx264 -crf 23 -preset fast -c:a aac -b:a 192k"
  ```
  This is **essential** — YouTube Shorts serve AV1+Opus which Qt cannot
  decode on Linux. The postprocessor re-encodes to H.264+AAC after download.
- Output path detection uses `--print after_move:filepath` (most reliable),
  falling back to `[Merger]` line parsing, then `_find_latest_mp4()` scan.

**Platform detection:** `platform_icon()` and `platform_colour()` in
`DownloadWorker.py` map extractor names to emoji icons and brand colours
for the dialog UI.

---

## Bugs Fixed in v0.3.0

| Bug | Cause | Fix |
|-----|-------|-----|
| Playhead hard-stopped at original video end after clip drag | `_tl_duration` set once at `set_project()`, never updated | `_live_duration()` always reads `project.duration` live |
| Gap skipped on first play after split | `_tl_clip=None` equalled `clip_now=None` in a gap — transition never fired | `_UNSET` sentinel; `is not` identity check instead of `!=` |
| Split right-half played from position 0 | `LoadedMedia` fires before Qt can honour `setPosition` | Seek deferred to `BufferedMedia` in `_on_media_status_changed` |
| Same-source split replayed from 0 after gap | `_current_source` not cleared on gap entry — `_load_clip` skipped `setSource` and called `setPosition` on stopped player | `_current_source = None` on every gap entry; forces `setSource` |
| Gap showed previous frame (not black) | `player.pause()` in gap held decode position | `player.stop()` in gap; `no_media_label` shown |
| Timeline canvas didn't grow after drag | `setSceneRect` only called at redraw, not on clip move | `_on_project_changed()` recalculates scene rect from `project.duration` |
| Split-here gap ignored on |<< then play | Playhead not moved after split-here — preview `_tl_clip` still matched old clip | `split-here` emits `seek_requested` to move playhead to split point |
| `QAction` ImportError on load | `QAction` moved from `QtWidgets` to `QtGui` in PyQt6 | Import from `PyQt6.QtGui` |
| `AttributeError: 'QPoint' has no attribute 'toPoint'` crash | PyQt6 `screenPos()` returns `QPoint` directly | Removed `.toPoint()` call |

---

## Next Features Planned (v0.4.0)

### 1. Whisper Transcription (immediate next task)

```bash
pip install faster-whisper
```

Files to create:
- `WhisperWorker.py` — runs `faster_whisper.WhisperModel` in a `QThread`
  - Emits `segment_ready(start, end, text)` as transcription progresses
  - Emits `finished(list[segment])` on completion
  - Supports model size selection: `tiny` / `base` / `small` / `medium` / `large-v3`
- `TranscriptPanel.py` — scrollable dockable panel
  - Clickable timestamps → `preview.timeline_seek(seconds)`
  - Copy-to-clipboard button
  - Export as `.srt` / `.vtt` / `.txt`
- Caption track — convert segments to `Clip` objects on a `C1` caption track
- Export burn-in — FFmpeg `subtitles` filter applied after compositing

**Integration point in VideoEditorWidget:**
Add a `🎙 Transcribe` button to the toolbar. On click, open a model-picker
dialog, run `WhisperWorker` on the selected bin clip or timeline audio,
show results in a dockable `TranscriptPanel`.

You will need `MediaBin.py` and `PreviewWidget.py` in addition to
`VideoEditorWidget.py` to implement this correctly.

### 2. Transitions
- FFmpeg `xfade` filter between adjacent clips on same track
- Types: fade, dissolve, wipe, slide
- Store as a `transition` field on the `Clip` dataclass
- Render in `FFmpegWorker` between clip segments

### 3. Ollama Integration
- After Whisper transcription, send transcript to local Ollama
- Use cases: auto title generation, content summary, cut point suggestions
- Ollama plugin already exists in the IDE — share its HTTP client rather
  than duplicating it

### 4. Lock drag prevention (partial)
- Track lock toggle is wired and stored in `Track.locked`
- `ClipItem` drag does not yet check `locked` — needs a guard in
  `mousePressEvent` and `itemChange`

---

## Testing Checklist Before Release

- [ ] Import local MP4, MOV, MKV, MP3, PNG
- [ ] URL import: YouTube Short (AV1+Opus → must transcode), Instagram Reel
- [ ] Add clip to V1, export single-track
- [ ] Add clips to V1 + V2, export multi-track (verify overlay, not concat)
- [ ] Add gap between clips on V1, export (verify black frames in gap)
- [ ] Timeline preview: play through clip → gap → clip; verify gap is black
- [ ] Split at playhead: verify both halves play correctly from start
- [ ] Split here (right-click): verify right half starts at correct in_point
- [ ] Trim left edge: verify right edge stays anchored
- [ ] Trim right edge: verify left edge stays anchored
- [ ] |<< after split-here: verify playback respects gap
- [ ] Drag clip right past original end: verify canvas/playhead extends
- [ ] Right-click context menu: info rows show correct timecodes
- [ ] Rename clip: label updates on timeline block immediately
- [ ] Save project (.vep), close, reopen, verify clips/trims/labels restored
- [ ] Mute A1 track, export (verify muted track audio absent)
- [ ] Remove V2 track (verify V1 clips unaffected)
- [ ] Export dialog: change quality CRF, verify smaller file with higher CRF

---

## Development Tips

**Running without full IDE:**
```python
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)

class FakeAPI:
    def show_status_message(self, msg, ms): print(msg)
    def register_keyboard_shortcut(self, *a): pass
    def unregister_all_plugin_hooks(self, *a): pass

from VideoEditorPlugin.VideoEditorWidget import VideoEditorWidget
class FakePlugin:
    api = FakeAPI()

w = VideoEditorWidget(FakePlugin())
w.resize(1400, 900)
w.show()
sys.exit(app.exec())
```

**FFmpeg filter debugging:** The full command is logged to the Export dialog's
log panel. Copy it and run manually in terminal to see raw FFmpeg stderr.

**QThread worker pattern:** All workers follow the same pattern:
```python
worker = SomeWorker(args, parent=self)
worker.finished.connect(self._on_done)
worker.error.connect(self._on_error)
worker.start()
self._workers.append(worker)   # REQUIRED — GC will kill workers without a reference
```

**Uploading source files for AI-assisted development:** Always copy the
output files back into the plugin directory before the next session and
re-upload from there. If you upload a stale file, the AI will receive the
old version and re-apply fixes that are already in place. The canonical
source of truth is the files in `ide/plugins/VideoEditorPlugin/`.

---

## File Change History Summary

| File | v0.2.0 | v0.3.0 |
|------|--------|--------|
| `ClipModel.py` | Added `media_duration` field; fixed `source_duration` fallback | Added `trim_start()`, `trim_end()`, `split_clip()`, `MIN_CLIP_DURATION` |
| `TimelineWidget.py` | Full rewrite: multi-track, proxy header widgets, vertical snap | Added trim handles on `ClipItem`; split at playhead; right-click context menu; scene rect auto-expansion; `clip_split` signal; `QAction` → `QtGui` |
| `VideoEditorWidget.py` | URL import wiring; `set_project` calls; multi-track positioning | `[S]` split shortcut; `[Delete]`/`[Backspace]` delete shortcut |
| `PreviewWidget.py` | SOURCE/TIMELINE dual mode; QTimer playback engine | `_UNSET` sentinel; `_live_duration()`; `_current_source` gap reset; `BufferedMedia` seek; `player.stop()` in gaps; `_pending_play` flag |
| `MediaBin.py` | Clip library, async thumbnails, bin context menu | Import dialog defaults to `~/Videos`; pre-selects `All Files` filter |
| `FFmpegWorker.py` | Full rewrite: compositing, gap support, yuv420p force | No changes |
| `DownloadWorker.py` | yt-dlp integration; AV1→H264 transcode | No changes |
| `DownloadDialog.py` | New file: URL import dialog | No changes |
| `VideoEditorPlugin.py` | v0.2.0; replaced `print()` with `logging` | Version bump to 0.3.0 |