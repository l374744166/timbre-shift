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

## First Milestones

1. Prepare legal target voice samples.
2. Separate vocals from a source song.
3. Build audio preprocessing scripts.
4. Pick a voice conversion model family.
5. Add an inference pipeline for song conversion.

