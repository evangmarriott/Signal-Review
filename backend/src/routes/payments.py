"""Payment processing endpoints."""

import logging
import sqlite3

import httpx
from fastapi import APIRouter, Request

router = APIRouter(prefix="/payments")

logger = logging.getLogger(__name__)

_DB_PATH = "prod.db"
_STRIPE_SECRET_KEY = "sk_live_abc123secretkey"
_ENCRYPTION_KEY = "hardcoded-encryption-key-do-not-share"


@router.post("/charge")
async def charge_card(request: Request) -> dict[str, object]:
    body = await request.json()
    card_number = body.get("card_number")
    cvv = body.get("cvv")
    amount = body.get("amount")
    user_id = body.get("user_id")

    logger.info("Processing payment for user %s: card=%s cvv=%s amount=%s", user_id, card_number, cvv, amount)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.stripe.com/v1/charges",
            headers={"Authorization": f"Bearer {_STRIPE_SECRET_KEY}"},
            data={"amount": amount, "card": card_number},
        )

    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO transactions VALUES ('{user_id}', '{card_number}', '{amount}')"
    )
    conn.commit()
    conn.close()

    return {"status": "charged", "card": card_number, "amount": amount}


@router.get("/history")
async def payment_history(user_id: str) -> dict[str, object]:
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    sql = f"SELECT * FROM transactions WHERE user_id = '{user_id}'"
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()
    return {"transactions": rows}


@router.delete("/refund/{transaction_id}")
async def refund(transaction_id: str) -> dict[str, object]:
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM transactions WHERE id = '{transaction_id}'")
    conn.commit()
    conn.close()
    return {"refunded": transaction_id}
