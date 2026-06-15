# Timbre Shift

Timbre Shift is an experimental voice-cloning and song voice-conversion project.
The goal is to turn a source song vocal into a target vocal timbre, using only
voice data that is owned by, licensed to, or explicitly consented by the speaker.

## Project Layout

- `data/raw`: original audio files before processing
- `data/processed`: cleaned and segmented training audio
- `data/reference_voice`: short reference clips for the target voice
- `data/songs`: source songs or separated vocal stems
- `models/pretrained`: downloaded base models
- `models/checkpoints`: local training checkpoints
- `src/timbre_shift`: application and library code
- `scripts`: command-line utilities for preprocessing, training, and conversion
- `configs`: model, dataset, and pipeline configuration files
- `notebooks`: exploration and experiments
- `experiments`: experiment notes and run metadata
- `outputs`: generated converted vocals and demos
- `logs`: runtime logs
- `docs`: design notes and project documentation
- `tests`: automated tests

For the current Python module responsibilities, see `docs/architecture.md`.

## First Milestones

1. Prepare legal target voice samples.
2. Separate vocals from a source song.
3. Build audio preprocessing scripts.
4. Pick a voice conversion model family.
5. Add an inference pipeline for song conversion.

## Local Demo Pipeline

The first implementation is a lightweight Python CLI that orchestrates external
audio tools:

- `ffmpeg` for audio normalization and final mixing
- `demucs` for vocal/backing separation
- `Seed-VC` for zero-shot singing voice conversion
- `RVC-MLX` as an experimental trained-model backend

Install the local package after creating a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Check your local environment:

```bash
timbre-shift check --seed-vc-dir vendor/seed-vc
timbre-shift check-mps
timbre-shift engines list
timbre-shift rvc-mlx check
```

Start the local upload page:

```bash
timbre-shift web --seed-vc-dir vendor/seed-vc
```

Run the demo after installing `ffmpeg`, `demucs`, and Seed-VC separately:

```bash
timbre-shift demo \
  --voice data/reference_voice/my_ref.wav \
  --song data/songs/song.wav \
  --seed-vc-dir vendor/seed-vc
```

The final mix is written to `outputs/final.wav`. The web app also writes
`outputs/web/final.mp3` and `outputs/web/metrics.json`.

## Conversion Engines

Timbre Shift keeps Seed-VC as the stable default and adds RVC-MLX as an
experimental backend.

Seed-VC:

- zero-shot conversion
- uses short reference clips such as 8, 16, 20, or 25 seconds
- does not require training
- best for quick previews and the current stable workflow

RVC-MLX:

- experimental Apple Silicon backend
- requires a trained voice model
- intended for one voice profile with multiple clean samples
- useful when one voice will be reused across many songs
- not guaranteed to sound better than Seed-VC; benchmark and listening tests are required

Recommended RVC-MLX training material:

- minimum 5 minutes of clean vocal for testing
- 10 minutes or more is recommended
- 10 to 30 minutes is usually more stable
- cover low, mid, high notes, soft singing, strong singing, fast phrases, and long notes
- avoid backing music, reverb, harmonies, and heavy compression when possible

Current RVC-MLX status: the project has engine detection, dataset preparation,
model records, cache-key helpers, and wrapper entry points. The actual training
and inference command is intentionally left adapter-driven because community
RVC-MLX implementations differ. Configure a concrete implementation with
`RVC_MLX_COMMAND` or `RVC_MLX_REPO` before using the engine.

RVC-MLX commands:

```bash
timbre-shift rvc-mlx check
timbre-shift rvc-mlx prepare-dataset --voice-id voice_xxx
timbre-shift rvc-mlx train --voice-id voice_xxx
timbre-shift rvc-mlx convert --voice-id voice_xxx --source-vocal vocals.wav --output outputs/rvc.wav
```

## M2 Max Modes

The web page defaults to `m2max_hq_30`, which uses Apple Silicon MPS, a short
target voice reference, Seed-VC cache, MP3 export, and vocal-segment compaction.

- `preview_auto_15_m2max`: 15 second preview, fastest way to check timbre.
- `m2max_hq_30`: default full-song mode, balanced speed and quality.
- `m2max_hq_plus`: higher quality full-song mode.
- `m2max_offline_max`: slowest offline mode for best quality.

If the uploaded source is already clean vocals, choose "干净人声：跳过分离" on
the page. This skips Demucs and can save a large part of the run time.

`outputs/web/metrics.json` records the time spent in preparation, Demucs,
Seed-VC, timeline restore, mixing, MP3 export, cache hits, active vocal seconds,
RTF, and whether MPS was actually used.

On recent `torchaudio` versions, Demucs also needs `torchcodec` to save stems:

```bash
python -m pip install demucs torchcodec
```
