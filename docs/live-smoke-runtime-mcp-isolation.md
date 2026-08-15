# Runtime MCP isolation for the negative-trigger smoke

The ordinary negative-trigger harness inventories configured MCP servers and
installed plugins before it starts its two authenticated model turns. Codex can
also contribute compatibility or extension MCP registrations at thread-runtime
construction time. Those registrations may not have a plugin ID and may not be
present in `config.toml`, so static inventory alone cannot disable them.

`python scripts/run_codex_negative_smoke_v4.py --confirm-live` adds a model-free
preflight before the established negative-trigger campaign:

1. Start an ephemeral app-server thread without a model turn.
2. Read the effective thread MCP inventory through `mcpServerStatus/list`.
3. Merge those names with the direct `config.toml` MCP names.
4. Apply every merged name as an explicit `mcp_servers.<name>.enabled=false`
   veto to both baseline and candidate sessions.
5. Delegate to the existing two-turn baseline-versus-core harness.

The probe writes
`preflight/runtime-mcp-inventory.json` inside the campaign directory. The file
records the direct names, runtime rows, final name-veto set, and `model_calls: 0`.
The normal `summary.json` and automatic failure diagnostics remain unchanged.

This is a maintainer qualification tool. Installing or using the published
skills does not require running this smoke campaign.
