# Tool SDK

Future developer-facing SDK for authoring new VEYRA tools against the
`ToolDefinition`/`ToolExecutor` contracts in `packages/contracts`, without
hand-writing registry boilerplate (schema validation helpers, risk-tier
lint checks, verification-strategy scaffolding).

Phase 1 ships the raw contracts and a hand-written example tool
(`services/local-api/app/services/bootstrap.py`) directly against them —
see docs/architecture/04-TOOL-ARCHITECTURE.md. This SDK package is a
placeholder for the ergonomic layer future tool authors will use once
there are enough real tools to justify one.
