"""
DownloadWorker — Downloads media from URLs using yt-dlp.

Supports YouTube, Kick, TikTok, Twitter/X, Twitch clips,
Instagram, Vimeo, and 1000+ other platforms.

Runs entirely in a QThread — never blocks the UI.
"""

import subprocess
import json
import os
import re
import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


# ---------------------------------------------------------------------------
# yt-dlp discovery
# ---------------------------------------------------------------------------

def _find_ytdlp() -> str | None:
    """Return path to yt-dlp binary or None if not found."""
    for candidate in ["yt-dlp", "yt_dlp", "/usr/bin/yt-dlp",
                       "/usr/local/bin/yt-dlp"]:
        if shutil.which(candidate):
            return candidate
    return None


def check_ytdlp_available() -> tuple[bool, str]:
    """Return (available, message)."""
    binary = _find_ytdlp()
    if not binary:
        return False, (
            "yt-dlp not found.\n\n"
            "Install it with:\n"
            "  pip install yt-dlp\n"
            "or:\n"
            "  sudo apt install yt-dlp"
        )
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            ver = result.stdout.strip()
            return True, f"yt-dlp {ver}"
        return False, "yt-dlp found but returned an error"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# MetadataWorker — fetch title / thumbnail / duration before downloading
# ---------------------------------------------------------------------------

class MetadataWorker(QThread):
    """
    Fetch video metadata from a URL without downloading.

    Signals
    -------
    finished(dict)   keys: title, duration, thumbnail_url, platform, url
    error(str)
    """

    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url.strip()

    def run(self):
        binary = _find_ytdlp()
        if not binary:
            self.error.emit("yt-dlp not found. Install with: pip install yt-dlp")
            return
        try:
            cmd = [
                binary,
                "--dump-json",
                "--no-download",
                "--no-playlist",
                self.url,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                err = result.stderr.strip()
                self.error.emit(f"Could not fetch metadata:\n{err[-500:]}")
                return

            data = json.loads(result.stdout.splitlines()[0])

            duration = data.get("duration") or 0
            meta = {
                "title":         data.get("title", "Unknown"),
                "duration":      float(duration),
                "thumbnail_url": data.get("thumbnail", ""),
                "platform":      data.get("extractor_key", "Unknown"),
                "uploader":      data.get("uploader", ""),
                "view_count":    data.get("view_count", 0),
                "url":           self.url,
                "ext":           data.get("ext", "mp4"),
                "formats":       _summarise_formats(data.get("formats", [])),
            }
            self.finished.emit(meta)

        except json.JSONDecodeError:
            self.error.emit("Could not parse metadata response.")
        except subprocess.TimeoutExpired:
            self.error.emit("Metadata fetch timed out (30s).")
        except Exception as e:
            self.error.emit(str(e))


def _summarise_formats(formats: list) -> list[dict]:
    """Return a clean list of available quality options."""
    seen   = set()
    result = []
    for f in reversed(formats):   # best quality last → iterate reversed
        height = f.get("height")
        vcodec = f.get("vcodec", "none")
        if not height or vcodec == "none":
            continue
        label = f"{height}p"
        if label not in seen:
            seen.add(label)
            result.append({
                "label":     label,
                "height":    height,
                "format_id": f.get("format_id", ""),
                "ext":       f.get("ext", "mp4"),
                "filesize":  f.get("filesize") or f.get("filesize_approx") or 0,
            })
    # Sort descending by height
    result.sort(key=lambda x: x["height"], reverse=True)
    # Add "Best available" at top
    result.insert(0, {"label": "Best available (h264)", "height": 9999,
                       "format_id": "bestvideo+bestaudio/best", "ext": "mp4",
                       "filesize": 0})
    return result


# ---------------------------------------------------------------------------
# DownloadWorker — the actual download
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    """
    Download a URL to a local file using yt-dlp.

    Signals
    -------
    progress(float, str)   0.0–1.0, human-readable speed/ETA string
    finished(str)          local file path on success
    error(str)
    log(str)               raw yt-dlp output line
    """

    progress = pyqtSignal(float, str)   # (pct, status_text)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)
    log      = pyqtSignal(str)

    def __init__(self, url: str, output_dir: str,
                 format_id: str = "bestvideo+bestaudio/best",
                 parent=None):
        super().__init__(parent)
        self.url        = url.strip()
        self.output_dir = output_dir
        self.format_id  = format_id
        self._cancelled = False
        self._process   = None

    def cancel(self):
        self._cancelled = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def run(self):
        binary = _find_ytdlp()
        if not binary:
            self.error.emit("yt-dlp not found. Install with: pip install yt-dlp")
            return

        out_template = os.path.join(self.output_dir, "%(title)s.%(ext)s")

        # Ensure video-only format IDs always include audio stream.
        # Prefer h264+aac for maximum compatibility with QMediaPlayer.
        # av1+opus (YouTube Shorts default) won't play in Qt on most Linux systems.
        format_id = self.format_id
        if format_id in ("bestvideo+bestaudio/best", "best"):
            # Override with h264-preferring format string
            format_id = (
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]"
                "/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            )
        elif "+" not in format_id:
            format_id = f"{format_id}+bestaudio[acodec^=mp4a]/bestaudio"

        cmd = [
            binary,
            "--format",              format_id,
            "--merge-output-format", "mp4",
            "--output",              out_template,
            "--print",               "after_move:filepath",
            "--newline",
            "--no-playlist",
            "--no-part",
            "--progress",
            # Always re-encode to h264+aac so Qt can play regardless of source codec.
            # YouTube Shorts use AV1+Opus which Qt multimedia cannot decode on Linux.
            "--postprocessor-args",  "ffmpeg:-c:v libx264 -crf 23 -preset fast -c:a aac -b:a 192k",
            "--recode-video",        "mp4",
            self.url,
        ]

        self.log.emit(f"yt-dlp command: {' '.join(cmd)}\n")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            output_path  = None
            merger_path  = None   # path from [Merger] line (before file exists)

            for line in self._process.stdout:
                if self._cancelled:
                    break

                line = line.rstrip()
                self.log.emit(line)

                # Progress reporting
                pct, status = _parse_progress_line(line)
                if pct is not None:
                    self.progress.emit(pct, status)

                # --print after_move:filepath outputs the FINAL merged file path
                # as a bare line (no prefix). Detect it: absolute path to .mp4
                if line.startswith("/") and line.endswith(".mp4") and not line.startswith("["):
                    output_path = line.strip()
                    continue

                # [Merger] line — store path even though file doesn't exist yet
                m = _MERGER_RE.search(line)
                if m:
                    merger_path = m.group(1).strip().strip('"')
                    self.progress.emit(0.95, "Merging video + audio…")
                    continue

                # [download] Destination — intermediate or single-stream file
                path = _extract_output_path(line)
                if path and path.endswith(".mp4"):
                    output_path = path

            self._process.wait()

            if self._cancelled:
                self.error.emit("Download cancelled.")
                return

            if self._process.returncode == 0:
                # Resolution order:
                # 1. --print after_move:filepath (most reliable — post-merge absolute path)
                # 2. [Merger] line path (exists now that merge is done)
                # 3. _find_latest_mp4 fallback
                if not output_path or not os.path.exists(output_path):
                    if merger_path and os.path.exists(merger_path):
                        output_path = merger_path
                if not output_path or not os.path.exists(output_path):
                    output_path = _find_latest_mp4(self.output_dir)

                if output_path and os.path.exists(output_path):
                    self.progress.emit(1.0, "Complete")
                    self.finished.emit(output_path)
                else:
                    self.error.emit(
                        "Download completed but output file could not be located.\n"
                        f"Check your download directory: {self.output_dir}"
                    )
            else:
                self.error.emit(
                    f"yt-dlp exited with code {self._process.returncode}.\n"
                    "Check the log for details."
                )

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._process = None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_PROGRESS_RE = re.compile(
    r"\[download\]\s+([\d.]+)%\s+of\s+([\d.]+\w+)\s+at\s+([\S]+)\s+ETA\s+([\S]+)"
)
_DEST_RE     = re.compile(r"\[download\] Destination: (.+)")
_MERGER_RE   = re.compile(r'\[Merger\] Merging formats into "(.+)"')
_ALREADY_RE  = re.compile(r"\[download\] (.+) has already been downloaded")


def _parse_progress_line(line: str) -> tuple[float | None, str]:
    m = _PROGRESS_RE.search(line)
    if m:
        pct    = float(m.group(1)) / 100.0
        size   = m.group(2)
        speed  = m.group(3)
        eta    = m.group(4)
        status = f"{m.group(1)}%  •  {size}  •  {speed}/s  •  ETA {eta}"
        return pct, status
    if "[download] 100%" in line:
        return 1.0, "Finalising…"
    return None, ""


def _extract_output_path(line: str) -> str | None:
    for pattern in (_DEST_RE, _MERGER_RE, _ALREADY_RE):
        m = pattern.search(line)
        if m:
            p = m.group(1).strip().strip('"')
            if os.path.exists(p):
                return p
    return None


def _find_latest_mp4(directory: str) -> str | None:
    """Fallback: find the most recently modified mp4 in a directory."""
    try:
        mp4s = list(Path(directory).glob("*.mp4"))
        if not mp4s:
            mp4s = list(Path(directory).glob("*.mkv")) + list(Path(directory).glob("*.webm"))
        if mp4s:
            return str(max(mp4s, key=lambda p: p.stat().st_mtime))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Platform detection (for display in UI)
# ---------------------------------------------------------------------------

PLATFORM_ICONS = {
    "youtube":   "▶",
    "kick":      "🟢",
    "twitch":    "🟣",
    "tiktok":    "🎵",
    "twitter":   "✖",
    "instagram": "📷",
    "vimeo":     "🎬",
    "reddit":    "🔴",
}


def platform_icon(platform: str) -> str:
    key = platform.lower()
    for k, icon in PLATFORM_ICONS.items():
        if k in key:
            return icon
    return "🌐"


def platform_colour(platform: str) -> str:
    key = platform.lower()
    colours = {
        "youtube":   "#FF0000",
        "kick":      "#53FC18",
        "twitch":    "#9146FF",
        "tiktok":    "#FF0050",
        "twitter":   "#1DA1F2",
        "instagram": "#E1306C",
        "vimeo":     "#1AB7EA",
    }
    for k, colour in colours.items():
        if k in key:
            return colour
    return "#4A90D9"