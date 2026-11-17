from streamlit.testing.v1 import AppTest

from backend.config import ROOT


def test_home_uses_backend_shape(monkeypatch):
    import httpx

    class Response:
        def raise_for_status(self):
            pass

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def get(url, **kwargs):
        return Response(
            {"status": "ok", "mode": "none", "embedding_backend": "hash"}
            if url.endswith("/health")
            else {"documents": 0, "chunks": 0, "failed_runs": 0}
        )

    monkeypatch.setattr(httpx, "get", get)
    app = AppTest.from_file(str(ROOT / "app/streamlit_app.py")).run(timeout=15)
    assert not app.exception
    assert len(app.metric) == 3
