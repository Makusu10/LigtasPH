"""Idempotency key management for state-changing endpoints in LigtasPH.

Follows the Idempotency Design Principles:
1. Accept Idempotency-Key from client header.
2. Guard the payload: Same key with different payload fails with 422.
3. Claim atomically: Unique constraint picks the winner.
4. Concurrency guard: In-flight duplicate returns 409 Conflict.
5. Replay: Exact retry receives original cached response.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any
from flask import Request, Response, jsonify

from utils.api_errors import api_error


def get_idempotency_key(req: Request) -> str | None:
    """Extract and validate Idempotency-Key header from incoming request."""
    key = req.headers.get("Idempotency-Key")
    if not key:
        return None
    key = key.strip()
    if not key:
        return None
    return key[:255]


def claim_idempotency(
    db: sqlite3.Connection,
    key: str,
    raw_payload: bytes,
) -> tuple[str, dict[str, Any] | None, tuple[Response, int] | None]:
    """Atomically claim an idempotency key before performing side effects.

    Returns:
        (state, cached_data, error_response)
        - If "claimed": Caller proceeds with business logic.
        - If "succeeded": Caller returns cached response directly.
        - If error: error_response is returned to client (409 or 422).
    """
    request_hash = hashlib.sha256(raw_payload).hexdigest()

    # Opportunistically prune expired keys
    try:
        db.execute("DELETE FROM idempotency_keys WHERE expires_at <= datetime('now')")
    except Exception:
        pass

    try:
        db.execute(
            """INSERT INTO idempotency_keys (key, request_hash, state, expires_at)
               VALUES (?, ?, 'in_progress', datetime('now', '+24 hours'))""",
            (key, request_hash),
        )
        db.commit()
        return "claimed", None, None
    except sqlite3.IntegrityError:
        # Key already claimed: check state and payload hash
        row = db.execute(
            "SELECT request_hash, status_code, response_body, state FROM idempotency_keys WHERE key=?",
            (key,),
        ).fetchone()

        if not row:
            # Race deletion: allow caller to retry
            return "claimed", None, None

        if row["request_hash"] != request_hash:
            err = api_error(
                "Idempotency key reused with a different payload",
                status_code=422,
                code="IDEMPOTENCY_PAYLOAD_MISMATCH",
            )
            return "mismatch", None, err

        if row["state"] == "in_progress":
            err = api_error(
                "A request with this idempotency key is currently in progress",
                status_code=409,
                code="IDEMPOTENCY_IN_PROGRESS",
            )
            return "in_progress", None, err

        if row["state"] == "succeeded":
            return "succeeded", {
                "status_code": row["status_code"],
                "response_body": row["response_body"],
            }, None

        # If previous attempt failed, reset state to in_progress to permit retry
        db.execute(
            """UPDATE idempotency_keys
               SET request_hash=?, state='in_progress', expires_at=datetime('now', '+24 hours')
               WHERE key=?""",
            (request_hash, key),
        )
        db.commit()
        return "claimed", None, None


def record_idempotency(
    db: sqlite3.Connection,
    key: str | None,
    status_code: int,
    response_body: str,
    succeeded: bool = True,
) -> None:
    """Record final response payload for an idempotency key upon completion."""
    if not key:
        return
    try:
        state = "succeeded" if succeeded else "failed"
        db.execute(
            """UPDATE idempotency_keys
               SET status_code=?, response_body=?, state=?
               WHERE key=?""",
            (status_code, response_body, state, key),
        )
        db.commit()
    except Exception:
        pass
