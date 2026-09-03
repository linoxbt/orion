from tests.conftest import ADMIN_HEADERS


def test_ingest_bill_without_gemini_key_returns_503(client):
    files = {"file": ("bill.txt", b"fake bill content", "text/plain")}
    res = client.post("/api/bills/ingest", headers=ADMIN_HEADERS, files=files)
    assert res.status_code == 503
    assert res.json()["detail"] == "gemini_not_configured"
