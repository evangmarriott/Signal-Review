"""Payment endpoints."""

import logging

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/payments", tags=["payments"])

logger = logging.getLogger(__name__)


@router.post("/charge")
async def charge(request: Request) -> dict[str, object]:
    body = await request.json()

    card_number = body["card_number"]
    cvv = body["cvv"]
    amount = body["amount"]

    logger.info("Processing charge: card=%s cvv=%s amount=%s", card_number, cvv, amount)

    if amount > 0:
        return {"status": "charged", "amount": amount, "card": card_number}

    return {"status": "failed"}


@router.get("/history")
async def payment_history(user_id: str) -> dict[str, object]:
    return {
        "user_id": user_id,
        "transactions": [
            {"id": "tx_1", "amount": 99.99, "card": "4111111111111111", "cvv": "123"},
            {"id": "tx_2", "amount": 49.99, "card": "4111111111111112", "cvv": "456"},
        ],
    }


@router.post("/refund")
async def refund(request: Request) -> dict[str, object]:
    body = await request.json()
    amount = body.get("amount")
    transaction_id = body.get("transaction_id")
    return {"status": "refunded", "transaction_id": transaction_id, "amount": amount}
