#!/bin/bash
# Compile the face tracker (macOS only: it uses Apple's Vision framework, so nothing is downloaded).
#   bash build_facetrack.sh            -> ./facetrack
#   ./facetrack VIDEO OUT.json [fps=10]   -> face boxes over time, normalised, origin top-left
set -euo pipefail
cd "$(dirname "$0")"
command -v swiftc >/dev/null || { echo "swiftc not found: install the Xcode command line tools (xcode-select --install)"; exit 1; }
swiftc -O -swift-version 5 facetrack.swift -o facetrack
echo "built $(pwd)/facetrack"
