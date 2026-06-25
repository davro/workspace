"""
FFmpegWorker — All FFmpeg operations run in background QThreads.

Never call FFmpeg on the main thread. Use these workers and connect
to their signals.
"""

import subprocess
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from .ClipModel import Clip, Project, MediaInfo, ClipType, TrackType, seconds_to_tc


# ---------------------------------------------------------------------------
# Helpers — ffprobe / ffmpeg discovery
# ---------------------------------------------------------------------------

def _find_ffmpeg() -> str:
    for candidate in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, timeout=3)
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return "ffmpeg"


def _find_ffprobe() -> str:
    for candidate in ["ffprobe", "/usr/bin/ffprobe", "/usr/local/bin/ffprobe"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, timeout=3)
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return "ffprobe"


FFMPEG  = _find_ffmpeg()
FFPROBE = _find_ffprobe()


# ---------------------------------------------------------------------------
# ProbeWorker
# ---------------------------------------------------------------------------

class ProbeWorker(QThread):
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        try:
            info = probe_file(self.path)
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


def probe_file(path: str) -> MediaInfo:
    cmd = [
        FFPROBE, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data    = json.loads(result.stdout)
    fmt     = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration") or 0)
    if not duration and video_stream:
        duration = float(video_stream.get("duration") or 0)

    fps = 0.0
    if video_stream:
        r_frame_rate = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = r_frame_rate.split("/")
            fps = float(num) / float(den) if float(den) else 0.0
        except (ValueError, ZeroDivisionError):
            fps = 0.0

    ext = Path(path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}:
        clip_type = ClipType.IMAGE
        duration  = duration or 5.0
    elif video_stream:
        clip_type = ClipType.VIDEO
    else:
        clip_type = ClipType.AUDIO

    return MediaInfo(
        path         = path,
        clip_type    = clip_type,
        duration     = duration,
        width        = int(video_stream.get("width",  0)) if video_stream else 0,
        height       = int(video_stream.get("height", 0)) if video_stream else 0,
        fps          = fps,
        codec        = video_stream.get("codec_name", "") if video_stream else "",
        audio_codec  = audio_stream.get("codec_name", "") if audio_stream else "",
        file_size    = int(fmt.get("size", 0)),
    )


# ---------------------------------------------------------------------------
# ThumbnailWorker
# ---------------------------------------------------------------------------

class ThumbnailWorker(QThread):
    finished = pyqtSignal(str, str)
    error    = pyqtSignal(str, str)

    def __init__(self, path: str, out_path: str, seek: float = 0.5, parent=None):
        super().__init__(parent)
        self.path     = path
        self.out_path = out_path
        self.seek     = seek

    def run(self):
        try:
            cmd = [
                FFMPEG, "-y",
                "-ss", str(self.seek),
                "-i", self.path,
                "-vframes", "1",
                "-vf", "scale=160:-1",
                "-q:v", "3",
                self.out_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            if result.returncode == 0 and Path(self.out_path).exists():
                self.finished.emit(self.path, self.out_path)
            else:
                self.error.emit(self.path, "Thumbnail extraction failed")
        except Exception as e:
            self.error.emit(self.path, str(e))


# ---------------------------------------------------------------------------
# ExportWorker
# ---------------------------------------------------------------------------

class ExportWorker(QThread):
    """
    Export a Project to a video file using FFmpeg filter_complex.

    Multi-track compositing model:
    -------------------------------
    - Each VIDEO track is built as its own composited sub-sequence:
      real clips placed at their timeline_position, with gaps filled.
        * On the BASE track (lowest track_index) gaps are opaque BLACK.
        * On every track STACKED ABOVE the base, gaps are TRANSPARENT
          (alpha=0) so the base layer shows through where the upper
          track has nothing.
    - Muted tracks are skipped entirely for video (still composited
      visually — mute only affects audio) — actually for video, "muted"
      has no visual meaning, so video tracks always render regardless
      of the muted flag (mute is audio-only by convention).
    - All composited video tracks are stacked with `overlay`, in
      ascending track_index order (track 0 = base/bottom, higher
      track_index = on top) — matching the timeline's visual stacking.
    - Each AUDIO track is similarly built as its own composited
      sub-sequence (silence in gaps), MUTED tracks excluded entirely.
    - All non-muted audio sub-sequences are mixed together with `amix`.

    Signals
    -------
    progress(float)   0.0 – 1.0
    finished(str)      output path on success
    error(str)         human-readable error message
    log(str)           ffmpeg output line
    """

    progress = pyqtSignal(float)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)
    log      = pyqtSignal(str)

    def __init__(self, project: Project, output_path: str,
                 preset: str = "medium", crf: int = 23, parent=None):
        super().__init__(parent)
        self.project     = project
        self.output_path = output_path
        self.preset      = preset
        self.crf         = crf
        self._cancelled  = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._export()
        except Exception as e:
            self.error.emit(str(e))

    # =========================================================================
    # Main export
    # =========================================================================

    def _export(self):
        project = self.project
        W, H, fps = project.width, project.height, project.fps

        total_duration = project.duration
        if total_duration <= 0:
            self.error.emit("Timeline duration is zero.")
            return

        video_tracks = [t for t in project.tracks if t.track_type == TrackType.VIDEO]
        audio_tracks = [t for t in project.tracks if t.track_type == TrackType.AUDIO]

        if not video_tracks or not any(
            c.track_type == TrackType.VIDEO for c in project.clips
        ):
            self.error.emit("No video clips on the timeline.")
            return

        cmd_inputs   = []     # flat list of -i / -f lavfi args, in order
        filter_parts = []     # filter_complex lines
        input_idx    = 0      # running index into cmd_inputs' -i entries

        # ------------------------------------------------------------------
        # Build one composited stream per VIDEO track
        # ------------------------------------------------------------------
        track_video_labels = []   # [(track_index, "[vtrackN]")] bottom→top order

        # Sort tracks by their index in project.tracks (creation order),
        # which we treat as bottom(0) → top(N) stacking order matching
        # the same convention used by the timeline UI's track_index field.
        sorted_v_tracks = sorted(
            range(len(video_tracks)), key=lambda i: i
        )

        for v_idx in sorted_v_tracks:
            is_base = (v_idx == 0)
            clips_on_track = sorted(
                [c for c in project.clips
                 if c.track_type == TrackType.VIDEO and c.track_index == v_idx],
                key=lambda c: c.timeline_position
            )

            label, new_idx = self._build_video_track_stream(
                clips_on_track, v_idx, is_base,
                W, H, fps, total_duration,
                cmd_inputs, filter_parts, input_idx
            )
            input_idx = new_idx
            track_video_labels.append((v_idx, label))

        if not track_video_labels:
            self.error.emit("No video tracks could be composited.")
            return

        # ------------------------------------------------------------------
        # Stack video tracks with overlay: base first, each higher track
        # overlaid on top of the running composite.
        # ------------------------------------------------------------------
        track_video_labels.sort(key=lambda pair: pair[0])   # ascending: base→top
        composite_label = track_video_labels[0][1]

        for i in range(1, len(track_video_labels)):
            _, upper_label = track_video_labels[i]
            out_label = f"[vstack{i}]"
            filter_parts.append(
                # Force yuv420p after overlay — without this, mixing yuv420p (base)
                # with yuva420p (overlay alpha track) causes FFmpeg to auto-negotiate
                # yuv444p which Qt's h264 decoder renders as blank/audio-only video.
                f"{composite_label}{upper_label}overlay=0:0:format=auto,format=yuv420p{out_label};"
            )
            composite_label = out_label

        final_video_label = composite_label

        # ------------------------------------------------------------------
        # Build one composited stream per AUDIO track (skip muted tracks)
        # ------------------------------------------------------------------
        audio_labels = []

        for a_idx in range(len(audio_tracks)):
            track = audio_tracks[a_idx]
            if track.muted:
                continue   # excluded entirely from the mix

            clips_on_track = sorted(
                [c for c in project.clips
                 if c.track_type == TrackType.AUDIO and c.track_index == a_idx],
                key=lambda c: c.timeline_position
            )
            if not clips_on_track:
                continue

            label, new_idx = self._build_audio_track_stream(
                clips_on_track, total_duration,
                cmd_inputs, filter_parts, input_idx
            )
            input_idx = new_idx
            audio_labels.append(label)

        # Also include audio from VIDEO clips themselves (each video clip's
        # own embedded audio track, composited per video track same as above)
        for v_idx in sorted_v_tracks:
            clips_on_track = sorted(
                [c for c in project.clips
                 if c.track_type == TrackType.VIDEO and c.track_index == v_idx],
                key=lambda c: c.timeline_position
            )
            if not clips_on_track:
                continue
            label, new_idx = self._build_audio_track_stream(
                clips_on_track, total_duration,
                cmd_inputs, filter_parts, input_idx,
                label_prefix=f"va{v_idx}"
            )
            input_idx = new_idx
            audio_labels.append(label)

        if not audio_labels:
            # No audio anywhere — generate silence for the full duration
            cmd_inputs += [
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-t", f"{total_duration:.6f}",
            ]
            filter_parts.append(f"[{input_idx}:a]anull[aout_silent];")
            final_audio_label = "[aout_silent]"
            input_idx += 1
        elif len(audio_labels) == 1:
            final_audio_label = audio_labels[0]
        else:
            mix_in = "".join(audio_labels)
            filter_parts.append(
                f"{mix_in}amix=inputs={len(audio_labels)}:duration=longest:normalize=0[aout_mixed];"
            )
            final_audio_label = "[aout_mixed]"

        # ------------------------------------------------------------------
        # Final output mapping
        # ------------------------------------------------------------------
        filter_parts.append(
            f"{final_video_label}null[vout];"
            f"{final_audio_label}anull[aout];"
        )

        filter_complex = "".join(filter_parts)

        cmd = (
            [FFMPEG, "-y"]
            + cmd_inputs
            + [
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", self.preset,
                "-crf", str(self.crf),
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                "-t", f"{total_duration:.6f}",
                "-progress", "pipe:1",
                self.output_path,
            ]
        )

        self.log.emit(f"FFmpeg command:\n{' '.join(cmd)}\n")
        self._run_ffmpeg(cmd, total_duration)

    # =========================================================================
    # Per-track video compositing
    # =========================================================================

    def _build_video_track_stream(self, clips, track_index, is_base,
                                   W, H, fps, total_duration,
                                   cmd_inputs, filter_parts, input_idx):
        """
        Build a single composited video stream for one V-track spanning the
        full timeline duration. Returns (output_label, new_input_idx).

        Gaps on the base track are opaque black.
        Gaps on any other (overlay) track are transparent so the layer(s)
        below show through.
        """
        # Base track: scale to fill the full canvas, padded with OPAQUE black
        # (there is nothing beneath it, so opaque bars are correct/expected).
        base_scale_pad = (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1:1,fps={fps}"
        )
        # Overlay tracks: still need every segment at the SAME WxH so concat
        # can join them — but pad with TRANSPARENT pixels instead of opaque
        # black, so letterbox bars don't block the layer(s) beneath. The
        # `pad` filter itself only fills with a solid colour (no alpha), so
        # we pad first then zero the alpha only in the padded border by
        # using `format=yuva420p` + a full-frame alpha of 255 followed by
        # compositing the original (opaque) clip over a transparent base —
        # in practice the simplest robust approach is: scale down (no pad),
        # convert to yuva420p, then pad with `pad=...:color=black@0.0`. Some
        # ffmpeg builds honour @alpha on `pad`'s color even though they
        # don't on lavfi `color` sources, since `pad` operates as a filter
        # on an existing format rather than generating raw frames.
        overlay_scale_pad = (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"setsar=1:1,fps={fps},format=yuva420p,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black@0.0"
        )
        scale_pad = base_scale_pad if is_base else overlay_scale_pad
        pix_fmt   = "format=yuv420p" if is_base else "format=yuva420p"

        segments = []   # (duration, clip_or_None)
        prev_end = 0.0
        for clip in clips:
            t_start = clip.timeline_position
            t_end   = clip.timeline_end
            gap     = t_start - prev_end
            if gap > 0.02:
                segments.append((gap, None))
            if clip.source_duration > 0:
                segments.append((clip.source_duration, clip))
            prev_end = t_end

        # Trailing gap to fill out the full timeline duration
        trailing = total_duration - prev_end
        if trailing > 0.02:
            segments.append((trailing, None))

        if not segments:
            segments = [(total_duration, None)]

        seg_labels = []
        for seg_idx, (seg_dur, clip) in enumerate(segments):
            vl = f"[t{track_index}v{seg_idx}]"

            if clip is None:
                cmd_inputs += [
                    "-f", "lavfi",
                    "-i", f"color=c=black:s={W}x{H}:r={fps}:d={seg_dur:.6f}"
                ]
                if is_base:
                    # Opaque black gap on the base track
                    filter_parts.append(
                        f"[{input_idx}:v]fps={fps},setsar=1:1,{pix_fmt},setpts=PTS-STARTPTS{vl};"
                    )
                else:
                    # Fully transparent gap so the layer(s) below show through.
                    # The `color` lavfi source ignores @alpha on its own, so we
                    # force yuva420p then zero the alpha channel explicitly.
                    filter_parts.append(
                        f"[{input_idx}:v]fps={fps},setsar=1:1,format=yuva420p,"
                        f"colorchannelmixer=aa=0.0,setpts=PTS-STARTPTS{vl};"
                    )
                input_idx += 1
            else:
                cmd_inputs += [
                    "-ss", f"{clip.in_point:.6f}",
                    "-t",  f"{seg_dur:.6f}",
                    "-i",  clip.source_path,
                ]
                filter_parts.append(
                    f"[{input_idx}:v]{scale_pad},{pix_fmt},setpts=PTS-STARTPTS{vl};"
                )
                input_idx += 1

            seg_labels.append(vl)

        # Concat this track's segments into one continuous stream
        out_label = f"[vtrack{track_index}]"
        if len(seg_labels) == 1:
            # Single segment — just rename via a no-op filter
            filter_parts.append(f"{seg_labels[0]}null{out_label};")
        else:
            concat_in = "".join(seg_labels)
            filter_parts.append(
                f"{concat_in}concat=n={len(seg_labels)}:v=1:a=0{out_label};"
            )

        return out_label, input_idx

    # =========================================================================
    # Per-track audio compositing
    # =========================================================================

    def _build_audio_track_stream(self, clips, total_duration,
                                   cmd_inputs, filter_parts, input_idx,
                                   label_prefix=None):
        """
        Build a single composited audio stream for one track spanning the
        full timeline duration, with silence filling gaps.
        Returns (output_label, new_input_idx).
        """
        prefix = label_prefix if label_prefix else f"a{id(clips) % 10000}"

        segments = []
        prev_end = 0.0
        for clip in clips:
            t_start = clip.timeline_position
            t_end   = clip.timeline_end
            gap     = t_start - prev_end
            if gap > 0.02:
                segments.append((gap, None))
            if clip.source_duration > 0:
                segments.append((clip.source_duration, clip))
            prev_end = t_end

        trailing = total_duration - prev_end
        if trailing > 0.02:
            segments.append((trailing, None))

        if not segments:
            segments = [(total_duration, None)]

        seg_labels = []
        for seg_idx, (seg_dur, clip) in enumerate(segments):
            al = f"[{prefix}a{seg_idx}]"

            if clip is None:
                cmd_inputs += [
                    "-f", "lavfi",
                    "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-t", f"{seg_dur:.6f}",
                ]
                filter_parts.append(
                    f"[{input_idx}:a]atrim=duration={seg_dur:.6f},asetpts=PTS-STARTPTS{al};"
                )
                input_idx += 1
            else:
                cmd_inputs += [
                    "-ss", f"{clip.in_point:.6f}",
                    "-t",  f"{seg_dur:.6f}",
                    "-i",  clip.source_path,
                ]
                filter_parts.append(
                    f"[{input_idx}:a]asetpts=PTS-STARTPTS,apad=whole_dur={seg_dur:.6f}{al};"
                )
                input_idx += 1

            seg_labels.append(al)

        out_label = f"[atrack_{prefix}]"
        if len(seg_labels) == 1:
            filter_parts.append(f"{seg_labels[0]}anull{out_label};")
        else:
            concat_in = "".join(seg_labels)
            filter_parts.append(
                f"{concat_in}concat=n={len(seg_labels)}:v=0:a=1{out_label};"
            )

        return out_label, input_idx

    # =========================================================================
    # Process runner
    # =========================================================================

    def _run_ffmpeg(self, cmd, total_duration):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in process.stdout:
            if self._cancelled:
                process.terminate()
                self.error.emit("Export cancelled.")
                return
            line = line.strip()
            self.log.emit(line)
            if line.startswith("out_time_ms="):
                try:
                    out_time = int(line.split("=")[1]) / 1_000_000
                    pct = min(out_time / total_duration, 1.0)
                    self.progress.emit(pct)
                except ValueError:
                    pass

        process.wait()

        if process.returncode == 0:
            self.progress.emit(1.0)
            self.finished.emit(self.output_path)
        else:
            self.error.emit(
                f"FFmpeg export failed (code {process.returncode}). "
                "Check the log above for details."
            )


# ---------------------------------------------------------------------------
# TrimWorker
# ---------------------------------------------------------------------------

class TrimWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, source: str, in_point: float, out_point: float,
                 output_path: str, parent=None):
        super().__init__(parent)
        self.source      = source
        self.in_point    = in_point
        self.out_point   = out_point
        self.output_path = output_path

    def run(self):
        try:
            duration = self.out_point - self.in_point
            cmd = [
                FFMPEG, "-y",
                "-ss", str(self.in_point),
                "-i", self.source,
                "-t", str(duration),
                "-c", "copy",
                self.output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                self.finished.emit(self.output_path)
            else:
                self.error.emit(result.stderr.decode(errors="replace")[-500:])
        except Exception as e:
            self.error.emit(str(e))



# ---------------------------------------------------------------------------
# SubtitleBurnWorker
# ---------------------------------------------------------------------------

class SubtitleBurnWorker(QThread):
    """
    Burns subtitles onto a video file using FFmpeg drawtext filters.

    One drawtext filter is generated per segment, enabled only during
    [start, end] using the 'enable' expression — no external font files
    or SRT parsing needed at runtime.

    Signals
    -------
    progress(float)   0.0-1.0
    finished(str)     output path
    error(str)        human-readable error
    log(str)          ffmpeg output line
    """

    progress = pyqtSignal(float)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)
    log      = pyqtSignal(str)

    def __init__(self, input_path: str, output_path: str,
                 segments: list, style,
                 total_duration: float = 0.0,
                 parent=None):
        """
        Parameters
        ----------
        input_path     : source video (already exported or raw clip)
        output_path    : destination
        segments       : list[TranscriptSegment]
        style          : SubtitleStyle instance
        total_duration : for progress reporting
        """
        super().__init__(parent)
        self.input_path      = input_path
        self.output_path     = output_path
        self.segments        = segments
        self.style           = style
        self.total_duration  = total_duration
        self._cancelled      = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._burn()
        except Exception as e:
            self.error.emit(str(e))

    def _burn(self):
        if not self.segments:
            self.error.emit("No subtitle segments to burn in.")
            return

        import tempfile, os

        s = self.style

        # --- Write a temporary ASS file ---
        # ASS gives us full style control (font, size, colour, outline, position)
        # and avoids all the filtergraph escaping hell of drawtext.
        ass_path = self._write_ass(s)
        if not ass_path:
            return
        try:
            self._run_burn_with_ass(ass_path)
        finally:
            try:
                os.unlink(ass_path)
            except OSError:
                pass

    def _probe_resolution(self) -> tuple:
        """Return (width, height) of the input video, defaulting to 1920x1080."""
        try:
            import json
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-select_streams", "v:0", self.input_path],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            stream = data["streams"][0]
            return int(stream["width"]), int(stream["height"])
        except Exception:
            return 1920, 1080

    def _write_ass(self, s) -> str:
        """Write an ASS subtitle file and return its path."""
        import tempfile

        # ASS alignment codes (numpad layout):
        # 1=BL 2=BC 3=BR  4=ML 5=MC 6=MR  7=TL 8=TC 9=TR
        _align_map = {
            "Bottom Left":    1,
            "Bottom Centre":  2,
            "Bottom Right":   3,
            "Centre":         5,
            "Top Left":       7,
            "Top Centre":     8,
            "Top Right":      9,
        }
        alignment = _align_map.get(s.position, 2)

        # Colours in ASS are &HAABBGGRR (alpha, blue, green, red)
        def _ass_colour(rgba, alpha_override=None):
            r, g, b, a = rgba
            aa = alpha_override if alpha_override is not None else (255 - a)
            return f"&H{aa:02X}{b:02X}{g:02X}{r:02X}"

        primary   = _ass_colour(s.text_color)
        outline_c = _ass_colour(s.outline_color)
        back_c    = _ass_colour(s.bg_color) if s.bg_enabled else "&H80000000"
        bold_val  = -1 if s.font_weight == "Bold" else 0
        outline_w = s.outline_width
        shadow    = 0
        border    = 3 if s.bg_enabled else 1   # 1=outline, 3=opaque box

        margin_v  = s.margin
        margin_h  = s.margin

        play_w, play_h = self._probe_resolution()

        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n"
            "YCbCr Matrix: None\n"
            f"PlayResX: {play_w}\n"
            f"PlayResY: {play_h}\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{s.font_family},{s.font_size},"
            f"{primary},&H000000FF,{outline_c},{back_c},"
            f"{bold_val},0,0,0,"
            f"100,100,0,0,{border},{outline_w},{shadow},"
            f"{alignment},{margin_h},{margin_h},{margin_v},1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        def _tc(s_sec):
            h  = int(s_sec // 3600)
            m  = int((s_sec % 3600) // 60)
            sc = s_sec % 60
            cs = int((sc % 1) * 100)
            return f"{h}:{m:02d}:{int(sc):02d}.{cs:02d}"

        events = []
        for seg in self.segments:
            text = seg.text.strip().replace("\n", " ").replace("\n", "\\N")
            events.append(
                f"Dialogue: 0,{_tc(seg.start)},{_tc(seg.end)},Default,,0,0,0,,{text}"
            )

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".ass", delete=False, encoding="utf-8")
        tmp.write(header + "\n".join(events))
        tmp.close()
        return tmp.name

    def _run_burn_with_ass(self, ass_path: str):
        """Run FFmpeg with the ASS subtitle filter."""
        # Escape the ass path for FFmpeg filter: backslashes and colons
        safe_ass = ass_path.replace("\\", "/").replace(":", r"\:")

        cmd = [
            FFMPEG, "-y",
            "-i", self.input_path,
            "-vf", f"ass={safe_ass}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            self.output_path,
        ]

        self.log.emit(f"Burning {len(self.segments)} subtitle segment(s) via ASS filter...")
        self._run_ffmpeg_burn(cmd)

    def _run_ffmpeg_burn(self, cmd):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        dur = self.total_duration
        for line in process.stdout:
            if self._cancelled:
                process.terminate()
                process.wait()   # ensure process is fully dead before cleanup
                # Remove the partial output file — FFmpeg will have written
                # an incomplete/corrupt file that would confuse the user
                try:
                    if os.path.exists(self.output_path):
                        os.unlink(self.output_path)
                except OSError:
                    pass
                self.error.emit("Subtitle burn cancelled.")
                return
            line = line.strip()
            self.log.emit(line)
            if line.startswith("out_time_ms=") and dur > 0:
                try:
                    t = int(line.split("=")[1]) / 1_000_000
                    self.progress.emit(min(t / dur, 1.0))
                except ValueError:
                    pass

        process.wait()
        if process.returncode == 0:
            self.progress.emit(1.0)
            self.finished.emit(self.output_path)
        else:
            self.error.emit(
                f"FFmpeg subtitle burn failed (code {process.returncode}). "
                "Check log for details."
            )

# ---------------------------------------------------------------------------
# check_ffmpeg_available
# ---------------------------------------------------------------------------

def check_ffmpeg_available() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [FFMPEG, "-version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            first_line = result.stdout.splitlines()[0] if result.stdout else "ffmpeg found"
            return True, first_line
        return False, "ffmpeg returned non-zero"
    except FileNotFoundError:
        return False, "ffmpeg not found — install it and ensure it is on your PATH"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"