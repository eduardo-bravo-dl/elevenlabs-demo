import asyncio
import hmac
import sqlite3
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app import db, services
from app.config import Settings, today_in_hotel
from app.schemas import (
    CheckAvailabilityRequest, CheckAvailabilityResponse, CreateTicketRequest,
    CreateTicketResponse, FindReservationRequest, FindReservationResponse,
    LateCheckoutRequest, LateCheckoutResponse,
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
    conn = db.connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def require_tool_secret(
    x_tool_secret: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings),
) -> None:
    supplied = (x_tool_secret or "").encode()
    if not hmac.compare_digest(supplied, settings.tool_secret.encode()):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Tool-Secret.")


async def simulate_failure(settings: Settings = Depends(get_settings)) -> None:
    if settings.failure_mode == "timeout":
        await asyncio.sleep(settings.timeout_seconds + 1)
        raise HTTPException(status_code=503, detail="PMS timed out.")
    if settings.failure_mode == "error":
        raise HTTPException(status_code=503, detail="PMS is unavailable.")


public = APIRouter()
tools = APIRouter(
    prefix="/tools",
    dependencies=[Depends(require_tool_secret), Depends(simulate_failure)],
)


@public.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "failure_mode": settings.failure_mode}


@tools.post("/find-reservation", response_model=FindReservationResponse)
def find_reservation(req: FindReservationRequest,
                     conn: sqlite3.Connection = Depends(get_conn)):
    return services.find_reservation(conn, req)


@tools.post("/check-availability", response_model=CheckAvailabilityResponse)
def check_availability(req: CheckAvailabilityRequest,
                       conn: sqlite3.Connection = Depends(get_conn)):
    return services.check_availability(conn, req)


@tools.post("/request-late-checkout", response_model=LateCheckoutResponse)
def request_late_checkout(req: LateCheckoutRequest,
                          conn: sqlite3.Connection = Depends(get_conn)):
    return services.request_late_checkout(conn, req, today_in_hotel())


@tools.post("/create-ticket", response_model=CreateTicketResponse)
def create_ticket(req: CreateTicketRequest,
                  conn: sqlite3.Connection = Depends(get_conn)):
    return services.create_ticket(conn, req)
