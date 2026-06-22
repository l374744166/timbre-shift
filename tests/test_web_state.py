from timbre_shift.web_state import ProgressState


def test_progress_update_clears_stale_error_on_success():
    progress = ProgressState()
    progress.fail("old error")

    progress.update("素材已添加", 100, "completed")
    snapshot = progress.snapshot()

    assert snapshot["status"] == "completed"
    assert snapshot["error"] == ""
    assert snapshot["cancel_requested"] is False
