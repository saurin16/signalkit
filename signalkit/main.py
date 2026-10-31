import asyncio
import csv
import io
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import AnalyzeRequest, DEFAULT, analyze
from .metro import METROS
from .qloo import QlooError

app = FastAPI(title="SignalKit", version="1.0.0")
ROOT = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
_runs: dict[str, dict] = {}
_limit = asyncio.Semaphore(2)


@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
async def health():
    return {"ok": True, "service": "signalkit"}


@app.get("/api/config")
async def config():
    return {"cities": sorted(METROS), "example": DEFAULT.model_dump()}


@app.post("/api/analyze")
async def run(request: AnalyzeRequest):
    try:
        async with _limit:
            result = await analyze(request)
    except (ValueError, QlooError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Qloo analysis is unavailable right now. Please retry.") from exc
    run_id = uuid.uuid4().hex[:16]
    result.update({"id": run_id, "approved": False})
    _runs[run_id] = result
    if len(_runs) > 100:
        _runs.pop(next(iter(_runs)))
    return result


class Approval(BaseModel):
    approved: bool


@app.post("/api/runs/{run_id}/approve")
async def approve(run_id: str, decision: Approval):
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run expired. Analyze again.")
    run["approved"] = decision.approved
    return {"id": run_id, "approved": run["approved"]}


@app.get("/api/runs/{run_id}/export.csv")
async def export(run_id: str):
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run expired. Analyze again.")
    if not run["approved"]:
        raise HTTPException(409, "Technician approval required before export.")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["site_id", "site_name", "city", "screen_orientation", "package_id",
                     "package_title", "qloo_city_percentile", "review_required", "technician_note"])
    packages = {p["id"]: p for p in run["packages"]}
    for a in run["assignments"]:
        package = packages.get(a["winner"])
        score = next((o["percentile"] for o in a["options"] if o["package_id"] == a["winner"]), "")
        writer.writerow([a["site"]["id"], a["site"]["name"], a["site"]["city"],
                         a["site"]["orientation"], a["winner"] or "", package["title"] if package else "",
                         score, a["confidence"] == "review", a["reason"]])
    return Response(output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="signalkit-{run_id}.csv"'})
