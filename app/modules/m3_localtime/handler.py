from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web import page
from .service import demo, run, review

router = APIRouter()
ROWS = [
    {"key": "JFK|2026-11-01 01:30", "status": "待确认", "value": "fold 0/1 两个 UTC"},
    {"key": "JFK|2026-03-08 02:30", "status": "隔离", "value": "跳时不存在"},
    {"key": "PVG|2026-11-16 09:00", "status": "已判定", "value": "+08:00"},
]


@router.get("/local-time", response_class=HTMLResponse)
def view(request: Request):
    return page(request, "m3.html", "当地时刻", "/api/local-time/resolve", ROWS)


@router.post("/api/local-time/resolve")
def execute(payload: dict | None = None):
    return run(payload) if payload else demo()


@router.post("/api/local-time/review")
def execute_review(payload: dict | None = None):
    return review(payload)
