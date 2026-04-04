# Coding Standards — AgentTrade

## Python Style

- Follow PEP 8
- Use `typing` module for all function signatures
- Use `dataclass` or `TypedDict` for structured data (quotes, RFQs, agreements)
- Use `datetime.utcnow()` for all timestamps
- No bare `except:` — always catch specific exceptions
- No `print()` for debugging — use the logger

## Imports

- Standard library first, then third-party, then local
- Never import from `.venv` directly
- Group imports: `import X`, `from Y import Z`

## Naming

- `snake_case` for functions, variables, file names
- `SCREAMING_SNAKE_CASE` for constants
- `PascalCase` for classes and dataclasses
- Prefix private methods with `_`

## File Organization

- One module per file for tools (`tools/search_suppliers.py`)
- Keep modules focused — don't bundle unrelated tools
- Max ~300 lines per file — split if larger

## Error Handling

- Always validate inputs at function entry
- Return error results as typed responses, not exceptions (for agent-facing tools)
- Log errors with context before propagating
- Never swallow exceptions silently

## Security

- Never log or print private keys, mnemonics, or API keys
- Store secrets in `.env` — never in source code
- Validate Algorand address format before using
- Validate amounts are positive integers (microALGO)
- Sanitize all user input in FastAPI endpoints

## Documentation

- Every module has a docstring describing its purpose
- Every public function has a docstring with args and return type
- Complex logic has inline comments explaining the why, not the what
- Keep docs in sync with code — stale docs are worse than no docs

## Logging

- Use `utils/logger.py` — structured logging only
- Log levels: DEBUG (detail), INFO (progress), WARNING (recoverable), ERROR (must investigate)
- Include context: `logger.info("Escrow locked", extra={"rfq_id": rfq_id, "amount": amount})`
- Never log sensitive data (keys, secrets, personal info)
