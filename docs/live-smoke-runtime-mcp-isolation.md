# Runtime MCP isolation for the negative-trigger smoke

The ordinary negative-trigger harness inventories configured MCP servers and
installed plugins before it starts its two authenticated model turns. Codex can
also contribute compatibility or extension MCP registrations at thread-runtime
construction time. Those registrations may not have a plugin ID and may not be
present in `config.toml`, so static inventory alone cannot disable them.

`python scripts/run_codex_negative_smoke_v4.py --confirm-live` adds two
model-free preflights before the established negative-trigger campaign:

1. Start an ephemeral app-server thread without a model turn.
2. Read the effective thread MCP inventory through `mcpServerStatus/list`.
3. Merge those names with the direct `config.toml` MCP names.
4. Represent every merged name as a transport-complete disabled MCP row in the
   app-server startup layer. Codex requires `command` or `url` even when
   `enabled = false`; an inert placeholder command is retained only as
   structural metadata and is never launched.
5. Omit top-level MCP rows from the later thread/session configuration layer.
   A partial thread row such as `{ enabled = false }` replaces the complete
   startup row rather than extending it, which otherwise produces
   `invalid transport` during `thread/start`.
6. Start a second ephemeral thread and require the complete startup name veto to
   expose no tools before either authenticated model turn is allowed to begin.
7. Delegate to the existing two-turn baseline-versus-core harness using the
   same validated startup veto and the same startup-only thread policy.

The preflight writes
`preflight/runtime-mcp-inventory.json` inside the campaign directory. The file
records the direct names, runtime rows, transport-complete startup overrides,
that thread MCP overrides were omitted, veto-validation inventory, and
`model_calls: 0`.

The Codex MCP catalog intentionally preserves a disabled configured winner as a
name veto when a later compatibility or extension registration uses the same
logical server name. This harness relies on that supported catalog behavior
rather than guessing which hidden runtime component supplied the server.

This is a maintainer qualification tool. Installing or using the published
skills does not require running this smoke campaign.
