"""Command-line entrypoint for the local demo pipeline."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from .library import (
    archive_song,
    archive_voice_profile,
    init_library,
    list_songs,
    list_voice_profiles,
    save_song_to_library,
    save_voice_to_library,
)
from .pipeline import PRESETS, PipelineOptions, check_environment, run_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timbre-shift",
        description="Run the Timbre Shift local voice conversion demo.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Check local tool availability.")
    check.add_argument("--seed-vc-dir", default="vendor/seed-vc")

    subparsers.add_parser("check-mps", help="Check Apple Silicon MPS availability.")

    web = subparsers.add_parser("web", help="Start the local upload demo web app.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--seed-vc-dir", default="vendor/seed-vc")

    library = subparsers.add_parser("library", help="Manage the local library.")
    library_sub = library.add_subparsers(dest="library_command", required=True)
    library_sub.add_parser("init", help="Create the local SQLite library.")

    voices = subparsers.add_parser("voices", help="Manage saved voice profiles.")
    voices_sub = voices.add_subparsers(dest="voices_command", required=True)
    voices_sub.add_parser("list", help="List saved voice profiles.")
    voices_add = voices_sub.add_parser("add", help="Add a voice profile.")
    voices_add.add_argument("--audio", required=True)
    voices_add.add_argument("--name", required=True)
    voices_add.add_argument("--description", default=None)
    voices_add.add_argument("--rights", choices=["own_voice", "authorized_voice", "source_only", "unknown"], default="unknown")
    voices_add.add_argument("--allow-target", action="store_true")
    voices_delete = voices_sub.add_parser("delete", help="Archive a voice profile.")
    voices_delete.add_argument("--id", required=True)

    songs = subparsers.add_parser("songs", help="Manage saved songs.")
    songs_sub = songs.add_subparsers(dest="songs_command", required=True)
    songs_sub.add_parser("list", help="List saved songs.")
    songs_add = songs_sub.add_parser("add", help="Add a song.")
    songs_add.add_argument("--audio", required=True)
    songs_add.add_argument("--title", required=True)
    songs_add.add_argument("--artist", default=None)
    songs_add.add_argument("--source-kind", choices=["full_song", "clean_vocal"], default="full_song")
    songs_delete = songs_sub.add_parser("delete", help="Archive a song.")
    songs_delete.add_argument("--id", required=True)

    demo = subparsers.add_parser("demo", help="Run separation, conversion, and mixing.")
    demo.add_argument("--voice", default=None, help="Target voice reference audio.")
    demo.add_argument("--song", default=None, help="Source song audio.")
    demo.add_argument("--voice-profile-id", default=None)
    demo.add_argument("--song-id", default=None)
    demo.add_argument("--save-voice-to-library", action="store_true")
    demo.add_argument("--save-song-to-library", action="store_true")
    demo.add_argument("--voice-name", default=None)
    demo.add_argument("--song-title", default=None)
    demo.add_argument("--rights-confirmed", action="store_true")
    demo.add_argument("--seed-vc-dir", default="vendor/seed-vc")
    demo.add_argument("--work-dir", default="data/processed/demo")
    demo.add_argument("--output-dir", default="outputs")
    demo.add_argument("--cache-dir", default="data/cache")
    demo.add_argument("--render-mode", choices=sorted(PRESETS), default="m2max_hq_30")
    demo.add_argument("--device", choices=["auto", "mps", "cpu", "cuda"], default="auto")
    demo.add_argument("--demucs-model", default=None)
    demo.add_argument("--demucs-overlap", type=float, default=None)
    demo.add_argument("--diffusion-steps", type=int, default=None)
    demo.add_argument("--length-adjust", type=float, default=1.0)
    demo.add_argument("--inference-cfg-rate", type=float, default=None)
    demo.add_argument("--semi-tone-shift", type=int, default=0)
    demo.add_argument("--fp16", action=argparse.BooleanOptionalAction, default=None)
    demo.add_argument("--clip-seconds", type=int, default=None, help="Override the preset clip duration.")
    demo.add_argument("--reference-seconds", type=int, default=None, help="Override the preset voice reference length.")
    demo.add_argument("--skip-separation", action="store_true", help="Treat the song input as clean vocals and skip Demucs.")
    demo.add_argument("--compact-vocals", action=argparse.BooleanOptionalAction, default=None, help="Only convert detected vocal regions.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "check":
        report = check_environment(Path(args.seed_vc_dir))
        print(report.to_text())
        return 0 if report.ready else 1

    if args.command == "check-mps":
        import torch

        print("Python:", sys.version.split()[0])
        print("platform:", platform.platform())
        print("torch:", torch.__version__)
        print("mps built:", torch.backends.mps.is_built())
        print("mps available:", torch.backends.mps.is_available())
        recommended = "mps" if torch.backends.mps.is_built() and torch.backends.mps.is_available() else "cpu"
        print("recommended device:", recommended)
        return 0 if recommended == "mps" else 1

    if args.command == "web":
        from .web import run_web_app

        run_web_app(host=args.host, port=args.port, seed_vc_dir=Path(args.seed_vc_dir))
        return 0

    if args.command == "library":
        init_library()
        print("Library initialized: data/library/timbre_shift.db")
        return 0

    if args.command == "voices":
        if args.voices_command == "list":
            for profile in list_voice_profiles():
                marker = "target" if profile.allowed_as_target else "source-only"
                print(f"{profile.id}\t{profile.name}\t{marker}\t{profile.rights_status}")
            return 0
        if args.voices_command == "add":
            profile = save_voice_to_library(
                Path(args.audio),
                name=args.name,
                description=args.description,
                rights_status=args.rights,
                allowed_as_target=args.allow_target,
            )
            print(f"Voice saved: {profile.id}\t{profile.name}")
            return 0
        if args.voices_command == "delete":
            archive_voice_profile(args.id)
            print(f"Voice archived: {args.id}")
            return 0

    if args.command == "songs":
        if args.songs_command == "list":
            for song in list_songs():
                print(f"{song.id}\t{song.title}\t{song.source_kind}")
            return 0
        if args.songs_command == "add":
            song = save_song_to_library(
                Path(args.audio),
                title=args.title,
                artist=args.artist,
                source_kind=args.source_kind,
            )
            print(f"Song saved: {song.id}\t{song.title}")
            return 0
        if args.songs_command == "delete":
            archive_song(args.id)
            print(f"Song archived: {args.id}")
            return 0

    if args.command == "demo":
        options = PipelineOptions(
            voice=Path(args.voice) if args.voice else None,
            song=Path(args.song) if args.song else None,
            seed_vc_dir=Path(args.seed_vc_dir),
            work_dir=Path(args.work_dir),
            output_dir=Path(args.output_dir),
            cache_dir=Path(args.cache_dir),
            render_mode=args.render_mode,
            demucs_model=args.demucs_model,
            demucs_overlap=args.demucs_overlap,
            diffusion_steps=args.diffusion_steps,
            length_adjust=args.length_adjust,
            inference_cfg_rate=args.inference_cfg_rate,
            semi_tone_shift=args.semi_tone_shift,
            fp16=args.fp16,
            clip_seconds=args.clip_seconds,
            reference_seconds=args.reference_seconds,
            device=args.device,
            skip_separation=args.skip_separation,
            compact_vocals=args.compact_vocals,
            voice_profile_id=args.voice_profile_id,
            song_id=args.song_id,
            save_voice_to_library=args.save_voice_to_library,
            save_song_to_library=args.save_song_to_library,
            voice_name=args.voice_name,
            song_title=args.song_title,
            rights_confirmed=args.rights_confirmed,
            source_mode="clean_vocal" if args.skip_separation else "full_song",
        )
        final_mix = run_demo(options)
        print("Final mix:", final_mix)
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
