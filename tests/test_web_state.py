from timbre_shift.web_state import ProgressState


def test_progress_update_clears_stale_error_on_success():
    progress = ProgressState()
    progress.fail("old error")

    progress.update("素材已添加", 100, "completed")
    snapshot = progress.snapshot()

    assert snapshot["status"] == "completed"
    assert snapshot["error"] == ""
    assert snapshot["cancel_requested"] is False


def test_completed_progress_elapsed_time_is_frozen(monkeypatch):
    current = {"now": 100.0}
    monkeypatch.setattr("timbre_shift.web_state.time.time", lambda: current["now"])
    progress = ProgressState()

    current["now"] = 188.0
    progress.update("生成完成", 100, "completed")
    first = progress.snapshot()["elapsed_seconds"]

    current["now"] = 300.0
    second = progress.snapshot()["elapsed_seconds"]

    assert first == 88
    assert second == 88
