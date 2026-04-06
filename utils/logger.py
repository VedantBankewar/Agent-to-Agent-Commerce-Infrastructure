"""
Structured logging for AgentTrade.
All agent reasoning traces and tool calls are logged here.
Never log sensitive data (private keys, mnemonics, API keys).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Log levels
# ---------------------------------------------------------------------------

DEBUG = logging.DEBUG    # Detail: tool args, intermediate states
INFO  = logging.INFO     # Progress: step completions, transaction IDs
WARNING = logging.WARNING # Recoverable: Redis unavailable, quote timeout
ERROR   = logging.ERROR  # Must investigate: API failures, contract errors


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class AgentTradeFormatter(logging.Formatter):
    """Formatter that adds ISO timestamp and level."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        # Ensure timestamp is always UTC
        if record.created:
            record.created = datetime.fromtimestamp(record.created, tz=timezone.utc).timestamp()
        return super().format(record)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    """
    Return a configured logger. Creates handlers if needed.

    Args:
        name: Logger name (use __name__ of the calling module).
        log_file: Optional path to a log file. If None, uses logs/{name}.log
                  under the project root.
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Console handler — INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(AgentTradeFormatter())
    logger.addHandler(console)

    # File handler — DEBUG and above
    if log_file is None:
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / f"{name.replace('.', '_')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(AgentTradeFormatter())
    logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


# ---------------------------------------------------------------------------
# Convenience helpers for agent tool logging
# ---------------------------------------------------------------------------

def log_tool_call(
    logger: logging.Logger,
    tool_name: str,
    args: dict[str, Any],
    result: Any = None,
) -> None:
    """Log a tool call with its arguments and result at DEBUG level."""
    # Scrub sensitive values
    safe_args = _scrub_args(args)
    if result is not None:
        logger.debug("TOOL_CALL tool=%s args=%s result_type=%s", tool_name, safe_args, type(result).__name__)
    else:
        logger.debug("TOOL_CALL tool=%s args=%s", tool_name, safe_args)


def log_agent_thought(logger: logging.Logger, thought: str) -> None:
    """Log an agent reasoning step at DEBUG level."""
    logger.debug("THOUGHT %s", thought)


def log_txn(logger: logging.Logger, message: str, **extra: Any) -> None:
    """Log an Algorand transaction event at INFO level."""
    logger.info("TXN %s", message, extra=extra)


def _scrub_args(args: dict[str, Any]) -> dict[str, Any]:
    """Remove potentially sensitive values from args before logging."""
    sensitive_keys = {"private_key", "mnemonic", "secret", "api_key", "token", "password"}
    return {
        k: ("***SCRUBBED***" if k.lower() in sensitive_keys else v)
        for k, v in args.items()
    }
