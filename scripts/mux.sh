#!/usr/bin/env bash
set -euo pipefail

AUDIO_DIR="${1:-./output/audio}"
RECORDINGS_DIR="${2:-./output/recordings}"
FINAL_OUTPUT="${3:-./output/final_demo.mp4}"
CONCAT_FILE="$AUDIO_DIR/audio_list.txt"
MASTER_AUDIO="$AUDIO_DIR/master_narration.wav"
POINTER_FILE="$RECORDINGS_DIR/latest_recording.txt"

mkdir -p "$(dirname "$MASTER_AUDIO")" "$(dirname "$FINAL_OUTPUT")"

if [[ ! -f "$CONCAT_FILE" ]]; then
  printf 'Error: Missing %s\n' "$CONCAT_FILE" >&2
  exit 1
fi

printf '==> Step 1: Concatenating audio tracks\n'
ffmpeg -f concat -safe 0 -i "$CONCAT_FILE" -c copy "$MASTER_AUDIO" -y

printf '==> Step 2: Locating screen recording\n'
LATEST_VIDEO=""
if [[ -f "$POINTER_FILE" ]]; then
  IFS= read -r RECORDING_PATH < "$POINTER_FILE" || true
  if [[ -n "${RECORDING_PATH:-}" ]]; then
    if [[ "$RECORDING_PATH" != /* ]]; then
      RECORDING_PATH="$RECORDINGS_DIR/$RECORDING_PATH"
    fi
    if [[ -f "$RECORDING_PATH" ]]; then
      LATEST_VIDEO="$RECORDING_PATH"
    fi
  fi
fi
if [[ -z "$LATEST_VIDEO" ]]; then
  LATEST_VIDEO=$(ls -t "$RECORDINGS_DIR"/*.webm 2>/dev/null | head -n 1 || true)
fi
if [[ -z "$LATEST_VIDEO" || ! -f "$LATEST_VIDEO" ]]; then
  printf 'Error: No recordings found in %s\n' "$RECORDINGS_DIR" >&2
  exit 1
fi
printf 'Using video source: %s\n' "$LATEST_VIDEO"

printf '==> Step 3: Muxing audio and video\n'
ffmpeg -i "$LATEST_VIDEO" -i "$MASTER_AUDIO" \
  -c:v libx264 -preset medium -crf 20 \
  -c:a aac -b:a 192k \
  -pix_fmt yuv420p \
  -shortest \
  "$FINAL_OUTPUT" -y

if [[ ! -s "$FINAL_OUTPUT" ]]; then
  printf 'Error: Final output was not created or is empty: %s\n' "$FINAL_OUTPUT" >&2
  exit 1
fi
printf '==> Pipeline complete: %s\n' "$FINAL_OUTPUT"
