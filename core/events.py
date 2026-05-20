"""EventBus for AgentTrade v2.

In-process event emitter that decouples the agent from the frontend.
No subscribers = no-ops (CLI mode works perfectly).
server.py subscribes and translates events to SSE for the React dashboard.

Event types emitted by the agent:
    agent_started        — {buyer_id, request}
    suppliers_discovered — {count, suppliers: [{id, name, rating}]}
    quote_received       — {supplier_id, supplier_name, terms}
    counter_sent         — {supplier_id, round, proposed_terms, reasoning}
    counter_received     — {supplier_id, round, decision, response_terms}
    offer_accepted       — {supplier_id, final_terms}
    supplier_rejected    — {supplier_id, reason}
    escrow_locked        — {deal_id, txid, amount_usd, amount_algo, deal_hash}
    delivery_confirmed   — {deal_id, proof_hash, txid}
    payment_released     — {deal_id, txid, amount}
    agent_thinking       — {thought}
    agent_error          — {error_type, message, details}
"""

from __future__ import annotations

from typing import Any, Callable

Listener = Callable[[str, dict[str, Any]], None]


class EventBus:
    """In-process event emitter. Thread-safe enough for single-process use."""

    _listeners: list[Listener] = []

    @classmethod
    def emit(cls, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to all subscribers.

        Args:
            event_type: One of the documented event types.
            data: Event payload (JSON-serializable dict).
        """
        payload = data or {}
        for listener in cls._listeners:
            try:
                listener(event_type, payload)
            except Exception:
                pass  # Never let a listener crash the agent

    @classmethod
    def subscribe(cls, listener: Listener) -> None:
        """Register a listener function.

        Args:
            listener: Callable(event_type: str, data: dict) -> None
        """
        cls._listeners.append(listener)

    @classmethod
    def unsubscribe(cls, listener: Listener) -> None:
        """Remove a previously registered listener."""
        try:
            cls._listeners.remove(listener)
        except ValueError:
            pass

    @classmethod
    def clear(cls) -> None:
        """Remove all listeners. Called after agent run completes."""
        cls._listeners.clear()

    @classmethod
    def has_listeners(cls) -> bool:
        """Check if any listeners are subscribed."""
        return len(cls._listeners) > 0
