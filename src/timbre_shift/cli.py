"""Command-line entrypoint for the local demo pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import PipelineOptions, check_environment, run_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="timbre-shift",
        description="Run the Timbre Shift local voice conversion demo.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Check local tool availability.")
    check.add_argument("--seed-vc-dir", default="vendor/seed-vc")

    web = subparsers.add_parser("web", help="Start the local upload demo web app.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--seed-vc-dir", default="vendor/seed-vc")

    demo = subparsers.add_parser("demo", help="Run separation, conversion, and mixing.")
    demo.add_argument("--voice", required=True, help="Target voice reference audio.")
    demo.add_argument("--song", required=True, help="Source song audio.")
    demo.add_argument("--seed-vc-dir", default="vendor/seed-vc")
    demo.add_argument("--work-dir", default="data/processed/demo")
    demo.add_argument("--output-dir", default="outputs")
    demo.add_argument("--demucs-model", default="htdemucs_ft")
    demo.add_argument("--diffusion-steps", type=int, default=40)
    demo.add_argument("--length-adjust", type=float, default=1.0)
    demo.add_argument("--inference-cfg-rate", type=float, default=0.7)
    demo.add_argument("--semi-tone-shift", type=int, default=0)
    demo.add_argument("--fp16", action=argparse.BooleanOptionalAction, default=False)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "check":
        report = check_environment(Path(args.seed_vc_dir))
        print(report.to_text())
        return 0 if report.ready else 1

    if args.command == "web":
        from .web import run_web_app

        run_web_app(host=args.host, port=args.port, seed_vc_dir=Path(args.seed_vc_dir))
        return 0

    if args.command == "demo":
        options = PipelineOptions(
            voice=Path(args.voice),
            song=Path(args.song),
            seed_vc_dir=Path(args.seed_vc_dir),
            work_dir=Path(args.work_dir),
            output_dir=Path(args.output_dir),
            demucs_model=args.demucs_model,
            diffusion_steps=args.diffusion_steps,
            length_adjust=args.length_adjust,
            inference_cfg_rate=args.inference_cfg_rate,
            semi_tone_shift=args.semi_tone_shift,
            fp16=args.fp16,
        )
        final_mix = run_demo(options)
        print("Final mix:", final_mix)
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
