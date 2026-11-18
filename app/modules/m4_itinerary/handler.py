from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web import page
from .service import demo, run_chains

router = APIRouter()
ROWS = [
    {"key": "BA185 LHR-JFK", "status": "候选 2 条 UTC", "value": "fold 0/1"},
    {"key": "BA178 JFK-LHR", "status": "已判定", "value": "07:30Z"},
    {"key": "BA168 LHR-PVG", "status": "已判定", "value": "20:30Z"},
]


@router.get("/itineraries", response_class=HTMLResponse)
def view(request: Request):
    return page(request, "m4.html", "UTC 航链", "/api/itineraries/build", ROWS)


@router.post("/api/itineraries/build")
def execute(payload: dict | None = None):
    if payload and isinstance(payload, dict) and "rows" in payload:
        return run_chains(payload["rows"])
    if payload is None:
        return demo()
    return demo()


@router.post("/api/itineraries/chains")
def execute_chains(payload: dict | None = None):
    rows = payload.get("rows") if payload else None
    return run_chains(rows)
