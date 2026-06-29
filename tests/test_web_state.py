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


def test_progress_snapshot_includes_details():
    progress = ProgressState()
    progress.reset("开始训练", 2, "running", {"task_type": "rvc_training", "current_epoch": 0, "total_epochs": 80})
    progress.update("训练第 12/80 轮", 30, details={"task_type": "rvc_training", "current_epoch": 12, "total_epochs": 80})

    snapshot = progress.snapshot()

    assert snapshot["details"]["task_type"] == "rvc_training"
    assert snapshot["details"]["current_epoch"] == 12
    assert snapshot["details"]["total_epochs"] == 80
