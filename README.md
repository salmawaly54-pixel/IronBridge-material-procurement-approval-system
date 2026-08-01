# IronBridge-material-procurement-system
AI + MCP-powered procurement workflow system for Ironbridge Construction Company, automating material requests, approvals, supplier coordination, and construction procurement management.
# IronBridge Construction — Procurement Assistant MCP Server

## The company & the problem

IronBridge Construction runs multiple active job sites at once. Today,
getting materials to a site works like this: a site engineer submits a
request, a procurement officer manually checks warehouse stock, a
project manager reviews and approves anything expensive, finance
checks whether the project's budget can absorb it, and a warehouse
team physically releases the material — five people, mostly by phone
and email, for every non-trivial order. It's slow, and nobody has a
single consistent record of who approved what, under which policy.

IronBridge wants an AI assistant that can answer inventory, budget, and
equipment questions instantly and even submit requests on a site
engineer's behalf — but the same governance rules that exist today have
to survive the move to an assistant, not get silently skipped:

- **Expensive purchases must always require human approval.**
- **Requests that exceed project budget limits must be escalated to
  management** — never auto-approved by cost tuning alone.
- **Low-stock situations must follow company approval workflows.**
- **Sensitive financial and employee data must remain protected** — the
  assistant never gets raw database access; it only gets scoped tools.

This is why every protocol concern in this lab has a genuine reason to
exist here:

- **"Expensive purchases must always require human approval"** → a real
  elicitation trigger on `approve_purchase_request` (over $10,000).
- **"Requests that exceed budget must be escalated"** → a hard
  validation block (not elicitation — a number can't talk its way past
  this) that redirects to a separate `escalate_purchase_request` tool.
- **"Low-stock situations must follow approval workflows"** → a second,
  independent elicitation trigger on `reserve_material`.
- **Five different roles, most of the workforce read-only, a few
  write-capable** → notifications (tool set changes on login) and
  capability negotiation.
- **The safety/handling rules referenced above are read-once reference
  material, not a lookup with parameters** → resources.
- **Every site engineer eventually has to justify an expensive
  request** → a reusable prompt template.
- **Multiple sites/departments, not one laptop** → transport.
- **Turning a pile of purchase-request records into an actual report is
  a reasoning task** → sampling.
- **A report over many requests genuinely takes a while** → progress
  tracking.

Built on the official `mcp` Python SDK's **FastMCP** API for tool/
resource/prompt registration. One deliberate exception, documented at
the top of `mcp_server/server.py`: FastMCP's own `mcp.run()` declares
`tools.listChanged=False` by default, which would break the
Notifications concern, so `main()` drives the same underlying low-level
`Server` object (`mcp._mcp_server`) directly with the right
`NotificationOptions`. Everything else — tools, resources, prompts,
elicitation, sampling, progress — uses FastMCP's decorators and
`Context` object normally.

## Database & ERD

Engine: **SQLite** (`db/procurement.db`, built from `db/schema.sql` +
`db/seed.sql`). The schema follows the entities and fields given in the
problem statement exactly, with **one addition**: `Employees.PinHash`.
The original spec has no authentication mechanism, but the lab requires
a genuine role-elevation flow to justify the Notifications concern
(different staff seeing different tool sets), so a PIN-based login was
added for the assistant session only — never used anywhere else, and
never returned by any read tool.

```
Projects ──< Employees (assigned)         Employees ──< Projects (ProjectManagerID)
Projects ──< PurchaseRequests >── MaterialInventory
Employees ──< PurchaseRequests
Employees ──< AuditLog
```

`Suppliers`, `Equipment`, and `SafetyPolicies` stand alone (no FK into
the request flow) — `Suppliers` isn't used by any tool in this lab
(procurement's supplier relationships weren't in scope for the
assistant), `Equipment` backs `track_equipment_availability`, and
`SafetyPolicies` backs the two resource documents.

Full ERD source: `db/erd.mmd` (Mermaid — paste into
[mermaid.live](https://mermaid.live) or view directly on GitHub).

Seed data (`db/seed.sql`) deliberately includes edge cases the write
tools must handle: request 3 is already `Rejected`, request 4 is already
`Completed`, request 2 is both over the $10k elicitation threshold *and*
over Project 1's remaining budget (to prove the budget block fires
before elicitation would even be considered), and the Reinforcement
Steel material starts **already below** its minimum stock level.

## How each protocol concern shows up (and where to find it)

Every section in `mcp_server/server.py` is tagged with a comment
starting `# === CONCERN: ... ===`.

| Concern | Where | What triggers it |
|---|---|---|
| **Capability negotiation** | `server.py: make_init_options()` | Server declares `tools.listChanged=True`; `agent/client.py: CapabilityGate` checks declared capabilities before relying on them |
| **Notifications** | `server.py: list_tools()`, `_authenticate_as_approver()` | Session starts able to see read tools + `create_purchase_request`; a successful `authenticate_as_approver` call sets `SESSION["employee"]` and pushes `send_tool_list_changed()` — three approver tools appear, no reconnect |
| **Elicitation (×2 genuine triggers)** | `server.py: _approve_purchase_request()`, `_reserve_material()` | (1) `EstimatedCost` > $10,000 → confirm the purchase. (2) A reservation that would drop stock below `MinimumStockLevel` → confirm the low-stock release. Independent triggers, independent policy reasons |
| **Resources** | `server.py: list_resources()/read_resource()`, `mcp_server/policies/*.md` | Material Handling Procedures and Warehouse Safety Regulations are read once via `resources/read`, not re-fetched per question |
| **Prompts** | `server.py: list_prompts()/get_prompt()` | `draft_purchase_justification` — parameterized starting point every site engineer needs before submitting an expensive request |
| **Transport** | `server.py: main()`, `mcp_server/http_app.py` | `TRANSPORT=stdio` (dev) vs `TRANSPORT=http` (Streamable HTTP, production) — same server code either way |
| **Progress tracking** | `server.py: _generate_procurement_report()` | Iterates every purchase request in a date range, sending `send_progress_notification` after each, before the sampling call even starts |
| **Sampling** | `server.py: _generate_procurement_report()` | After collecting raw records, calls `ctx.session.create_message(...)` — the **client's** model writes the narrative, not a server-side template |
| **Defensive tool design** | `server.py: _approve_purchase_request()`, `_reserve_material()`; `validation.py` | Typed JSON Schemas, `required` + `additionalProperties: false`; server-side validation (`validate_within_budget`, `validate_sufficient_stock`, `validate_request_pending/approved`) independent of the schema; handler-level authorization (`require_role`, `require_project_scope`) checked per-action, not just per-tool-visibility |

## Transport rationale

A single site could run this over stdio. IronBridge is not a single
site: site engineers, procurement, finance, and warehouse staff are in
different departments and often different locations. **What we
actually built**: both — `TRANSPORT=stdio` (default) for local dev,
`TRANSPORT=http` (Streamable HTTP, `mcp_server/http_app.py`, bearer
token from `IRONBRIDGE_API_TOKEN`) for production. Early development
used stdio exclusively; the HTTP path was added once the multi-role,
multi-location requirement was clear (see commit history).

## Comparison note: read-only vs. write, and capability fallback

| Tool | Read/Write | Requires elicitation? | Requires approver session? |
|---|---|---|---|
| `check_material_inventory` | read | no | no |
| `view_project_budget` | read | no | no |
| `track_equipment_availability` | read | no | no |
| `generate_procurement_report` | read (+ sampling) | no | no |
| `create_purchase_request` | **write** | no | no (open to any employee — matches "site engineers submit requests" in the problem statement) |
| `authenticate_as_approver` | — (session state) | no | no |
| `approve_purchase_request` | **write** | **yes, if EstimatedCost > $10,000** (and hard-blocked, not elicited, if over remaining budget) | **yes** (Project Manager or Finance Officer) |
| `escalate_purchase_request` | **write** | no | **yes** (Project Manager or Finance Officer) |
| `reserve_material` | **write** | **yes, if it would breach MinimumStockLevel** | **yes** (Warehouse Supervisor) |

**Note on `create_purchase_request` being open:** the problem statement
has site engineers *submitting* requests as their normal job, with
*approval* as the separate, gated step — so submission itself isn't
treated as the risky action here. If IronBridge wanted to restrict who
can submit on a project's behalf, `require_project_scope` in
`validation.py` is the seam to add that check.

**If a client connects without elicitation support:**
`approve_purchase_request` and `reserve_material` would hang on a
response the client can never send. A capability-aware host should
check its own configured capabilities before ever offering these tools
and instead surface "this action requires human confirmation, which
this client doesn't support" — same idea as `CapabilityGate` in
`agent/client.py`, extended to gate tool exposure, not just log a
capability check.

**If a client connects without sampling support:**
`generate_procurement_report` would fail on `create_message`. A
capability-aware client should fall back to returning the raw JSON
records without the narrative summary.


## What we'd still worry about in production

- **Auth is a stand-in.** PIN-over-a-tool-call is fine for a lab demo;
  production needs a real identity provider and the HTTP transport's
  bearer-token check replaced with proper session-scoped auth.
- **Sampling/elicitation callbacks are stand-ins** (`agent/client.py`'s
  `fake_model_reply` and the `input()`-based confirmation) — a real host
  app wires these to an actual model and an actual UI.
- **Single in-process session state.** `SESSION` in `server.py` is a
  module-level dict, fine for one connection at a time in a lab demo; a
  real multi-user HTTP deployment needs this keyed per transport
  session, not global.
- **`create_purchase_request` doesn't check the requester's project
  scope.** A real deployment should verify the submitting employee
  actually belongs to the project they're requesting against.
- **What we'd try next:** move `SESSION` to a proper per-connection
  store, wire `Suppliers` into a real reorder-suggestion tool, and add a
  `subscribe`d resource for live budget status instead of polling
  `view_project_budget`.
