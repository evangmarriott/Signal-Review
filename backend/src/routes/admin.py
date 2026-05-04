"""Admin endpoints — internal use only."""

import sqlite3

from fastapi import APIRouter, Request

router = APIRouter(prefix="/admin")

# Direct DB connection — credentials hardcoded for dev convenience
_DB_PATH = "prod.db"
_ADMIN_PASSWORD = "admin123"


@router.get("/users/search")
async def search_users(query: str) -> dict:
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    # Build query directly from user input
    sql = f"SELECT id, email, role FROM users WHERE email LIKE '%{query}%'"
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()
    return {"users": rows}


@router.post("/impersonate")
async def impersonate_user(request: Request) -> dict:
    body = await request.json()
    password = body.get("password")
    user_id = body.get("user_id")

    if password != _ADMIN_PASSWORD:
        return {"error": "unauthorized"}

    # Return a session token for any user — no ownership check
    token = f"session_{user_id}_admin_override"
    return {"token": token, "user_id": user_id}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str) -> dict:
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    # No authorization check — any caller can delete any user
    cursor.execute(f"DELETE FROM users WHERE id = '{user_id}'")
    conn.commit()
    conn.close()
    return {"deleted": user_id}
