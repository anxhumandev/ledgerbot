"""Clean Feed API: what API buyers receive (the same canonical records and offer selection as the portal)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import feed

router = APIRouter()


@router.get("/v1/hotels/{tid}/offers")
def hotel_offers(tid: str, nights: int = Query(3, ge=1, le=30), strategy: str = "expected_value"):
    if strategy not in ("expected_value", "cheapest"):
        raise HTTPException(400, "strategy must be expected_value or cheapest")
    try:
        return feed.hotel_offers(tid, nights, strategy)
    except KeyError:
        raise HTTPException(404, "unknown ledger id")


@router.get("/v1/search")
def search(area: str = "marina", nights: int = Query(3, ge=1, le=30)):
    return feed.search(area, nights)
