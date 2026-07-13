"""Per-specialist-agent prompt assembly and tool schemas.

Splits `verbatim.prompt`'s single 4-category system prompt into one module
per specialist agent (`structural`, `line_editor`), each scoped to its own
category subset and tool. See `MULTI_AGENT_PLAN.md`.
"""
