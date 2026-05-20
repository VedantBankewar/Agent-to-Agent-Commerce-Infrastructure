"""Supplier implementations for AgentTrade v2.

Three supplier types, all implementing SupplierInterface:
    - RuleBotSupplier  — deterministic pricing + negotiation logic
    - LLMSupplier      — Claude/GPT-powered reasoning
    - HumanSupplier    — API/Redis adapter for human-in-the-loop
"""
