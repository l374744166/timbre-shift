from pathlib import Path
from types import SimpleNamespace

from timbre_shift.variant_actions import find_variant
from timbre_shift.voice_quality import build_voice_quality_details
from timbre_shift.web import AppHandler
from timbre_shift.web_serializers import serialize_voice_model
from timbre_shift.web_template import page_html


def test_ui_uses_product_workstation_shell_and_module_assets():
    html = page_html()
    static_root = Path(__file__).parents[1] / "src" / "timbre_shift" / "web_static"
    app_js = (static_root / "app.js").read_text()
    dashboard_js = (static_root / "views" / "DashboardView.js").read_text()
    result_js = (static_root / "components" / "ResultCard.js").read_text()
    variant_js = (static_root / "components" / "VariantCard.js").read_text()
    base_css = (static_root / "styles" / "base.css").read_text()

    assert "本地 AI 音色转换工作台" in html
    assert 'data-view="dashboard"' in html
    assert 'data-view="training"' in html
    assert 'id="viewRoot"' in html
    assert 'id="envStatus"' in html
    assert 'id="seedvcStatus"' in html
    assert 'id="applioStatus"' in html
    assert '<script type="module" src="/static/app.js"></script>' in html
    assert "/static/styles/base.css" in html
    assert "__APP_CSS__" not in html
    assert "__APP_JS__" not in html

    assert "const form = document.getElementById" in app_js
    assert "Step 1：选择转换方式" in dashboard_js
    assert "Seed-VC 快速试听" in dashboard_js
    assert "Applio RVC 正式生成" in dashboard_js
    assert "自然稳定" in dashboard_js
    assert "歌词更清楚" in dashboard_js
    assert "更像目标音色" in dashboard_js
    assert "高级设置" in dashboard_js
    assert "源人声清理" in dashboard_js
    assert "咬字增强" in dashboard_js
    assert "音色记忆库" in dashboard_js
    assert "混音风格" in dashboard_js
    assert "scorecard" in result_js
    assert "干声人声" in result_js
    assert "downloadDryVocal" in result_js
    assert "设为最终版本" in variant_js
    assert "标记喜欢" in variant_js
    assert ":root" in base_css


def test_voice_sample_quality_details_warn_for_short_single_source():
    samples = [
        SimpleNamespace(duration_seconds=120.0, source_type="separated_voice"),
    ]

    details = build_voice_quality_details(samples)

    assert details["sample_count"] == 1
    assert "少于5分钟" in details["duration_hint"]
    assert any("来源偏单一" in warning for warning in details["warnings"])
    assert any("分离人声" in warning for warning in details["warnings"])


def test_variant_lookup_uses_stable_ids():
    metrics = {
        "variants": [
            {"id": "stable_balanced", "wav": "stable.wav"},
            {"id": "clear_diction", "wav": "clear.wav"},
        ]
    }

    assert find_variant("clear_diction", metrics)["wav"] == "clear.wav"
    assert find_variant("missing", metrics) is None


def test_success_message_does_not_expose_device_name():
    source = AppHandler.do_POST.__code__.co_consts
    assert "歌曲生成完成" in source
    assert not any(isinstance(item, str) and "M2 Max" in item and "生成完成" in item for item in source)


def test_voice_model_serializer_exposes_training_details():
    model = SimpleNamespace(
        id="model1",
        model_name="Demo RVC",
        engine_id="rvc_applio",
        status="ready",
        dataset_seconds=123.0,
        training_seconds=45.0,
        model_path="/tmp/model.pth",
        updated_at="2026-06-22T10:00:00+00:00",
        metadata_json='{"epochs": 80, "batch_size": 4, "sample_rate": 40000}',
    )
    quality = {"sample_count": 3, "sample_seconds": 123.0, "duration_hint": "素材10-30分钟，比较推荐"}

    payload = serialize_voice_model(model, quality)

    assert payload["epochs"] == 80
    assert payload["batch_size"] == 4
    assert payload["sample_rate"] == 40000
    assert payload["dataset_seconds"] == 123.0
    assert payload["training_seconds"] == 45.0


def test_voice_model_serializer_infers_epochs_from_model_filename():
    model = SimpleNamespace(
        id="model1",
        model_name="Demo RVC",
        engine_id="rvc_applio",
        status="ready",
        dataset_seconds=123.0,
        training_seconds=45.0,
        model_path="/tmp/Demo_80e_s123.pth",
        updated_at="2026-06-22T10:00:00+00:00",
        metadata_json="{}",
    )
    quality = {"sample_count": 3, "sample_seconds": 123.0, "duration_hint": "素材10-30分钟，比较推荐"}

    assert serialize_voice_model(model, quality)["epochs"] == 80
