# MCP & Odoo Integration Review

**Reviewed:** 2026-04-14
**Scope:** mcp/mcp_servidor_precios.py, services/mcp_budget.py, odoo_integration/odoo_api_wrapper.py, odoo_integration/odoo_mcp_server.py, scripts/odoo_setup.py

---

## mcp/mcp_servidor_precios.py

### Purpose

Simulated (mock) MCP server that exposes product catalog and quoting logic using in-memory hardcoded data. Intended as a stable interface placeholder until replaced by the real Odoo-backed server (`odoo_mcp_server.py`). Communicates via stdio transport. No external dependencies.

### MCP Tools Exposed

| Tool name | Description | Input | Output |
|---|---|---|---|
| `list_catalog` | Returns full product catalog | none | `dict[str, dict]` — keyed by product code |
| `get_product` | Returns single product detail | `product_code: str` | `dict` with name, price, description; raises `ValueError` if not found |
| `get_customer_profile` | Returns commercial profile for a company | `company_name: str` | `dict` with segment, discount_pct, currency; returns safe defaults for unknown clients |
| `calculate_quote` | Calculates subtotal, discount, and total for a list of modules | `product_codes: list[str]`, `company_name: str` | `dict` with lines, subtotal, discount_pct, discount_amount, total, currency, segment |

### Issues

- **LOW** — `calculate_quote` silently skips unknown product codes (`continue`) without any warning in the returned payload. Callers cannot detect partial failures.
- **LOW** — CATALOGO and CLIENTES are module-level mutable dicts. No real risk here (single process, no writes), but should be declared as constants (e.g. uppercase + type annotation) to signal intent.
- **LOW** — No `if __name__ == "__main__"` guard on `mcp.run()` prevents use as an importable module without side effects during tests.

---

## services/mcp_budget.py

### Purpose

Async service layer that bridges the budget agent with the MCP server. Builds a `MultiServerMCPClient`, opens a session to the `odoo_budget` server (the mock or real MCP server), invokes two tools (`get_customer_profile`, `calculate_quote`), and returns a unified dict for the agent to use.

### Issues

- **HIGH** — A new MCP subprocess is spawned on every call to `get_budget_context`. There is no connection pooling or reuse. Under any non-trivial load this is wasteful and slow, and spawning a child process per LLM turn may cause race conditions in async contexts.
- **HIGH** — Only two of the four tools exposed by the MCP server (`get_customer_profile`, `calculate_quote`) are used. `list_catalog` and `get_product` are never called. If an agent needs product detail or catalog listing it has no path to get it through this service.
- **MEDIUM** — `_parse_mcp_result` handles `dict` and `list[dict]` but silently falls through to a hard `ValueError` for any other shape. If the MCP protocol or library version changes response format, this gives an opaque error with no guidance.
- **MEDIUM** — No timeout is set on the MCP session. A hung child process will block the async event loop indefinitely.
- **MEDIUM** — `_build_client` checks only for the server file path existence; it does not validate that the file is executable or that `sys.executable` is available, making error messages at runtime confusing.
- **LOW** — Class has no `__init__` and no state; could be a module-level function or a set of free functions. Wrapping in a class without injecting dependencies offers no testing benefit.
- **LOW** — The comment block at the top of the class body (lines 11–15) belongs in a docstring.
- **LOW** — `print()` used nowhere, but `logging` is also absent. Any errors surface only as exceptions with no diagnostic trail.

---

## odoo_integration/odoo_api_wrapper.py

### Purpose

Synchronous XML-RPC wrapper around a live Odoo instance. Handles authentication at construction time and exposes CRUD operations for `product.product`, `res.partner`, `helpdesk.ticket`, generic `search`/`search_read`, and a destructive `drop_model` utility. Also includes lookup helpers for helpdesk metadata (teams, ticket types, categories, tags, motives).

### Odoo Operations

| Function | Odoo model | Method | Purpose |
|---|---|---|---|
| `_login` | — | `common.authenticate` | Authenticate and obtain UID |
| `get_dbs` | — | `db.list` | List available databases |
| `get_all` | any | `search_read` | Generic fetch up to `limit` records |
| `get_products` | `product.product` | `search_read` | Active products |
| `create_product` | `product.product` | `create` | Create product |
| `get_product` | `product.product` | `read` | Single product by ID |
| `update_product` | `product.product` | `write` | Update product fields |
| `delete_product` | `product.product` | `unlink` | Delete product |
| `get_contacts` | `res.partner` | `search_read` | Active contacts |
| `create_contact` | `res.partner` | `create` | Create contact |
| `get_contact` | `res.partner` | `read` | Single contact by ID |
| `update_contact` | `res.partner` | `write` | Update contact |
| `delete_contact` | `res.partner` | `unlink` | Delete contact |
| `install_module` | `ir.module.module` | `search` + `button_immediate_install` | Install an Odoo module |
| `search` | any | `search` | Return IDs matching domain |
| `search_read` | any | `search_read` | Return records matching domain |
| `drop_model` | any | `unlink` (batched) | **Delete all records** in any model |
| `get_team_id_by_name` | `helpdesk.ticket.team` | `search` | Resolve team name to ID |
| `get_ticket_type_id_by_name` | `helpdesk.ticket.type` | `search` | Resolve ticket type to ID |
| `get_category_id_by_name` | `helpdesk.ticket.category` | `search` | Resolve category to ID |
| `get_tag_ids_by_names` | `helpdesk.ticket.tag` | `search` | Resolve tag names to IDs |
| `get_motive_id_by_name_and_team` | `helpdesk.ticket.motive` | `search` | Resolve motive to ID |
| `create_helpdesk_ticket` | `helpdesk.ticket` | `create` | Create helpdesk ticket |
| `get_helpdesk_ticket` | `helpdesk.ticket` | `read` | Single ticket by ID |
| `get_helpdesk_tickets` | `helpdesk.ticket` | `search` + `read` | All tickets up to limit |

### Credentials Handling

- Credentials (`url`, `username`, `password`, `db`) are passed as constructor arguments.
- `odoo_setup.py` and the test suite pull them from `shared.config` (which presumably reads from environment variables or a `.env` file — this is not visible in the reviewed files but is the correct pattern).
- The raw `password` string is stored as `self._password` and is passed on every subsequent `execute_kw` call for the lifetime of the object. This is standard Odoo XML-RPC behavior but means the password lives in process memory for the session duration.

### Issues

- **CRITICAL** — `drop_model` deletes **all records** in any model passed to it with no confirmation, no dry-run, no access control check, and no logging. Calling `odoo.drop_model("sale.order")` in production would be catastrophic. This function should be removed or gated behind an explicit `confirm=True` flag and restricted to dev/test environments only.
- **HIGH** — `_format` URL normalization is fragile: `pieces[2][:4]` hard-codes that the port is exactly 4 characters (e.g. `8069`). A port like `80`, `443`, or `10069` would silently corrupt the URL, causing an obscure `xmlrpc` connection error.
- **HIGH** — No type annotations on any method signature, making static analysis and IDE assistance ineffective across the codebase.
- **HIGH** — `get_helpdesk_tickets` issues two separate XML-RPC calls (`search` then `read`) instead of a single `search_read`, doubling the network round-trips for a very common operation.
- **MEDIUM** — `get_dbs` uses `print()` for output and silently swallows exceptions. Should use `logging` and re-raise or return a typed result.
- **MEDIUM** — `install_module` calls `self.search(...)` (correct) but the class method name shadows the XML-RPC method name in a confusing way; the search result is also never validated before being passed to `button_immediate_install`.
- **MEDIUM** — There is a syntax indentation issue at line 100: the `# helpers helpdesk` comment and everything below it appears to be at class body level but is placed after `drop_model` without proper indentation alignment (visible as top-level comment at column 0 inside the class). This is a style issue that could confuse linters.
- **LOW** — `_login` error message contains informal text (`"don't give up ur close!"`). Should be a clean, machine-readable message.
- **LOW** — No `fields` parameter on `get_helpdesk_tickets` / `get_helpdesk_ticket` reads; Odoo will return all fields, which is wasteful over XML-RPC.
- **LOW** — Password is stored in plaintext in `self._password` and logged in tracebacks if an exception occurs inside `execute_kw`. Consider redacting in `__repr__`/`__str__` if added.

---

## odoo_integration/odoo_mcp_server.py

### Purpose

Production MCP server that mirrors the tool interface of `mcp_servidor_precios.py` but fetches real data from Odoo via XML-RPC. Additionally, `calculate_quote` creates a real `sale.order` in Odoo as a side effect.

### MCP Tools Exposed

| Tool name | Description | Input | Output |
|---|---|---|---|
| `list_catalog` | Returns catalog from Odoo `product.product` filtered by known `default_code` values | none | `dict[str, dict]` keyed by product code |
| `get_product` | Delegates to `list_catalog` and filters | `product_code: str` | `dict` with name, price, description; raises `ValueError` if not found |
| `get_customer_profile` | Looks up `res.partner` by name; returns segment/discount by hardcoded name matching | `company_name: str` | `dict` with segment, discount_pct, currency |
| `calculate_quote` | Builds sale order lines, creates `sale.order` in Odoo, returns quote summary | `product_codes: list[str]`, `company_name: str` | `dict` with lines, subtotal, discount_pct, discount_amount, total, currency, segment |

### Issues

- **CRITICAL** — Credentials are hardcoded as module-level constants (`URL`, `DB`, `USERNAME`, `PASSWORD` all set to `"admin"`/`"http://localhost:8069"`). These must come from environment variables. This is a security violation that also makes the server non-deployable outside a specific local machine.
- **CRITICAL** — `_get_odoo_connection()` creates a brand new XML-RPC connection and authenticates on **every tool call**. With `calculate_quote` calling `get_customer_profile` (1 auth), then `execute` for partner search (1 auth), then `execute` per product code (N auths), a 5-product quote triggers ~8 full authentication round-trips. This is both a performance and a reliability problem.
- **HIGH** — `get_customer_profile` determines segment and discount by string-matching the partner name against `'ACME'` and `'MEGACORP'` with hardcoded `if/elif` branches. All other real Odoo customers receive `segment='standard'` with 0% discount regardless of any Odoo data. The mock and the real server behave differently for unknown customers (`"desconocido"` vs `"standard"`), breaking contract parity.
- **HIGH** — `calculate_quote` creates a `sale.order` as a side effect of what callers expect to be a read/calculate operation. This means every time the budget agent asks for a quote preview, it creates a real order in Odoo. There is no `confirm_order` flag or separate `create_sale_order` tool.
- **HIGH** — `calculate_quote` returns the quote dict even when `order_lines` is empty (no valid products found), but `so_id` is never assigned. If the agent tries to reference `so_id` later it will get a `NameError`. The `so_id` is also not included in the returned dict at all, so callers cannot link back to the created order.
- **MEDIUM** — `get_product` calls `list_catalog()` which triggers a full Odoo query just to look up one product. A direct `search_read` with `default_code = product_code` would be more efficient.
- **MEDIUM** — The `execute` helper is a module-level function with a short generic name. It will shadow any other `execute` import and is easy to accidentally call without the right Odoo context.
- **MEDIUM** — No error handling around any `execute` calls. An Odoo downtime or XML-RPC fault will surface as an unhandled exception with no context for the MCP client.
- **MEDIUM** — `list_catalog` uses a hardcoded `default_code` whitelist. Adding a new product requires a code change in two places (here and in the mock). Should be driven by a product category or a tag in Odoo instead.
- **LOW** — `description` field from Odoo `product.product` may be HTML (Odoo stores it as an HTML field). Returning raw HTML to the agent without stripping tags may produce noisy text in LLM prompts.
- **LOW** — No `if __name__ == "__main__"` guard already present — actually it is present at line 136. No issue.

---

## scripts/odoo_setup.py

### Purpose

One-time (idempotent) seed script that installs required Odoo modules, creates the 5 service products (if they do not already exist), and creates 2 test customer contacts. Reads credentials from `shared.config`. Intended to be run once against a fresh Odoo instance.

### Issues

- **HIGH** — Module installation via `odoo.install_module(m)` calls `OdooAPIWrapper.install_module`, which calls `self.search('ir.module.module', ...)` before `button_immediate_install`. This is a synchronous blocking call that on a real Odoo instance can take minutes. There is no timeout, progress feedback, or error handling. A failure mid-list leaves the instance in a partially configured state with no indication of which modules succeeded.
- **MEDIUM** — Uses a list comprehension `[odoo.install_module(m) for m in MODULES]` purely for side effects. This is a Python anti-pattern; a `for` loop is the correct and more readable construct here.
- **MEDIUM** — Product idempotency check uses `default_code` to detect duplicates, which is correct. Contact idempotency uses exact `name` match, which is case-sensitive and will create duplicates if the name casing differs between runs.
- **MEDIUM** — No logging or print output. Running the script gives zero feedback about what was installed or created, making debugging failures impossible without attaching a debugger.
- **LOW** — `MODULES` includes `'base'` which is always installed in every Odoo instance. Attempting to install it again is harmless but unnecessary noise.
- **LOW** — Script body is not wrapped in a function; all logic runs at import time (inside `if __name__ == "__main__"` but still at module scope). Extract into a `def main()` function for testability.

---

## Issues Summary

### CRITICAL
1. `odoo_mcp_server.py` — Hardcoded credentials (`admin`/`admin`, localhost URL) at module level. Must use environment variables.
2. `odoo_mcp_server.py` — A new Odoo auth session is created on every tool invocation, causing N×8 round-trips for a single quote.
3. `odoo_api_wrapper.py` — `drop_model()` deletes all records in any model with no guard. Catastrophic if called on production data.

### HIGH
4. `odoo_mcp_server.py` — `calculate_quote` creates a real `sale.order` as a side effect of a "calculate" operation with no opt-in flag.
5. `odoo_mcp_server.py` — `so_id` undefined when `order_lines` is empty; not returned in output dict regardless.
6. `odoo_mcp_server.py` — Discount logic is hardcoded name matching, not read from Odoo data; breaks contract parity with mock server.
7. `odoo_api_wrapper.py` — `_format` port extraction is broken for ports other than 4 characters.
8. `odoo_api_wrapper.py` — No type annotations on any method.
9. `odoo_api_wrapper.py` — `get_helpdesk_tickets` uses two XML-RPC calls instead of one `search_read`.
10. `services/mcp_budget.py` — New subprocess spawned per call; no connection reuse or pool.
11. `services/mcp_budget.py` — Only 2 of 4 MCP tools consumed; catalog and product-detail tools are unreachable through the service layer.
12. `scripts/odoo_setup.py` — No error handling or feedback on module installation; partial failures are silent.

### MEDIUM
13. `odoo_mcp_server.py` — `get_product` triggers a full catalog fetch to look up one item.
14. `odoo_mcp_server.py` — `list_catalog` hardcoded product code whitelist duplicates the mock server's catalog.
15. `odoo_mcp_server.py` — No error handling around any XML-RPC calls.
16. `services/mcp_budget.py` — No timeout on MCP session; a hung child process blocks the event loop.
17. `services/mcp_budget.py` — Opaque `ValueError` from `_parse_mcp_result` on unexpected response shapes.
18. `odoo_api_wrapper.py` — `get_dbs` swallows exceptions silently; uses `print` instead of `logging`.
19. `scripts/odoo_setup.py` — List comprehension used for side effects (should be a `for` loop).
20. `scripts/odoo_setup.py` — Contact deduplication is case-sensitive; may create duplicate entries.
21. `scripts/odoo_setup.py` — No output feedback during execution.

### LOW
22. `mcp_servidor_precios.py` — Silently skips unknown product codes in `calculate_quote`; partial failures not surfaced.
23. `odoo_api_wrapper.py` — `_login` error message is informal/non-machine-readable.
24. `odoo_api_wrapper.py` — No `fields` restriction on helpdesk ticket reads; fetches all fields unnecessarily.
25. `odoo_mcp_server.py` — `description` from Odoo may be raw HTML; needs stripping before passing to LLM.
26. `services/mcp_budget.py` — No logging; errors surface only as bare exceptions.
27. `scripts/odoo_setup.py` — `'base'` module in install list is always already installed; harmless but unnecessary.
