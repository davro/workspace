"""
WhisperWorker — QThread wrapper around faster-whisper transcription.

Usage
-----
    worker = WhisperWorker(
        source_path = "/path/to/video.mp4",
        model_size  = "base",          # tiny | base | small | medium | large-v3
        language    = None,            # None = auto-detect
        parent      = self,
    )
    worker.segment_ready.connect(self._on_segment)   # fired per segment
    worker.progress.connect(self._on_progress)       # 0.0–1.0
    worker.finished.connect(self._on_finished)       # list[TranscriptSegment]
    worker.error.connect(self._on_error)             # human-readable string
    worker.start()
    self._workers.append(worker)   # REQUIRED — prevent GC

Model sizes (speed ↔ accuracy trade-off)
-----------------------------------------
    tiny      ~39M  — fastest, least accurate
    base      ~74M  — good balance for most use cases
    small     ~244M
    medium    ~769M
    large-v3  ~1550M — most accurate, slowest
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class TranscriptSegment:
    """One recognised phrase returned by Whisper."""
    start:  float           # seconds in the SOURCE file
    end:    float           # seconds in the SOURCE file
    text:   str
    words:  list = field(default_factory=list)  # word-level if available

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_srt_block(self, index: int) -> str:
        return (
            f"{index}\n"
            f"{_fmt_srt(self.start)} --> {_fmt_srt(self.end)}\n"
            f"{self.text.strip()}\n"
        )

    def to_vtt_block(self) -> str:
        return (
            f"{_fmt_vtt(self.start)} --> {_fmt_vtt(self.end)}\n"
            f"{self.text.strip()}\n"
        )


def _fmt_srt(s: float) -> str:
    h  = int(s // 3600)
    m  = int((s % 3600) // 60)
    sc = s % 60
    ms = int((sc % 1) * 1000)
    return f"{h:02d}:{m:02d}:{int(sc):02d},{ms:03d}"


def _fmt_vtt(s: float) -> str:
    h  = int(s // 3600)
    m  = int((s % 3600) // 60)
    sc = s % 60
    ms = int((sc % 1) * 1000)
    return f"{h:02d}:{m:02d}:{int(sc):02d}.{ms:03d}"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class WhisperWorker(QThread):
    """
    Runs faster-whisper in a background QThread.

    Signals
    -------
    segment_ready(start, end, text)  — emitted after each recognised segment
    progress(float)                  — 0.0–1.0
    finished(list)                   — list[TranscriptSegment] on completion
    error(str)                       — human-readable message on failure
    """

    segment_ready = pyqtSignal(float, float, str)
    progress      = pyqtSignal(float)
    finished      = pyqtSignal(list)
    error         = pyqtSignal(str)

    def __init__(
        self,
        source_path:     str,
        model_size:      str   = "base",
        language:        Optional[str] = None,
        device:          str   = "cpu",
        compute_type:    str   = "int8",
        source_duration: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.source_path      = source_path
        self.model_size       = model_size if model_size in MODEL_SIZES else "base"
        self.language         = language
        self.device           = device
        self.compute_type     = compute_type
        self.source_duration  = source_duration
        self._cancelled       = False

    def cancel(self):
        """Request cancellation.  finished() is NOT emitted after cancel()."""
        self._cancelled = True

    # -------------------------------------------------------------------------

    def run(self):
        try:
            self._run()
        except Exception as exc:
            self.error.emit(str(exc))

    def _run(self):
        # --- Import check ---
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            self.error.emit(
                "faster-whisper is not installed.\n\n"
                "Install it with:\n  pip install faster-whisper"
            )
            return

        # --- Audio extraction if source is video ---
        audio_path, is_temp = self._prepare_audio(self.source_path)
        if audio_path is None:
            return  # error already emitted

        try:
            # --- Load model ---
            model = WhisperModel(
                self.model_size,
                device       = self.device,
                compute_type = self.compute_type,
            )

            # --- Transcribe ---
            # VAD (Voice Activity Detection) can silently drop ALL segments on
            # short clips, music, or singing because it classifies them as non-speech.
            # We disable it so Whisper processes the full audio unconditionally.
            # For longer files with long silences users can re-enable via self.vad_filter.
            use_vad = getattr(self, "vad_filter", False)
            transcribe_kwargs = dict(
                language        = self.language,
                beam_size       = 5,
                word_timestamps = False,
                vad_filter      = use_vad,
                condition_on_previous_text = False,
                temperature     = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),  # fallback on low confidence
            )
            if use_vad:
                transcribe_kwargs["vad_parameters"] = dict(
                    min_silence_duration_ms = 300,
                    speech_pad_ms           = 200,
                    threshold               = 0.3,   # lower = more sensitive
                )
            segments, info = model.transcribe(audio_path, **transcribe_kwargs)

            dur = self.source_duration if self.source_duration > 0 else info.duration
            results: list[TranscriptSegment] = []

            for seg in segments:
                if self._cancelled:
                    return

                ts = TranscriptSegment(start=seg.start, end=seg.end, text=seg.text)
                results.append(ts)
                self.segment_ready.emit(seg.start, seg.end, seg.text)

                if dur > 0:
                    self.progress.emit(min(seg.end / dur, 1.0))

            if not self._cancelled:
                self.progress.emit(1.0)
                self.finished.emit(results)

        finally:
            if is_temp and audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except OSError:
                    pass

    # -------------------------------------------------------------------------
    # Audio preparation
    # -------------------------------------------------------------------------

    def _prepare_audio(self, path: str) -> tuple[Optional[str], bool]:
        """
        Return (audio_path, is_temp).

        Audio-only files are passed directly to Whisper.
        Video files have audio extracted to a 16 kHz mono WAV temp file.
        Returns (None, False) on error — error signal is already emitted.
        """
        ext = os.path.splitext(path)[1].lower()
        audio_exts = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg", ".opus"}
        if ext in audio_exts:
            return path, False

        # Video → extract audio with ffmpeg
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        tmp_path = tmp.name

        cmd = [
            "ffmpeg", "-y",
            "-i", path,
            "-vn",
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            tmp_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace").strip()
                self.error.emit(f"FFmpeg audio extraction failed:\n{err}")
                os.unlink(tmp_path)
                return None, False
        except FileNotFoundError:
            self.error.emit("FFmpeg not found. Install FFmpeg and add it to PATH.")
            os.unlink(tmp_path)
            return None, False
        except subprocess.TimeoutExpired:
            self.error.emit("FFmpeg audio extraction timed out.")
            os.unlink(tmp_path)
            return None, False

        return tmp_path, True