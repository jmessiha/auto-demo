# Skill: Automated Product Demo Recording

## Context
Use this skill when asked to create a recorded product demo, walkthrough video, or certification demonstration.

## Protocol
1. Inspect the target web application and draft an array of discrete scene cues.
2. Write the cues to `./output/cues.json` as `[{"id":"cue_01","text":"..."}]`.
3. Confirm `assets/reference_voice.wav` is a clean 5–10 second WAV sample.
4. Run `python3 scripts/voice_clone.py --cues ./output/cues.json --ref-audio ./assets/reference_voice.wav`.
5. Copy `scripts/run_demo_template.js` to `./output/run_demo.js` and replace `runProductWorkflow` with the actual product navigation, selectors, authentication, and click actions.
6. Add `await page.waitForTimeout(waitDuration(timings, "cue_xx"));` after every action whose narration should finish before the next action. Keep cue order consistent with `cues.json`.
7. Set `DEMO_URL` and any required authentication environment variables.
8. Run `node ./output/run_demo.js`.
9. Run `bash scripts/mux.sh ./output/audio ./output/recordings ./output/final_demo.mp4`.
10. Verify that FFmpeg exits successfully, the final MP4 exists and is non-empty, and the video duration matches the narration.

## Requirements
- NVIDIA GPU with 8 GB VRAM for the 1.7B model or 4 GB for the 0.6B model.
- FFmpeg available in `$PATH`.
- Python dependencies from `requirements.txt`.
- Node dependencies from `package.json`.
- Reference voice, product URL, and test credentials available to the agent.

## Execution Notes
- Audio durations are generated before recording and are read from `output/timing_manifest.json`.
- The Playwright template records at 1920×1080 and writes the resulting WebM path to `output/recordings/latest_recording.txt`.
- `mux.sh` uses the pointer file when present and otherwise selects the newest WebM recording.
