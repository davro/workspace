# VideoEditorPlugin — Developer Handover Document

**Version:** 0.2.0
**Status:** Beta — included in main Workspace IDE release
**Last Updated:** June 2026

---

## What This Is

A professional non-linear video editor (NLE) built entirely as a Workspace IDE plugin.
It follows the standard IDE plugin contract (`PLUGIN_NAME`, `get_widget()`, `initialize()`,
`cleanup()`) and drops into `ide/plugins/` like any other plugin.

The stack is: **PyQt6 UI → FFmpeg engine → yt-dlp downloader → faster-whisper (planned)**

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

---

## How the Plugin Loads

The IDE scans `ide/plugins/` for `.py` files, imports each, finds a class
matching the filename, and calls `initialize()` then `get_widget()`.

```python
# VideoEditorPlugin.py (entry point)
class VideoEditorPlugin:
    PLUGIN_NAME = "Video Editor"
    PLUGIN_VERSION = "0.2.0"
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

Project.save(path)    → .vep JSON file
Project.load(path)    → Project instance
```

**Critical:** `Clip.source_duration = out_point - in_point`. Never leave
`out_point = 0.0` — the position calculation `clip.timeline_end = timeline_position + source_duration`
will break and all subsequent clips will stack at position 0. Always set
`out_point = media_duration` explicitly when creating clips.

---

## Timeline UI (TimelineWidget.py)

Built on `QGraphicsScene` / `QGraphicsView`.

**Track ordering (top → bottom in scene):** V tracks reversed (V2 above V1),
then A tracks in order. This matches standard NLE convention where higher
V-track numbers = overlay layers rendered on top.

```python
track_order = list(reversed(v_tracks)) + a_tracks
```

**ClipItem** (`QGraphicsRectItem`) — draggable:
- Horizontal drag → updates `clip.timeline_position`
- Vertical drag → snaps to nearest valid track of same type via
  `TimelineScene.snap_y_for_drag()` — video clips can't land on audio tracks

**Per-track header widget** embedded via `QGraphicsProxyWidget`:
- 🔊/🔇 mute toggle (adds dark overlay tint on the lane)
- 🔓/🔒 lock toggle (wired, drag prevention TODO)
- ✕ remove (keeps minimum 1 V and 1 A track)

**Adding tracks:** `TimelineScene.add_track(track_type)` — appends to
`project.tracks` and calls `redraw()`.

---

## Preview Widget (PreviewWidget.py)

Two modes toggled by SOURCE / TIMELINE pill buttons above the video area:

**SOURCE mode:**
- `load_source(path)` → loads file into `QMediaPlayer`
- Scrubber = that file's duration
- Used when clicking a clip in the Media Bin

**TIMELINE mode:**
- Driven by `QTimer` (80ms tick = `_tl_tick()`)
- `_tl_position` = virtual playhead in project seconds
- `_clip_at(seconds)` finds the topmost video clip covering that position
  (highest `track_index` wins — V2 over V1)
- Auto-loads new source into player at clip transitions
- Gaps show `◼ Gap` placeholder
- Clicking timeline ruler calls `preview.timeline_seek(seconds)` which
  switches to TIMELINE mode automatically

**Key wiring** (in VideoEditorWidget):
```python
self.preview.set_project(project)          # call whenever project changes
self.preview.position_changed → timeline.set_playhead   # sync playhead
self.timeline.seek_requested → preview.timeline_seek    # ruler click
```

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

## Known Bugs Fixed in This Version

| Bug | Cause | Fix |
|-----|-------|-----|
| Second clip overwrites first on timeline | `Clip.out_point=0` → `source_duration=0` → `timeline_end=0` | Always set `out_point=media_duration` explicitly; added `media_duration` field as fallback |
| Preview only showed last bin clip selected | `_clip_at()` hardcoded `track_index==0` | Now picks highest `track_index` clip at that position (topmost layer) |
| Export skipped timeline gaps | Concat-file approach ignored `timeline_position` | Rewrote to `filter_complex` with segment builder: clips+black gap lavfi sources+concat |
| Gap audio error (`aevalsrc r=` invalid) | `r=` not valid in modern FFmpeg `aevalsrc` | Replaced with `anullsrc=channel_layout=stereo:sample_rate=44100` |
| SAR mismatch crash on gap export | Black lavfi source has SAR 1:1, phone video has non-square SAR | Added `setsar=1:1` to all video filter chains |
| Overlay export blank video (audio only) | Base yuv420p + overlay yuva420p → FFmpeg auto-negotiates yuv444p → Qt decoder fails | Force `format=yuv420p` after every `overlay` filter |
| YouTube download audio-only | AV1+Opus codec not supported by Qt on Linux | Added `--recode-video mp4` + libx264/aac postprocessor args |
| Transparent overlay padding blocked base layer | `pad` filter with `color=black` was opaque | Use `format=yuva420p` then `pad=...:color=black@0.0` for transparent letterbox bars |

---

## Next Features Planned (v0.3.0)

### 1. Whisper Transcription (immediate next task)

```
pip install faster-whisper
```

Files to create:
- `WhisperWorker.py` — runs `faster_whisper.WhisperModel` in a QThread
  - Emits `segment_ready(start, end, text)` signals as transcription progresses
  - Emits `finished(list[segment])` on completion
  - Supports model size selection: tiny/base/small/medium/large-v3
- `TranscriptPanel.py` — scrollable panel showing transcript segments
  - Clickable timestamps seek the timeline preview
  - Copy-to-clipboard button
  - Export as .srt / .vtt / .txt
- Caption track integration — convert segments to `Clip` objects on a `C1` track
- Export burn-in — FFmpeg `subtitles` filter applied after compositing

**Whisper integration point in VideoEditorWidget:**
Add a `🎙 Transcribe` button to the toolbar. On click, open a model-picker
dialog, run `WhisperWorker` on the selected bin clip or timeline audio,
show results in a dockable `TranscriptPanel`.

### 2. Trim / Split tools
- Drag clip edges to set `in_point` / `out_point` (razor trim handles)
- ✂ Split at playhead: split clip into two at `_tl_position`
- Already have `btn_split` in TimelineWidget toolbar — just needs implementation

### 3. Transitions
- FFmpeg `xfade` filter between adjacent clips on same track
- Types: fade, dissolve, wipe, slide
- Stored as `transition` field on `Clip` dataclass

### 4. Ollama Integration
- After Whisper transcription, send transcript text to local Ollama
- Use cases: auto title generation, content summary, cut point suggestions
- Ollama plugin already exists in the IDE — share its API rather than
  duplicating the HTTP client

---

## Testing Checklist Before Release

- [ ] Import local MP4, MOV, MKV, MP3, PNG
- [ ] URL import: YouTube Short (AV1+Opus → must transcode), Instagram Reel
- [ ] Add clip to V1, export single-track
- [ ] Add clips to V1 + V2, export multi-track (verify overlay, not concat)
- [ ] Add gap between clips on V1, export (verify black frames in gap)
- [ ] Timeline mode preview: play through V1→gap→V2 transition
- [ ] Save project (.vep), close, reopen, verify clips restored
- [ ] Mute A1 track, export (verify muted track audio absent)
- [ ] Remove V2 track (verify V1 clips unaffected)
- [ ] Export dialog: change quality CRF, verify smaller file with higher CRF

---

## Development Tips

**Running without full IDE:** The plugin can be loaded standalone for testing:
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
# Keep a reference: self._workers.append(worker)
```
Always keep a reference to running workers or Python GC will destroy them
mid-execution.

---

## File Change History Summary

| File | Key Changes |
|------|-------------|
| `ClipModel.py` | Added `media_duration` field; fixed `source_duration` to use it as fallback |
| `FFmpegWorker.py` | Full rewrite: multi-track compositing, gap support, overlay stacking, audio mixing, yuv420p force |
| `PreviewWidget.py` | Added SOURCE/TIMELINE dual mode; QTimer-driven timeline playback engine; topmost-track clip selection |
| `TimelineWidget.py` | Full rewrite: multi-track, per-track header widgets via QGraphicsProxyWidget, vertical clip drag with track-type snapping |
| `VideoEditorWidget.py` | URL import button/dialog wiring; set_project calls for preview sync; multi-track clip positioning |
| `DownloadWorker.py` | yt-dlp integration; AV1→H264 transcode; reliable output path detection via `--print after_move:filepath` |
| `DownloadDialog.py` | New file: professional URL import dialog with metadata preview, quality selector, progress |
| `VideoEditorPlugin.py` | v0.2.0; replaced print() with logging |
| `CONTEXT.md` | New file: architecture reference |
| `HANDOVER.md` | New file: this document |
