#!/usr/bin/env bash
# Report-only: which toolchains can the New Project wizard use?
for tool in php composer node npm cargo go cmake git; do
    if command -v "$tool" >/dev/null 2>&1; then echo "  ✓ $tool"
    else echo "  - $tool (not installed)"; fi
done
exit 0
