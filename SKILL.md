---
name: record-demo
description: Create an automated product demo recording, browser walkthrough, or synchronized narration video with Playwright and Qwen3-TTS voice cloning.
---

# Automated Product Demo Recording

Create a short product demo video with a real browser recording, synchronized narration cloned from a local reference voice, and a verified MP4 output.

## Runtime

The skill bundles the runtime files used by the workflow:

- `assets/reference_voice.wav`: a local reference voice input that is ignored by Git.
- `scripts/voice_clone.py`: Qwen3-TTS MLX and PyTorch cue synthesis.
- `scripts/run_demo_template.js`: Playwright recorder template.
- `scripts/mux.sh`: FFmpeg audio/video muxer.
- `scripts/setup_env.sh`: backend-aware environment setup.
- `requirements-mlx.txt`: Apple Silicon MLX dependencies.
- `requirements-pytorch.txt`: CUDA or CPU PyTorch dependencies.
- `package.json` and `package-lock.json`: recorder dependencies.

Use `${CLAUDE_SKILL_DIR}` for every path to a bundled file so the skill works when installed at the user, project, or plugin level.

## Protocol

1. Inspect the target web application and draft discrete scene cues.
2. Create `./output/cues.json` as a JSON array of `{ "id": "cue_01", "text": "..." }` objects.
3. Confirm `ffmpeg`, `node`, and `npm` are available. Run the backend-aware bootstrap once after installing or updating the skill:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/setup_env.sh"
```

4. Use the local reference voice sample with Qwen3-TTS. On Apple Silicon, the bootstrap creates `.venv-mlx` and the default 0.6B MLX backend is the fast path:

```bash
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  PYTHON="${CLAUDE_SKILL_DIR}/.venv-mlx/bin/python"
  BACKEND_ARGS=(--backend mlx)
else
  PYTHON="${CLAUDE_SKILL_DIR}/.venv/bin/python"
  BACKEND_ARGS=(--backend pytorch)
fi
REF_AUDIO="${CLAUDE_SKILL_DIR}/assets/reference_voice.wav"
"$PYTHON" "${CLAUDE_SKILL_DIR}/scripts/voice_clone.py" \
  --cues ./output/cues.json \
  --ref-audio "$REF_AUDIO" \
  "${BACKEND_ARGS[@]}" \
  --model-size 0.6B
```

The MLX 0.6B path uses Qwen's x-vector voice-clone prompt and does not require a reference transcript. The PyTorch path requires `--ref-transcript` with the exact words spoken in the WAV. Use `1.7B` only with a compatible CUDA/MLX setup and sufficient memory.

5. Copy the recorder template to the target repository's output directory and replace `runProductWorkflow` with the target product's navigation, selectors, authentication, and click actions:

```bash
mkdir -p ./output
cp "${CLAUDE_SKILL_DIR}/scripts/run_demo_template.js" ./output/run_demo.js
```

6. Start or open the target application and set `DEMO_URL` plus any authentication variables required by the workflow.
7. Install the target repository's Node dependencies if the generated recorder is run from that repository. The skill's `setup_env.sh` installs its recorder dependencies in `${CLAUDE_SKILL_DIR}/node_modules`; when the generated script is copied into another repository, use that repository's dependencies or set `NODE_PATH="${CLAUDE_SKILL_DIR}/node_modules"`.
8. Run the recorder:

```bash
node ./output/run_demo.js
```

9. Mux the audio and recording:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/mux.sh" ./output/audio ./output/recordings ./output/final_demo.mp4
```

10. Verify that the final MP4 exists, is non-empty, contains H.264 video and AAC audio, and has approximately the narration duration:

```bash
test -s ./output/final_demo.mp4
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height \
  -of default=noprint_wrappers=1 ./output/final_demo.mp4
```

## Requirements

- Python 3.11 or newer with `venv` support.
- FFmpeg available in `$PATH`.
- Node.js and npm available in `$PATH`.
- Approximately 3 GB of free disk space for the default Qwen 0.6B model and its isolated environment.
- A clean 5–12 second reference WAV. The exact transcript is required only for the PyTorch backend.
- Target URL, test credentials, and authentication instructions when the target is not public.

## Troubleshooting

- `externally-managed-environment`: use `setup_env.sh`; do not install into the system Python.
- MLX and PyTorch dependency conflict: keep `.venv-mlx` and `.venv` separate; do not install both backends in one environment.
- `ref_text is required`: use the PyTorch backend with `--ref-transcript`, or use the MLX 0.6B x-vector path.
- CUDA unavailable: use MLX on Apple Silicon; do not use slow CPU PyTorch generation on a Mac.
- Qwen model download or memory failure: confirm free disk space, remove unused local model caches, and retry the 0.6B model.
- Playwright module missing: run the skill bootstrap and set `NODE_PATH="${CLAUDE_SKILL_DIR}/node_modules"` when running from a target repository.
- Missing target selectors: inspect the running target with browser tools and replace the template workflow before recording.
- Final duration mismatch: compare the master narration and final MP4 with `ffprobe`; the audio track is intentionally the shorter source and muxing uses `-shortest`.

## Execution Notes

- Audio durations are generated before recording and read from `output/timing_manifest.json`.
- The Playwright template uses smooth target scrolling and a click ripple; it does not transform or zoom the page body, which keeps long pages and nested scroll containers stable.
- `mux.sh` uses the pointer file when present and otherwise selects the newest WebM recording.
- Generated files belong under `output/` and should not be committed.
- After changing this skill, restart Claude Code so the updated skill is loaded.
