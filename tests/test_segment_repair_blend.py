from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf

from timbre_shift.segment_repair_blend import blend_problem_segments
from timbre_shift.vocal_segments import VocalSegment, map_compact_problem_segments


def test_blend_problem_segments_keeps_clean_ranges_and_repairs_bad_range():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        sr = 1000
        base = np.zeros(sr, dtype=np.float32)
        repair = np.ones(sr, dtype=np.float32)
        base_path = root / "base.wav"
        repair_path = root / "repair.wav"
        out_path = root / "out.wav"
        sf.write(base_path, base, sr)
        sf.write(repair_path, repair, sr)

        blend_problem_segments(
            base_path,
            repair_path,
            out_path,
            problem_segments=[{"start": 0.4, "end": 0.6}],
            wet=0.5,
            fade_seconds=0.01,
        )

        mixed, _ = sf.read(out_path)
        assert abs(float(mixed[100])) < 0.01
        assert 0.45 <= float(mixed[500]) <= 0.55
        assert abs(float(mixed[900])) < 0.01


def test_map_compact_problem_segments_to_original_timeline():
    compact_segments = [
        VocalSegment(original_start=10.0, original_end=20.0, compact_start=0.0),
        VocalSegment(original_start=40.0, original_end=50.0, compact_start=10.0),
    ]

    mapped = map_compact_problem_segments(
        [{"start": 8.0, "end": 12.0, "risk_level": "bad"}],
        compact_segments,
    )

    assert mapped == [
        {"start": 18.0, "end": 20.0, "risk_level": "bad"},
        {"start": 40.0, "end": 42.0, "risk_level": "bad"},
    ]
