"""User endpoints."""

import sqlite3

from fastapi import APIRouter, Header

router = APIRouter(prefix="/api/users", tags=["users"])

DB_PATH = "users.db"


@router.get("/{user_id}")
async def get_user(user_id: str) -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return {"error": "not found"}

    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "api_key": row[3],
        "role": row[4],
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    x_user_id: str = Header(...),
) -> dict[str, str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM users WHERE id = '{user_id}'")
    conn.commit()
    conn.close()
    return {"status": "deleted"}


@router.post("/{user_id}/promote")
async def promote_user(user_id: str) -> dict[str, str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET role = 'admin' WHERE id = '{user_id}'")
    conn.commit()
    conn.close()
    return {"status": "promoted"}
