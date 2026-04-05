"""
Redis client helpers for AgentTrade.
Handles quote collection (TTL 30s) and agent inbox / session state (TTL 5min).
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

QUOTE_TTL_SECONDS = 30       # RFQ quote collection window
SESSION_TTL_SECONDS = 300   # 5 minutes — agent session state
MESSAGE_TTL_SECONDS = 300   # agent inbox messages


# ---------------------------------------------------------------------------
# Quote collection
# ---------------------------------------------------------------------------

def open_quote_window(rfq_id: str) -> None:
    """Open a Redis key for collecting quotes for an RFQ. TTL: 30s."""
    r = get_redis()
    key = f"rfq:{rfq_id}:quotes"
    r.delete(key)
    r.expire(key, QUOTE_TTL_SECONDS)


def push_quote(rfq_id: str, quote: dict) -> None:
    """
    Push a supplier quote into the RFQ's quote collection.
    Stores as a JSON list member.
    """
    r = get_redis()
    key = f"rfq:{rfq_id}:quotes"
    r.rpush(key, json.dumps(quote))
    # Refresh TTL on each push
    r.expire(key, QUOTE_TTL_SECONDS)


def get_quotes(rfq_id: str) -> list[dict]:
    """Retrieve all quotes collected for an RFQ."""
    r = get_redis()
    key = f"rfq:{rfq_id}:quotes"
    raw = r.lrange(key, 0, -1)
    return [json.loads(item) for item in raw]


def get_quote_count(rfq_id: str) -> int:
    """Return the number of quotes collected so far."""
    r = get_redis()
    return r.llen(f"rfq:{rfq_id}:quotes")


# ---------------------------------------------------------------------------
# Agent inbox / messaging
# ---------------------------------------------------------------------------

def send_message(agent_id: str, message: dict) -> None:
    """
    Deliver a message to an agent's inbox.
    Used for RFQ notifications and negotiation messages.
    """
    r = get_redis()
    key = f"agent:{agent_id}:inbox"
    r.rpush(key, json.dumps(message))
    r.expire(key, MESSAGE_TTL_SECONDS)


def get_messages(agent_id: str) -> list[dict]:
    """Fetch and drain all pending messages for an agent."""
    r = get_redis()
    key = f"agent:{agent_id}:inbox"
    raw = r.lrange(key, 0, -1)
    if raw:
        r.delete(key)
    return [json.loads(item) for item in raw]


def peek_messages(agent_id: str) -> list[dict]:
    """Peek at pending messages without draining."""
    r = get_redis()
    key = f"agent:{agent_id}:inbox"
    raw = r.lrange(key, 0, -1)
    return [json.loads(item) for item in raw]


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def set_session_state(agent_id: str, session_id: str, state: dict) -> None:
    """Store ephemeral agent session state."""
    r = get_redis()
    key = f"session:{agent_id}:{session_id}"
    r.set(key, json.dumps(state), ex=SESSION_TTL_SECONDS)


def get_session_state(agent_id: str, session_id: str) -> dict | None:
    """Retrieve agent session state, returns None if expired or missing."""
    r = get_redis()
    key = f"session:{agent_id}:{session_id}"
    raw = r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


def delete_session_state(agent_id: str, session_id: str) -> None:
    """Explicitly delete session state (e.g., on session end)."""
    r = get_redis()
    r.delete(f"session:{agent_id}:{session_id}")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def ping() -> bool:
    """Return True if Redis is reachable."""
    try:
        return get_redis().ping()
    except redis.RedisError:
        return False
