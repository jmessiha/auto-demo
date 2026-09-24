#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import soundfile as sf
import torch


def parse_args():
    parser = argparse.ArgumentParser(description="Generate voice-cloned cues using Qwen3-TTS")
    parser.add_argument("--cues", required=True, help="Path to JSON file containing an array of {id, text}")
    parser.add_argument("--ref-audio", required=True, help="Path to the reference .wav sample")
    parser.add_argument("--ref-transcript", default=None, help="Optional reference audio transcript")
    parser.add_argument("--out-dir", default="./output/audio", help="Output directory for WAV files")
    parser.add_argument("--manifest-path", default="./output/timing_manifest.json", help="Timing manifest output path")
    parser.add_argument(
        "--model-size",
        default="1.7B",
        choices=["0.6B", "1.7B"],
        help="Qwen3-TTS model variant",
    )
    return parser.parse_args()


def load_cues(path):
    with open(path, "r", encoding="utf-8") as handle:
        cues = json.load(handle)
    if not isinstance(cues, list) or not cues:
        raise ValueError("Cue file must contain a non-empty JSON array")
    seen = set()
    for cue in cues:
        if not isinstance(cue, dict) or not cue.get("id") or not cue.get("text"):
            raise ValueError("Every cue must contain non-empty id and text fields")
        if cue["id"] in seen:
            raise ValueError(f"Duplicate cue id: {cue['id']}")
        seen.add(cue["id"])
    return cues


def write_audio_list(path, files):
    with open(path, "w", encoding="utf-8") as handle:
        for file_path in files:
            escaped = str(file_path).replace("'", "'\\''")
            handle.write(f"file '{escaped}'\n")


def write_manifest(path, manifest):
    parent = Path(path).parent
    parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")


def main():
    args = parse_args()
    cues = load_cues(args.cues)
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading Qwen3-TTS ({args.model_size})...")
    from qwen_tts import Qwen3TTSModel

    use_cuda = torch.cuda.is_available()
    model_name = f"Qwen/Qwen3-TTS-12Hz-{args.model_size}-Base"
    model = Qwen3TTSModel.from_pretrained(
        model_name,
        device_map="cuda:0" if use_cuda else "cpu",
        dtype=torch.bfloat16 if use_cuda else torch.float32,
    )

    print("Creating speaker prompt embedding...")
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(Path(args.ref_audio).resolve()),
        ref_text=args.ref_transcript,
    )

    manifest = {}
    audio_files = []
    for cue in cues:
        cue_id = str(cue["id"])
        text = str(cue["text"])
        print(f"Synthesizing [{cue_id}]: {text}")
        wavs, sample_rate = model.generate_voice_clone(
            text=[text],
            language=["English"],
            voice_clone_prompt=prompt,
        )
        waveform = wavs[0]
        if hasattr(waveform, "detach"):
            waveform = waveform.detach().cpu().numpy()
        output_file = out_dir / f"{cue_id}.wav"
        sf.write(str(output_file), waveform, sample_rate)
        duration = float(len(waveform)) / float(sample_rate)
        manifest[cue_id] = {
            "file": str(output_file),
            "duration_sec": duration,
            "text": text,
        }
        audio_files.append(output_file)

    write_audio_list(out_dir / "audio_list.txt", audio_files)
    write_manifest(args.manifest_path, manifest)
    write_manifest(out_dir / "timing_manifest.json", manifest)
    print(f"Audio generation complete. Manifest: {Path(args.manifest_path).resolve()}")


if __name__ == "__main__":
    main()
