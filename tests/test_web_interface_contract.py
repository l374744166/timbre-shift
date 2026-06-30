from pathlib import Path


def test_web_backend_routes_remain_available():
    source = Path('src/timbre_shift/web.py').read_text()
    routes = [
        '"/"',
        '"/static/"',
        '"/api/check"',
        '"/api/progress"',
        '"/api/history"',
        '"/api/latest-result"',
        '"/api/voice-preference"',
        '"/api/voice-samples"',
        '"/api/voice-models"',
        '"/download/history/"',
        '"/download/variants/"',
        '"/download/"',
        '"/api/cancel-task"',
        '"/api/tts-generate"',
        '"/api/history-restore"',
        '"/api/history-delete"',
        '"/api/select-variant"',
        '"/api/variant-feedback"',
        '"/api/add-voice-sample"',
        '"/api/delete-voice-sample"',
        '"/api/delete-voice"',
        '"/api/delete-song"',
        '"/api/delete-voice-model"',
        '"/api/create-voice-profile"',
        '"/api/applio-prepare"',
        '"/api/applio-train"',
        '"/api/save-voice"',
        '"/api/generate"',
    ]
    for route in routes:
        assert route in source


def test_frontend_does_not_call_unknown_api_routes():
    expected = {
        '/api/check',
        '/api/progress',
        '/api/history',
        '/api/latest-result',
        '/api/voice-models',
        '/api/voice-samples',
        '/api/voice-preference',
        '/api/generate',
        '/api/cancel-task',
        '/api/delete-voice-sample',
        '/api/delete-voice-model',
        '/api/applio-train',
        '/api/delete-voice',
        '/api/delete-song',
        '/api/add-voice-sample',
        '/api/create-voice-profile',
        '/api/save-voice',
        '/api/select-variant',
        '/api/variant-feedback',
        '/api/tts-generate',
    }
    frontend = '\n'.join(path.read_text() for path in Path('src/timbre_shift/web_static').rglob('*.js'))
    import re
    used = set(re.findall(r"['\"](/api/[^'\"?`]+)", frontend))
    assert used <= expected
