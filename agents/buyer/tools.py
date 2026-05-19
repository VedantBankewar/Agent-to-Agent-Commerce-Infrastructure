"""Buyer agent tools for AgentTrade v2.

Eight tools that the autonomous LangGraph ReAct buyer agent uses:
    1. discover_suppliers    — Search marketplace by category
    2. request_quotes        — Send RFQ to N suppliers concurrently
    3. evaluate_quotes       — Score and rank using priority-weighted formula
    4. send_counter_offer    — Multi-variable counter to one supplier
    5. accept_offer          — Accept supplier's terms
    6. reject_supplier       — Walk away from negotiation
    7. lock_escrow           — Lock USDC in Algorand escrow (1:1 with USD)
    8. get_negotiation_status — View all active negotiations
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool

from core.events import EventBus
from core.negotiation import NegotiationSessionManager
from core.types import (
    NegotiationTerms,
    ProcurementContext,
    SupplierProfile,
)
from utils.logger import get_logger

logger = get_logger("buyer_tools")

DATABASE_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")


def build_buyer_tools(
    session_manager: NegotiationSessionManager,
) -> list:
    """Build all 8 buyer tools, each wrapping the session manager.

    Args:
        session_manager: The NegotiationSessionManager for this procurement.

    Returns:
        List of LangChain tool functions.
    """

    @tool
    def discover_suppliers(category: str) -> dict[str, Any]:
        """Search the marketplace for suppliers matching a category.

        Args:
            category: Product category to search (furniture, office_supplies, electronics, general).

        Returns:
            Dict with count and list of supplier profiles.
        """
        from tools.search_suppliers import search_suppliers

        matches = search_suppliers(category=category)

        suppliers = []
        for m in matches:
            suppliers.append({
                "supplier_id": m.supplier_id,
                "name": m.name,
                "category": m.category,
                "rating": m.rating,
                "base_cost": m.base_cost,
                "lead_days": m.lead_days,
                "warranty_yrs": m.warranty_yrs,
                "min_price": m.min_price,
            })

        EventBus.emit("suppliers_discovered", {
            "count": len(suppliers),
            "suppliers": [{"id": s["supplier_id"], "name": s["name"], "rating": s["rating"]} for s in suppliers],
        })

        logger.info("Suppliers discovered", extra={"category": category, "count": len(suppliers)})

        return {"count": len(suppliers), "suppliers": suppliers}

    @tool
    def request_quotes(supplier_ids: list[str]) -> dict[str, Any]:
        """Send RFQ to multiple suppliers and get their quotes back concurrently.

        Args:
            supplier_ids: List of supplier IDs to request quotes from.

        Returns:
            Dict mapping supplier_id to their quote terms and score.
        """
        import sqlite3

        # Load supplier profiles from DB
        profiles = []
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        for sid in supplier_ids:
            row = conn.execute("SELECT * FROM suppliers WHERE supplier_id = ?", (sid,)).fetchone()
            if row:
                profiles.append(SupplierProfile(
                    supplier_id=row["supplier_id"],
                    name=row["name"],
                    category=row["category"],
                    wallet_addr=row["wallet_addr"],
                    rating=row["rating"],
                    base_cost=row["base_cost"],
                    margin_pct=row["margin_pct"],
                    lead_days=row["lead_days"],
                    warranty_yrs=row["warranty_yrs"],
                    min_price=row["min_price"],
                ))
        conn.close()

        responses = session_manager.start_negotiations_concurrent(profiles)

        result = {}
        for sid, response in responses.items():
            state = session_manager.context.negotiations.get(sid)
            result[sid] = {
                "supplier_name": state.supplier_name if state else sid,
                "terms": {
                    "unit_price_usd": response.proposed_terms.unit_price_usd,
                    "quantity": response.proposed_terms.quantity,
                    "delivery_days": response.proposed_terms.delivery_days,
                    "warranty_yrs": response.proposed_terms.warranty_yrs,
                    "total_usd": response.proposed_terms.total_usd(),
                } if response.proposed_terms else None,
                "score": state.score if state else None,
                "message": response.natural_language,
            }

        return result

    @tool
    def evaluate_quotes() -> dict[str, Any]:
        """Evaluate and rank all received quotes using priority-weighted scoring.

        Returns:
            Ranked list of offers with scores, budget check, and recommendations.
        """
        best = session_manager.get_best_offers()
        budget = session_manager.context.request.budget_usd

        ranked = []
        for sid, terms, score in best:
            state = session_manager.context.negotiations.get(sid)
            total = terms.total_usd()
            ranked.append({
                "supplier_id": sid,
                "supplier_name": state.supplier_name if state else sid,
                "unit_price_usd": terms.unit_price_usd,
                "total_usd": total,
                "delivery_days": terms.delivery_days,
                "warranty_yrs": terms.warranty_yrs,
                "score": score,
                "within_budget": total <= budget,
                "rating": state.rating if state else 0,
            })

        within_budget = [r for r in ranked if r["within_budget"]]
        over_budget = [r for r in ranked if not r["within_budget"]]

        return {
            "ranked_offers": ranked,
            "within_budget_count": len(within_budget),
            "over_budget_count": len(over_budget),
            "budget_usd": budget,
            "best_offer": ranked[0] if ranked else None,
        }

    @tool
    def send_counter_offer(
        supplier_id: str,
        unit_price_usd: float,
        delivery_days: int,
        warranty_yrs: float,
        message: str,
    ) -> dict[str, Any]:
        """Send a multi-variable counter-offer to a specific supplier.

        Args:
            supplier_id: The supplier to counter.
            unit_price_usd: Proposed unit price in USD.
            delivery_days: Proposed delivery time in days.
            warranty_yrs: Proposed warranty period in years.
            message: Natural language reasoning for the counter.

        Returns:
            Supplier's response with decision, terms, and round number.
        """
        state = session_manager.context.negotiations.get(supplier_id)
        quantity = state.current_terms.quantity if state and state.current_terms else session_manager.context.request.quantity

        terms = NegotiationTerms(
            unit_price_usd=unit_price_usd,
            quantity=quantity,
            delivery_days=delivery_days,
            warranty_yrs=warranty_yrs,
        )

        response = session_manager.send_counter(supplier_id, terms, message)

        return {
            "decision": response.decision.value if response.decision else None,
            "response_terms": {
                "unit_price_usd": response.proposed_terms.unit_price_usd,
                "delivery_days": response.proposed_terms.delivery_days,
                "warranty_yrs": response.proposed_terms.warranty_yrs,
                "total_usd": response.proposed_terms.total_usd(),
            } if response.proposed_terms else None,
            "round_number": response.round_number,
            "supplier_message": response.natural_language,
            "supplier_id": supplier_id,
        }

    @tool
    def accept_offer(supplier_id: str) -> dict[str, Any]:
        """Accept the current offer from a supplier. Call this when ready to finalize.

        Args:
            supplier_id: The supplier whose offer to accept.

        Returns:
            Confirmation with final terms.
        """
        confirmation = session_manager.accept_offer(supplier_id)
        state = session_manager.context.negotiations.get(supplier_id)

        session_manager.context.winning_supplier_id = supplier_id
        session_manager.context.deal_phase = session_manager.context.deal_phase.AGREED

        return {
            "confirmed": True,
            "supplier_id": supplier_id,
            "supplier_name": state.supplier_name if state else supplier_id,
            "final_terms": {
                "unit_price_usd": state.best_offer.unit_price_usd,
                "quantity": state.best_offer.quantity,
                "delivery_days": state.best_offer.delivery_days,
                "warranty_yrs": state.best_offer.warranty_yrs,
                "total_usd": state.best_offer.total_usd(),
            } if state and state.best_offer else None,
            "message": confirmation.natural_language,
        }

    @tool
    def reject_supplier(supplier_id: str, reason: str) -> dict[str, Any]:
        """Walk away from a negotiation with a supplier.

        Args:
            supplier_id: The supplier to reject.
            reason: Why the agent is walking away.

        Returns:
            Confirmation of rejection.
        """
        session_manager.reject_supplier(supplier_id, reason)

        return {
            "rejected": True,
            "supplier_id": supplier_id,
            "reason": reason,
        }

    @tool
    def lock_escrow(supplier_id: str) -> dict[str, Any]:
        """Lock USDC funds in the Algorand escrow contract.

        This is the final step after accepting a supplier's offer.
        USDC is 1:1 with USD — no conversion needed.
        Locks the USDC in the smart contract and anchors the deal hash on-chain.

        Args:
            supplier_id: The winning supplier whose deal to lock.

        Returns:
            Deal details including transaction ID, deal hash, and amounts.
        """
        state = session_manager.context.negotiations.get(supplier_id)
        if not state or not state.best_offer:
            return {"error": f"No accepted offer from supplier {supplier_id}"}

        terms = state.best_offer
        total_usd = terms.total_usd()
        total_usdc = total_usd  # 1:1 with USD

        # Calculate deadline timestamp
        deadline_str = session_manager.context.request.deadline
        try:
            deadline_dt = datetime.fromisoformat(deadline_str)
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
            deadline_ts = int(deadline_dt.timestamp())
        except (ValueError, TypeError):
            deadline_ts = int(time.time()) + (terms.delivery_days * 86400) + (7 * 86400)

        EventBus.emit("agent_thinking", {
            "thought": (
                f"Locking ${total_usd:.2f} USDC in escrow (1:1 with USD). "
                f"Settlement via USDC on Algorand."
            ),
        })

        from tools.sign_escrow import sign_escrow

        result = sign_escrow(
            rfq_id=state.rfq_id,
            supplier_id=supplier_id,
            item=session_manager.context.request.item,
            quantity=terms.quantity,
            unit_price=terms.unit_price_usd,  # USD/USDC 1:1
            delivery_days=terms.delivery_days,
            warranty_yrs=terms.warranty_yrs,
            buyer_agent_id=session_manager.context.buyer_agent_id,
            budget=session_manager.context.request.budget_usd,
            deadline_ts=deadline_ts,
        )

        # Update context
        session_manager.context.deal_id = result.deal_id
        session_manager.context.deal_phase = session_manager.context.deal_phase.ESCROW_LOCKED

        # Update deal record with USD info
        try:
            import sqlite3
            conn = sqlite3.connect(DATABASE_PATH)
            conn.execute(
                "UPDATE deals SET amount_usd = ?, usd_to_algo_rate = ? WHERE deal_id = ?",
                (total_usd, 1.0, result.deal_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to update deal with USD info", extra={"error": str(e)})

        EventBus.emit("escrow_locked", {
            "deal_id": result.deal_id,
            "txid": result.txid,
            "confirmed_round": result.confirmed_round,
            "amount_usd": total_usd,
            "amount_usdc": total_usdc,
            "deal_hash": result.deal_hash,
            "app_id": result.app_id,
        })

        return {
            "deal_id": result.deal_id,
            "txid": result.txid,
            "confirmed_round": result.confirmed_round,
            "amount_usd": total_usd,
            "amount_usdc": total_usdc,
            "deal_hash": result.deal_hash,
            "escrow_address": result.escrow_address,
            "app_id": result.app_id,
            "status": result.status,
        }

    @tool
    def get_negotiation_status() -> dict[str, Any]:
        """Get the current state of all active negotiations.

        Returns:
            Dict with deal phase and per-supplier negotiation status.
        """
        return session_manager.get_status()

    return [
        discover_suppliers,
        request_quotes,
        evaluate_quotes,
        send_counter_offer,
        accept_offer,
        reject_supplier,
        lock_escrow,
        get_negotiation_status,
    ]
