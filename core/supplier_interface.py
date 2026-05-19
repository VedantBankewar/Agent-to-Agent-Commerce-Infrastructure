"""Supplier interface ABC and registry for AgentTrade v2.

The buyer agent communicates through SupplierInterface only.
It never knows if the other side is a bot, an LLM, or a human.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import NegotiationMessage


class SupplierInterface(ABC):
    """Abstract base class for all supplier implementations.

    Implementations:
        - RuleBotSupplier  (deterministic pricing + negotiation logic)
        - LLMSupplier      (Claude/GPT-powered reasoning)
        - HumanSupplier    (API/Redis adapter, waits for human input)
    """

    supplier_id: str
    supplier_name: str

    @abstractmethod
    def receive_rfq(self, message: NegotiationMessage) -> NegotiationMessage:
        """Handle an incoming RFQ. Return a Quote message with proposed terms."""
        ...

    @abstractmethod
    def receive_counter(self, message: NegotiationMessage) -> NegotiationMessage:
        """Handle a counter-offer. Return accept/counter/reject with updated terms."""
        ...

    @abstractmethod
    def confirm_deal(self, message: NegotiationMessage) -> NegotiationMessage:
        """Acknowledge accepted deal. Return confirmation message."""
        ...


class SupplierRegistry:
    """Maps supplier_id to SupplierInterface implementation.

    Falls back to RuleBotSupplier for unregistered suppliers.
    """

    _suppliers: dict[str, SupplierInterface] = {}
    _default_factory: type | None = None

    @classmethod
    def register(cls, supplier_id: str, impl: SupplierInterface) -> None:
        """Register a supplier implementation."""
        cls._suppliers[supplier_id] = impl

    @classmethod
    def set_default_factory(cls, factory: type) -> None:
        """Set the default supplier class for unregistered suppliers.

        Args:
            factory: A class that accepts (supplier_id: str) and returns SupplierInterface.
        """
        cls._default_factory = factory

    @classmethod
    def get(cls, supplier_id: str) -> SupplierInterface:
        """Get supplier implementation, creating a default bot if unregistered.

        Args:
            supplier_id: The supplier to look up.

        Returns:
            The registered SupplierInterface implementation.

        Raises:
            ValueError: If supplier is not registered and no default factory is set.
        """
        if supplier_id in cls._suppliers:
            return cls._suppliers[supplier_id]

        if cls._default_factory is not None:
            impl = cls._default_factory(supplier_id)
            cls._suppliers[supplier_id] = impl
            return impl

        raise ValueError(
            f"Supplier '{supplier_id}' not registered and no default factory set. "
            "Call SupplierRegistry.set_default_factory(RuleBotSupplier) first."
        )

    @classmethod
    def all_registered(cls) -> dict[str, SupplierInterface]:
        """Return all registered supplier implementations."""
        return dict(cls._suppliers)

    @classmethod
    def clear(cls) -> None:
        """Remove all registered suppliers. Useful for testing."""
        cls._suppliers.clear()
        cls._default_factory = None
