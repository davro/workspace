#!/usr/bin/env bash
for tool in yt-dlp ffmpeg; do
    command -v "$tool" >/dev/null 2>&1 || sudo apt-get install -y "$tool"
done
