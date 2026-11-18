from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from app.web import page
from . import service

router = APIRouter()
ROWS = [
    {"key": "BA185->BA178@JFK", "status": "待确认", "value": "等待 60/120 分钟"},
    {"key": "BA178->BA168@LHR", "status": "已判定", "value": "VALID 330"},
    {"key": "JFK T4-T1（样例）", "status": "已判定", "value": "VALID 150"},
]


@router.get("/connections", response_class=HTMLResponse)
def view(request: Request):
    return page(request, "m5.html", "衔接判定", "/api/connections/check", ROWS)


@router.post("/api/connections/check")
def execute(payload: dict | None = None):
    if payload:
        return service.run(payload)
    result = service.demo()
    result["run_id"] = service.run_id(service.DEMO_PAYLOAD)
    return result


@router.post("/api/connections/check-chain")
def execute_chain(payload: dict | None = None):
    return service.check_demo()


@router.post("/api/connections/confirm")
def execute_confirm(payload: dict | None = None):
    return service.apply_confirmation(payload)


@router.get("/api/connections/board")
def execute_board(run_id: str | None = None):
    return service.get_board(run_id)
