#!/usr/bin/env python3
import argparse
import importlib.util
import json
import platform
from pathlib import Path

import numpy as np
import soundfile as sf


def parse_args():
    parser = argparse.ArgumentParser(description="Generate voice-cloned cues using Qwen3-TTS")
    parser.add_argument("--cues", required=True, help="Path to JSON file containing an array of {id, text}")
    parser.add_argument("--ref-audio", default="./assets/reference_voice.wav", help="Path to the reference WAV sample")
    parser.add_argument("--ref-transcript", default=None, help="Exact transcript for the PyTorch ICL prompt")
    parser.add_argument("--out-dir", default="./output/audio", help="Output directory for WAV files")
    parser.add_argument("--manifest-path", default="./output/timing_manifest.json", help="Timing manifest output path")
    parser.add_argument("--model-size", default="0.6B", choices=["0.6B", "1.7B"], help="Qwen3-TTS model size")
    parser.add_argument("--backend", default="auto", choices=["auto", "mlx", "pytorch"], help="Inference backend")
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


def validate_reference(ref_audio):
    if not ref_audio.is_file():
        raise FileNotFoundError(f"Reference audio not found: {ref_audio}")
    duration = float(sf.info(str(ref_audio)).duration)
    if duration < 5 or duration > 12:
        raise ValueError(f"Reference audio must be 5-12 seconds; got {duration:.2f}s")


def select_backend(requested):
    if requested != "auto":
        return requested
    apple_silicon = platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}
    if apple_silicon and importlib.util.find_spec("mlx_audio") is not None:
        return "mlx"
    return "pytorch"


def model_audio_result(result, output_file):
    waveform = result.audio
    if hasattr(waveform, "detach"):
        waveform = waveform.detach().cpu().numpy()
    waveform = np.asarray(waveform)
    sf.write(str(output_file), waveform, int(result.sample_rate))
    return float(len(waveform)) / float(result.sample_rate)


def synthesize_mlx(cues, ref_audio, out_dir, model_size):
    from mlx_audio.tts.utils import load_model

    model_id = f"mlx-community/Qwen3-TTS-12Hz-{model_size}-Base-bf16"
    print(f"Loading Qwen3-TTS MLX ({model_id})...")
    model = load_model(model_id)
    prompt_transcript = None
    if model_size != "0.6B":
        raise ValueError("MLX voice cloning currently supports the 0.6B Base model")
    print("Using the MLX x-vector prompt path for the 0.6B model.")
    manifest = {}
    audio_files = []
    for cue in cues:
        cue_id = str(cue["id"])
        text = str(cue["text"])
        print(f"Synthesizing [{cue_id}]: {text}")
        results = list(model.generate(text=text, ref_audio=str(ref_audio), ref_text=prompt_transcript, lang_code="en", max_tokens=4096, verbose=False))
        if not results:
            raise RuntimeError(f"MLX returned no audio for {cue_id}")
        output_file = out_dir / f"{cue_id}.wav"
        duration = model_audio_result(results[0], output_file)
        manifest[cue_id] = {"file": str(output_file), "duration_sec": duration, "text": text}
        audio_files.append(output_file)
    return manifest, audio_files


def select_torch_device():
    import torch

    if torch.cuda.is_available():
        return "cuda:0", torch.bfloat16
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def load_torch_model(model_name, device_map, dtype):
    from qwen_tts import Qwen3TTSModel

    try:
        return Qwen3TTSModel.from_pretrained(model_name, device_map=device_map, dtype=dtype)
    except Exception as error:
        if device_map == "cpu":
            raise
        print(f"Unable to load Qwen3-TTS on {device_map}; retrying on CPU: {error}")
        return Qwen3TTSModel.from_pretrained(model_name, device_map="cpu", dtype=torch.float32)


def synthesize_pytorch(cues, ref_audio, ref_transcript, out_dir, model_size):
    import torch

    if not ref_transcript:
        raise ValueError("--ref-transcript is required for the PyTorch backend")
    device_map, dtype = select_torch_device()
    model_name = f"Qwen/Qwen3-TTS-12Hz-{model_size}-Base"
    print(f"Loading Qwen3-TTS PyTorch ({model_name}) on {device_map}...")
    model = load_torch_model(model_name, device_map, dtype)
    prompt = model.create_voice_clone_prompt(ref_audio=str(ref_audio), ref_text=ref_transcript)
    manifest = {}
    audio_files = []
    for cue in cues:
        cue_id = str(cue["id"])
        text = str(cue["text"])
        print(f"Synthesizing [{cue_id}]: {text}")
        try:
            wavs, sample_rate = model.generate_voice_clone(text=[text], language=["English"], voice_clone_prompt=prompt)
        except Exception as error:
            if device_map == "cpu":
                raise
            print(f"Generation failed on {device_map}; retrying on CPU: {error}")
            device_map = "cpu"
            model = load_torch_model(model_name, device_map, torch.float32)
            prompt = model.create_voice_clone_prompt(ref_audio=str(ref_audio), ref_text=ref_transcript)
            wavs, sample_rate = model.generate_voice_clone(text=[text], language=["English"], voice_clone_prompt=prompt)
        waveform = wavs[0]
        if hasattr(waveform, "detach"):
            waveform = waveform.detach().cpu().numpy()
        output_file = out_dir / f"{cue_id}.wav"
        sf.write(str(output_file), waveform, sample_rate)
        duration = float(len(waveform)) / float(sample_rate)
        manifest[cue_id] = {"file": str(output_file), "duration_sec": duration, "text": text}
        audio_files.append(output_file)
    return manifest, audio_files


def main():
    args = parse_args()
    cues = load_cues(args.cues)
    ref_audio = Path(args.ref_audio).resolve()
    validate_reference(ref_audio)
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    backend = select_backend(args.backend)
    print(f"Selected backend: {backend}")
    if backend == "mlx":
        manifest, audio_files = synthesize_mlx(cues, ref_audio, out_dir, args.model_size)
    else:
        manifest, audio_files = synthesize_pytorch(cues, ref_audio, args.ref_transcript, out_dir, args.model_size)
    write_audio_list(out_dir / "audio_list.txt", audio_files)
    write_manifest(args.manifest_path, manifest)
    write_manifest(out_dir / "timing_manifest.json", manifest)
    print(f"Audio generation complete. Manifest: {Path(args.manifest_path).resolve()}")


if __name__ == "__main__":
    main()
