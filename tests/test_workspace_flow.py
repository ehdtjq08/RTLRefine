import json

import pytest

from rtl_agent.common import ROOT, sha256
from rtl_agent.sequential.case_review import original_source
from workspace_service import request_repair


def test_one_active_workspace_worker_and_release_after_error(tmp_path, monkeypatch):
    import workspace_service as service
    monkeypatch.setattr(service, "LOCK_PATH", tmp_path / "worker.lock")
    with service.execution_slot():
        with pytest.raises(RuntimeError, match="Another RTL review"):
            with service.execution_slot():
                pytest.fail("Concurrent worker was allowed")
    with service.execution_slot():
        pass


def test_paid_repair_requires_the_exact_current_failing_source():
    source = original_source("fifo_reset")
    with pytest.raises(ValueError, match="current failing source"):
        request_repair("fifo_reset", source, {"case": "axis_keep", "rtl_sha256": sha256(source.encode()), "accepted": False})
    with pytest.raises(ValueError, match="current failing source"):
        request_repair("fifo_reset", source, {"case": "fifo_reset", "rtl_sha256": "changed", "accepted": False})
    with pytest.raises(ValueError, match="current failing source"):
        request_repair("fifo_reset", source, {"case": "fifo_reset", "rtl_sha256": sha256(source.encode()), "accepted": True})


def test_workspace_browsing_never_calls_a_model_and_paid_actions_default_off(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv("RTLREFINE_ENABLE_LIVE_MODEL", raising=False)
    monkeypatch.setattr("workspace_service.request_repair", lambda *a, **k: pytest.fail("Unexpected model request"))
    app = AppTest.from_file(str(ROOT / "workspace_app.py"), default_timeout=20).run()
    assert not app.exception
    assert app.title[0].value == "Check your RTL change."
    assert next(b for b in app.button if b.label == "Ask NVIDIA to repair this failing change").disabled
    app.selectbox[0].select("frame_fifo").run()
    assert not app.exception
    assert "FRAME_FIFO" in app.info[0].value


def test_focused_hackathon_app_has_only_rtl_workflows():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(ROOT / "rtl_app.py"), default_timeout=20).run()
    assert not app.exception
    assert app.title[0].value == "An AI fix needs evidence."
    values = {metric.label: metric.value for metric in app.metric}
    assert values["Historical RTL cases"] == "13"
    assert values["Known-bug comparison cases"] == "9"
    assert not any("booking" in str(x.value).lower() for x in app.caption)
