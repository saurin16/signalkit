import pytest
from httpx import ASGITransport, AsyncClient

from signalkit.engine import AnalyzeRequest, Package, Site, assign
from signalkit.main import app


def test_compatibility_and_thin_data_never_create_false_winner():
    request = AnalyzeRequest(packages=[
        Package(id="A", title="Creative A", artist="Artist A", orientation="portrait"),
        Package(id="B", title="Creative B", artist="Artist B", orientation="landscape"),
    ], sites=[Site(id="S", name="Test site", city="Chicago, IL", orientation="landscape")])
    profiles = [
        {"resolved_name": "Artist A", "scores": {"Chicago, IL": {"percentile": 100, "affinity_rank": 0.9}}},
        {"resolved_name": "Artist B", "scores": {"Chicago, IL": {"percentile": None, "affinity_rank": None}}},
    ]
    result = assign(request, profiles)[0]
    assert result["winner"] is None
    assert result["confidence"] == "review"
    assert result["options"][0]["compatible"] is False


@pytest.mark.asyncio
async def test_export_needs_technician_approval(monkeypatch):
    import signalkit.main as main
    fake = {"packages": [{"id": "A", "title": "Approved A"}],
            "assignments": [{"site": {"id": "S", "name": "Site", "city": "Chicago, IL", "orientation": "landscape"},
                             "winner": "A", "confidence": "clear", "reason": "Measured fit",
                             "options": [{"package_id": "A", "percentile": 90}]}],
            "approved": False}
    monkeypatch.setitem(main._runs, "test", fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/runs/test/export.csv")).status_code == 409
        approval = await client.post("/api/runs/test/approve", json={"approved": True})
        assert approval.status_code == 200
        csv_response = await client.get("/api/runs/test/export.csv")
        assert csv_response.status_code == 200
        assert "Chicago, IL" in csv_response.text
        assert "Approved A" in csv_response.text
