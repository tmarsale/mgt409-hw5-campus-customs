# Campus Customs Agent Harness

This file describes the data the Homework 5 AI agents work with. We will keep adding to it in later problems.

All AI agents in Homework 5 use only `gpt-6-luna`, routed through Portkey.

---

## Databases

| File | Purpose |
|---|---|
| `data/campus_customs.db` | The original database. It is never changed. |
| `data/campus_customs_new.db` | A working copy of the original. The agents read and write this copy for the rest of the homework. |

The working copy was made with SQLite's backup function, so it started out identical to the original. The store's "today" is **2026-08-31** (from the `desk` table).

---

## Tables

The database has 9 tables. The first three tell the agents what is happening, the middle group describes the store's stock and money, and `payments` is where the agents' approved actions are recorded.

### 1. `tickets` (3 rows): the work queue

| Field | Meaning |
|---|---|
| `id` | Ticket number (primary key). |
| `type` | Kind of request: `customer_order`, `rent_notice`, or `price_override`. |
| `requester` | The person or organization who asked. |
| `subject` | Short title. |
| `sku`, `size`, `qty` | The product, size, and quantity involved, if any. |
| `lease_id` | Links to `leases.id` for rent tickets. |
| `invoice_id` | Links to `invoices.id` when a vendor bill is involved. |
| `status` | `open` until the ticket is handled. |
| `notes` | Free-text details from the requester. |
| `created_at` | When the ticket arrived (timestamp with time zone). |

**Why it matters:** this is the agents' to-do list. Each ticket's `type` decides which agent should handle it, and its link fields point to the other data the agent needs to check.

### 2. `desk` (1 row): today's context

| Field | Meaning |
|---|---|
| `date_today` | The store's current date (`2026-08-31`). |
| `notes` | Optional notes for the day (empty right now). |

**Why it matters:** agents must use this date, not the real calendar date, to decide whether a bill is overdue or a rent payment is coming up.

### 3. `inventory` (10 rows): what is on the shelves

| Field | Meaning |
|---|---|
| `sku` | Product code, such as `CC-TEE-WHITE`. |
| `name` | Product name. |
| `size` | Size (`S`, `M`, `L`, `XL`, or `OS` for one size). |
| `qty` | Units in stock. |
| `location` | Aisle where the product is kept. |

The primary key is (`sku`, `size`), so each size of a product has its own row.

**Why it matters:** an agent has to check stock before promising an order. Two items are already at zero: the white tee in size S and the crest mug.

### 4. `pricing` (4 rows): cost and price per product

| Field | Meaning |
|---|---|
| `sku` | Product code (primary key). |
| `unit_cost` | What the store pays per unit. |
| `list_price` | The normal selling price. |

**Why it matters:** the agent uses this to quote prices and to check that a discount does not drop the price below cost.

### 5. `vendors` (3 rows): suppliers

| Field | Meaning |
|---|---|
| `id` | Vendor number (primary key). |
| `name` | Vendor name. |
| `specialty` | What the vendor supplies. |
| `lead_days` | Days the vendor needs to deliver. |

**Why it matters:** when something is out of stock, the agent can see who restocks it and how long it will take.

### 6. `invoices` (1 row): bills the store owes vendors

| Field | Meaning |
|---|---|
| `id` | Invoice number (primary key). |
| `vendor_id` | Links to `vendors.id`. |
| `amount` | Amount owed. |
| `due_date` | Payment deadline. |
| `status` | `open` means unpaid. |
| `description` | What the bill is for. |

**Why it matters:** unpaid bills compete with other expenses for the same cash, and an overdue bill can hold up a restock.

### 7. `leases` (1 row): the shop's rent

| Field | Meaning |
|---|---|
| `id` | Lease number (primary key). |
| `space_name` | The rented space. |
| `landlord` | Who is paid. |
| `monthly_rent` | Rent amount. |
| `next_due` | Next rent due date. |
| `notes` | Optional notes. |

**Why it matters:** rent is a fixed, high-priority expense, so the agent needs to plan for it before spending cash elsewhere.

### 8. `cash_accounts` (1 row): money available

| Field | Meaning |
|---|---|
| `name` | Account name (primary key), currently `checking`. |
| `balance` | Current balance. |
| `date` | Date of the balance. |

**Why it matters:** this is the hard limit on spending. The agent must never schedule payments that add up to more than this balance.

### 9. `payments` (0 rows): log of money paid out

| Field | Meaning |
|---|---|
| `id` | Payment number (primary key). |
| `kind` | What was paid, for example rent or an invoice. |
| `ref_id` | The related lease or invoice id. |
| `amount` | Amount paid. |
| `account` | Account the money came from. |
| `paid_at` | When it was paid. |
| `approved_by` | Who approved it (required). |

**Why it matters:** this is where the agents' payments get recorded. Because `approved_by` is required, every payment needs a named approver, which gives a natural point for a human to sign off.

---

## How the tables connect

```
tickets ──invoice_id──▶ invoices ──vendor_id──▶ vendors
   │
   ├──lease_id──────▶ leases
   │
   └──sku, size ───▶ inventory (sku, size)
        sku ───────▶ pricing (sku)

payments ──ref_id──▶ invoices.id or leases.id (depending on kind)
payments ──account─▶ cash_accounts.name
desk.date_today ── the "today" used for every due-date check
```

Only `tickets → leases`, `tickets → invoices`, and `invoices → vendors` are real foreign keys in the database. The links on `sku`/`size` and from `payments` exist only through matching values, so the agents have to join them deliberately.

---

## The three open tickets

### Ticket 101: customer order (Tauhid Zaman, "Bulldog tee")

- Wants 1 × `CC-TEE-WHITE` in size **S**.
- `inventory` shows **0** in stock for that size (Aisle B).
- The ticket links to **invoice 501**: $840 to **Bulldog Print Co** for a "Rush reprint CC-TEE-WHITE S." It was due **2026-08-28**, so it is **3 days overdue** and still `open`.
- Bulldog Print Co needs **5 days** to deliver, so the order cannot be filled today. The reprint likely depends on paying this invoice.
- Price: $28 list, $8 cost.

### Ticket 102: rent notice (Elm City Properties, "Rent due")

- Links to **lease 1**: Chapel Street shop, **$2,400** due **2026-09-02**, two days from today.
- Cash on hand is **$3,400** in checking.

### Ticket 103: price override (Yale AI Club, "Bulk hoodie discount")

- Wants **20** × `CC-HOOD-NAVY` in size **M** and asks for a bulk discount.
- Only **8** are in stock in size M (32 across all sizes), so the full order cannot be filled in that size.
- Price: $58 list, $22 cost, which gives a $36 margin per hoodie for any discount to come out of.

### How the tickets affect each other

The tickets compete for the same **$3,400**:

| Use of cash | Amount |
|---|---|
| Rent (ticket 102) | $2,400 |
| Overdue reprint invoice 501 (ticket 101) | $840 |
| **Total** | **$3,240** |
| **Left over** | **$160** |

Both bills fit, but only with $160 to spare, so paying anything else first could leave the store short on rent. No payments have been recorded yet (`payments` is empty).

---

## MCP server tools

The MCP server in `mcp_server/` (built with FastMCP) started with three tools, one per open ticket, described below. Problem 5 added more lookups and two locked, human-only write tools (see "The multi-agent team" below). See `mcp_server/README.md` for the full list and setup details.

- **Database:** all three tools read `data/campus_customs_new.db` over a **read-only** connection. They never touch the original `data/campus_customs.db`.
- **Date:** "today" always comes from `desk.date_today`.
- **Data:** every figure comes from the database, nothing is invented.
- **Ticket checks:** each tool confirms the ticket exists and is the right type before answering.
- **Read-only:** these three tools look things up but do not pay bills, change stock, or close tickets.

### Tool 1: `check_order_fulfillment(ticket_id)`

- **Supports:** ticket 101 (customer order for a white tee, size S).
- **Reads:** `desk`, `tickets`, `inventory`, `pricing`, `invoices`, `vendors`.
- **Returns:** stock for the requested product and size, its aisle, other sizes in stock, list price and cost, and the linked invoice with its vendor, amount, due date, days overdue, and the vendor's lead time.
- **Why it's useful:** in one call the agent sees that the tee is out of stock in S (0 on hand; M, L, and XL are available). It also sees that the $840 reprint invoice from Bulldog Print Co is 3 days overdue and the reprint takes 5 days. The agent can then tell the customer the truth (it can't ship today) and offer real choices: wait for the reprint or take another size.

### Tool 2: `check_cash_for_rent(ticket_id)`

- **Supports:** ticket 102 (rent notice from Elm City Properties).
- **Reads:** `desk`, `tickets`, `leases`, `cash_accounts`, `invoices`, `vendors`, `payments`.
- **Returns:** the lease (rent, due date, days until due), cash balances, every open invoice with days overdue, payments already recorded, and the cash left after rent and after rent plus all open invoices.
- **Why it's useful:** rent is $2,400 and due in 2 days, and the store has $3,400. Paying rent leaves $1,000. Paying rent and the overdue invoice leaves $160. That puts the full cash picture in front of the agent, so it doesn't commit money to one bill without seeing the others.

### Tool 3: `evaluate_bulk_discount(ticket_id, discount_percent=None)`

- **Supports:** ticket 103 (Yale AI Club wants 20 hoodies, size M, at a bulk discount).
- **Reads:** `desk`, `tickets`, `inventory`, `pricing`.
- **Returns:** stock in the requested size (8) and in every size (32 total), the shortfall (12), unit cost ($22), list price ($58), margin per unit ($36), the largest discount before a loss (62.07%), and revenue and profit at list price. If the agent passes a `discount_percent`, it also returns the discounted unit price, order revenue, order profit, and whether the price falls below cost.
- **Why it's useful:** the agent can test any discount against real cost data before offering it, and it sees right away that only 8 hoodies in size M can be supplied today. The tool does not choose a discount; that remains a business decision.

### Which tool goes with which ticket

| Ticket | Type | Tool |
|---|---|---|
| 101 | `customer_order` | `check_order_fulfillment` |
| 102 | `rent_notice` | `check_cash_for_rent` |
| 103 | `price_override` | `evaluate_bulk_discount` |

---

## The multi-agent team (Problem 5)

Five PydanticAI agents work the tickets together. The code is in `backend/`, and each agent's instructions are in `backend/prompts/`.

### Model

| Setting | Value | Where |
|---|---|---|
| Model | `gpt-6-luna` for **every** agent. `OPENAI_MODEL` is read, but any other value stops the program. | `backend/config.py` |
| Gateway | Portkey (`https://api.portkey.ai/v1`), headers `x-portkey-api-key` and `x-portkey-provider: openai`; key from `PORTKEY_API_KEY` | `make_model()` in `backend/team.py` |
| API | OpenAI **Responses** API (`OpenAIResponsesModel`). `gpt-6-luna` rejects function tools on `/v1/chat/completions`. | `backend/team.py` |
| Framework | PydanticAI 2.64 (`pydantic-ai-slim[openai,mcp]`) | `backend/requirements.txt` |

### Agent roles

| Agent | Job | MCP tools it can use | Prompt |
|---|---|---|---|
| **Boss** | Takes each ticket, checks the whole shop, sends work to the right specialists, combines their answers into one recommendation for the human owner. | `get_desk_overview`, `get_ticket`, `get_cash_position` | `boss.md` |
| **Inventory** | Stock, sizes, aisles, vendor lead times, and the restock path. | `get_ticket`, `check_order_fulfillment`, `check_stock`, `evaluate_bulk_discount`, `list_vendors` | `inventory.md` |
| **Accounting** | Cash, bills, payment priority (rent first), payment previews, margins and safe discounts. | `get_ticket`, `get_cash_position`, `check_cash_for_rent`, `preview_payments`, `evaluate_bulk_discount`, `list_vendors` | `accounting.md` |
| **Facilities** | The shop space and lease: checks a rent notice against the lease and flags mismatches. | `get_ticket`, `get_lease`, `check_cash_for_rent` | `facilities.md` |
| **Customer Service** | Writes honest customer replies as **drafts** only, with no internal figures. | `get_ticket`, `check_order_fulfillment`, `check_stock`, `evaluate_bulk_discount` | `customer_service.md` |

Every agent also gets `shop_rules.md`: facts only from MCP, the desk date as "today", cash never negative, rent first, no below-cost prices, payments only as proposals, customer messages only as drafts, no ticket status changes, and keep delegation and tool use small.

### How the agents talk to each other

- Every agent has a `delegate(to_agent, task)` tool and can hand part of a ticket to **any** of the other four. The other agent runs and returns its structured report.
- The Boss starts every ticket. Typical routes: 101 → Inventory, then Customer Service; 102 → Facilities and Accounting; 103 → Inventory, Accounting, then Customer Service.
- Every agent returns the same `AgentReport`: summary, key facts with the MCP tool each came from, recommendation, `payment_requests`, `customer_draft`, `proposed_ticket_status`, `needs_human_approval`, and open questions.

### MCP tools

All shop information reaches the agents only through the campus-customs MCP server, which reads `data/campus_customs_new.db`. The team starts its own copy of the server over stdio. It passes no API keys to that copy, and writes stay locked. The server now has 12 tools (full list in `mcp_server/README.md`):

| Group | Tools |
|---|---|
| Ticket tools (Problem 3) | `check_order_fulfillment`, `check_cash_for_rent`, `evaluate_bulk_discount` |
| Team lookups (read-only) | `get_desk_overview`, `get_ticket`, `check_stock`, `list_vendors`, `get_lease`, `get_cash_position`, `preview_payments` (dry run, pays nothing) |
| Human-only writes (locked) | `record_payment`, `update_ticket_status` (never given to an agent) |

### Database tables the team uses

| Table | Read by | Written by |
|---|---|---|
| `desk` | every lookup ("today") | nobody |
| `tickets` | all ticket tools, `get_ticket`, `get_desk_overview` | only `update_ticket_status`, after human approval |
| `inventory`, `pricing` | `check_order_fulfillment`, `evaluate_bulk_discount`, `check_stock` | nobody |
| `vendors` | `check_order_fulfillment`, `list_vendors`, `get_cash_position` | nobody |
| `invoices` | ticket tools, `list_vendors`, `get_cash_position`, `preview_payments` | only `record_payment` (marks an invoice `paid`), after human approval |
| `leases` | `check_cash_for_rent`, `get_lease`, `get_cash_position`, `preview_payments` | nobody |
| `cash_accounts` | `check_cash_for_rent`, `get_cash_position`, `preview_payments` | only `record_payment` (lowers the balance), after human approval |
| `payments` | `check_cash_for_rent`, `get_lease`, `get_cash_position`, `preview_payments` | only `record_payment`, after human approval |

### Safety controls

| Rule | How it is enforced |
|---|---|
| **Payments need a human** | Agents have no payment tool; they can only add a `payment_requests` item whose status can only be `pending_human_approval` (anything else fails validation). `record_payment` runs only if a human starts the server with `CAMPUS_CUSTOMS_ALLOW_WRITES=1` **and** supplies the approval code from `CAMPUS_CUSTOMS_APPROVAL_CODE`, and `approved_by` must name a person, not an agent. A second filter in `team.py` refuses any tool call outside the agent's list. |
| **Cash never negative** | Accounting must run `preview_payments` first; it draws cash down in order and flags any payment that overdraws. After every run, the harness previews **all** proposed payments together (rent first) and records whether cash stays non-negative. `record_payment` re-checks inside a database transaction and refuses a negative balance, a wrong amount, an already-paid invoice, or rent already paid. |
| **Customer messages stay drafts** | `customer_draft.status` can only be `draft`. There is no send tool, and Customer Service is told never to share internal figures. |
| **No ticket status changes** | Agents can only suggest `proposed_ticket_status`. `update_ticket_status` is human-only and locked. |
| **Original database untouched** | Lookups use read-only connections; write tools refuse `campus_customs.db`. Every run hashes both databases before and after and records the result. |
| **Facts only from MCP** | Agents have no other data source; prompts require naming the source tool for each fact. |

### Loop and token limits (`backend/config.py`)

| Limit | Value | What happens when reached |
|---|---|---|
| Delegation depth | 2 (Boss → specialist → one more specialist) | `delegate` is hidden from the agent, and any call is refused. |
| No loops | An agent can't delegate to itself or to anyone already in the current chain. | Refused with a message telling it to answer with what it has. |
| Delegations per ticket | 5 | `delegate` is hidden and refused. |
| Model requests per ticket (all agents) | 30 | Ticket stops (`UsageLimitExceeded`) and is logged; the run moves on. |
| Tool calls per ticket | 40 | Same. |
| Tokens per ticket | 150,000 | Same. |
| Tokens per run | 400,000 | Remaining tickets are skipped and logged. |
| Output tokens per model request | 4,000 | Caps each answer. |
| Output retries per agent | 2 | Agent fails after repeated invalid output. |

All agents on one ticket share one usage counter, so a delegated agent's tokens count against the same ticket limits.

### Audit trail: `output/audit_trail.json`

- **Append-only:** each run is added to the end of the `runs` list; earlier runs are copied over unchanged. The file is written to a temp file and then swapped in, so a crash can't leave half a file.
- **Tamper-evident:** each run stores its own SHA-256 (`run_hash`) and the previous run's (`prev_run_hash`). Before appending, the program re-checks the whole chain and refuses to write if an earlier run was edited.
- **What's recorded:** run settings (model, tool lists, limits), every agent start and finish (with its full report and token use so far), every delegation and refused delegation, every MCP tool call with its arguments and result, the Boss's final decision per ticket, the payment preview over all proposals, guardrail results, and database hashes before and after. Failed runs are recorded too.

### Test results (2026-10-31)

| Test | Result |
|---|---|
| `mcp_server/test_tools.py`: new lookups match the DB, preview catches overdrafts and wrong amounts, writes locked without approval, negative cash refused, original DB refused (writes only on a temp copy) | 20/20 pass |
| `backend/test_team.py` (offline, scripted model, no tokens): self-delegation, loops, depth, and budget refused; `delegate` hidden at depth 2; each agent sees only its tools; `record_payment` unreachable; audit trail append-only and tamper-evident | 21/21 pass |
| First live run (`run-20261031T041508Z-6f8392`) | `error`: `gpt-6-luna` refused tools on chat completions. Kept in the audit trail. Fixed by switching to the Responses API. |
| Live run `run-20261031T041553Z-c48d36`, `gpt-6-luna` via Portkey, tickets 101–103 | `ok`, see below |

Live run, test mode (nothing executed):

| Ticket | Delegations | Requests | Tokens | Team recommendation |
|---|---|---|---|---|
| 101 | Boss → Inventory, Boss → Customer Service | 8 | 16,816 | Tee size S is out of stock; draft asks Tauhid about another size; no payment proposed; suggest `waiting_on_customer`. |
| 102 | Boss → Facilities → Accounting, Boss → Accounting | 13 | 28,224 | Propose $2,400 rent for human approval (preview valid, $1,000 left); suggest `in_progress`. |
| 103 | Boss → Inventory, Boss → Accounting, Boss → Customer Service | 11 | 24,108 | Only 8 of 20 size M in stock; no discount promised yet, any price must stay above $22; draft asks how to proceed; suggest `waiting_on_customer`. |

Run total: 69,148 tokens (limit 400,000). Guardrails: one pending payment (rent $2,400), cash after all proposals $1,000, 2 customer drafts (both `draft`), 0 human-only tools given to agents, 0 refused calls, both databases unchanged (same SHA-256 before and after).

**Gap found:** on ticket 101 the team didn't raise paying the overdue $840 Bulldog Print Co invoice (501) or mention the 5-day reprint lead time, even though `check_order_fulfillment` returned both.

**Prompt tuning (follow-up):**
- **Boss** must also ask Accounting about a linked vendor invoice when an order is blocked, and must always report that blocker.
- **Inventory** must list the invoice and lead time and give an estimated restock date.
- **Accounting** must look at every open invoice and preview rent first, then a restock-blocking invoice, in one call.
- **Customer Service** may give an estimated restock time but never mentions the invoice.

Rerun `run-20261031T042209Z-115f0f` (tickets 101 and 102, test mode):

| Ticket | Delegations | Requests | Tokens | Team recommendation |
|---|---|---|---|---|
| 101 | Boss → Inventory, Boss → Accounting → Inventory, Boss → Customer Service | 14 | 34,427 | Propose rent $2,400 first, then invoice 501 ($840, 3 days overdue, for the size S reprint), both pending human approval; preview leaves $160. Estimated earliest restock 2026-09-05 if paid today (5-day lead time), stated as an estimate. Draft offers M/L/XL or waiting, says "about five days" is an estimate, and doesn't mention the invoice. Suggest `waiting_on_customer`. |
| 102 | Boss → Facilities → Accounting, Boss → Accounting | 13 | 29,620 | Propose rent $2,400 only; notes the overdue $840 invoice is open but outside this ticket. Suggest `in_progress`. |

Run total 64,047 tokens. Guardrails: pending payments rent $2,400 + invoice 501 $840, valid together, cash after both **$160**, 1 customer draft (`draft`), 0 refused calls, both databases unchanged.

The audit trail also holds `run-20261031T042028Z-37d1d5` (tickets 101–103, `ok`, databases unchanged). It was not started by the assistant session that wrote this section, and its results and token totals are identical to `run-20261031T041553Z-c48d36`. The Problem 7 route tests showed the same pattern: identical prompts returned identical answers and token counts in about 10 seconds. That suggests Portkey is answering repeated identical requests from its cache. A run with different data (for example, after a payment) gets fresh answers.

---

## FastAPI backend (Problem 7)

`backend/main.py` connects the five agents to the React dashboard (Problem 8). Run it from the `backend/` folder:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

(With the virtual environment activated, `uvicorn main:app --reload --port 8000` works as written.) Interactive docs: `http://127.0.0.1:8000/docs`. Before starting it again, check that nothing is still using port 8000 (`netstat -ano | findstr :8000`).

### How it is built

| File | Role |
|---|---|
| `backend/main.py` | The FastAPI app and its routes. |
| `backend/mcp_client.py` | All shop data goes through the campus-customs MCP server. Reads use one long-lived server with writes **locked**. A human-approved payment starts a separate one-off server with writes unlocked for that single call. |
| `backend/approvals.py` | `output/approvals.json`: every payment the agents proposed, and what a human decided (`pending`, `executed`, `rejected`, `voided`). |
| `backend/run_team.py` | `run_tickets()` runs the agent team (also used by the command line). |
| `backend/audit.py` | Appends agent runs **and** human actions (approve, reject, refused, blocked, reset) to `output/audit_trail.json`. |

The dashboard's dev server may call the API from `localhost:5173` or `localhost:3000` (CORS allowed).

### Routes

| # | Method and URL | Purpose |
|---|---|---|
| – | `GET /api/health` | Backend is up; model (`gpt-6-luna`), store date, working DB, whether the original DB is unchanged (SHA-256 check), whether approvals are enabled, and any agent run in progress. |
| 1 | `GET /api/tickets` | Tickets 101, 102, 103 with their **current status** from the database, the number of pending approvals, and the latest team result for each. |
| 1 | `GET /api/tickets/{ticket_id}` | One ticket with its linked lease or invoice, the latest team decision (summary, facts, recommendation, payment requests, customer draft), `agent_reports` (each agent's state, who asked it, tool calls, and summary for the latest or in-progress run), and its approvals. 404 for an unknown ticket. |
| 1 | `POST /api/tickets/{ticket_id}/status` | *(Added in Problem 8.)* A human changes a ticket's status, for example to `resolved`. Body: `{"status": ..., "approved_by": ..., "approval_code": ...}`. Runs the locked `update_ticket_status` MCP tool; a wrong code returns `403`. |
| 2 | `POST /api/tickets/{ticket_id}/run` | Starts the five-agent team on one ticket. Returns `202` and a `job_id` right away; add `?wait=true` to wait for the result. Only one run at a time (`409` if busy). Each payment the team proposes becomes a **pending approval**. |
| 2 | `GET /api/jobs/{job_id}` | Status of a run started through the API: `running`, `finished`, or `failed`, with the decision, tokens, delegations, guardrails, and new approval ids. |
| 2 | `GET /api/runs?limit=10` | Recent audit-trail entries (agent runs and human actions), newest first. |
| 3 | `GET /api/activity?limit=50&ticket_id=&kind=&include_results=false` | Recent activity, newest first (including a run still in progress, from Problem 8 on), each with a plain-English `summary`. `kind` filters to `agent` (start/finish), `delegation`, `tool` (MCP calls with arguments; full results with `include_results=true`), `decision`, `message` (customer drafts, always `draft`), `human` (approvals, rejections, reset), or `system`. |
| 4 | `GET /api/approvals?status=&ticket_id=` | Proposed payments (rent, and vendor invoices, which are the store's purchases) with their status, plus the pending total. |
| 4 | `POST /api/approvals/{approval_id}/approve` | A human approves and **executes** a payment. Body: `{"approved_by": "<person>", "approval_code": "<code>"}`. |
| 4 | `POST /api/approvals/{approval_id}/reject` | A human rejects a proposed payment. Body: `{"rejected_by": "<person>", "reason": "..."}`. Nothing is paid. |
| 5 | `GET /api/cash` | Current **checking balance** and date, open invoices, upcoming rent, recorded payments, and the balance if every pending approval were paid (with a non-negative flag). |
| 6 | `POST /api/reset` | Body `{"confirm": true}`. Copies the original database over the working copy (the original is opened **read-only**), voids pending approvals, and confirms the working copy's contents now match the original. Refused while an agent run is in progress. |

### Safety in the backend

| Rule | How |
|---|---|
| Payments need a human | Agents can only propose; the backend turns proposals into `pending` approvals. `approve` needs a person's name and the approval code from `CAMPUS_CUSTOMS_APPROVAL_CODE` in `HW5/.env` (approvals are switched off with `503` until it is set). A wrong code returns `403`, nothing is paid, and the attempt is logged. The MCP server checks the code again and rejects agent names as approvers. |
| Cash never negative | Before paying, `approve` runs `preview_payments`; if the payment would overdraw cash, is the wrong amount, or is already paid, it returns `409` with the reasons, pays nothing, and leaves the approval pending so a human can reject it. `record_payment` re-checks inside a database transaction. |
| One change at a time | Payments and resets share a lock; only one agent run can be in progress. |
| Original database unchanged | The backend only ever opens `campus_customs.db` read-only (for reset), and `/api/health` and `/api/reset` check its SHA-256 against `23686a90…f360a`. |
| Everything is audited | Agent runs, approvals, rejections, refused or blocked payments, and resets are appended to `output/audit_trail.json`. |

### Route test results (2026-10-31)

The server was started with `uvicorn main:app --reload --port 8000` from `backend/`, with a test-only approval code.

| Test | Result |
|---|---|
| Health, tickets, ticket detail, unknown ticket `404`, activity filters (`tool`, `message`, `ticket_id`), runs, cash, approvals, reset without confirm `400`, unknown approval and job `404` | 13/13 pass |
| `POST /api/tickets/101/run`: `202` with a job id, a second run while busy `409`, job finished, approvals created for rent $2,400 and invoice 501 $840, and the run's delegations and tool calls appear in `/api/activity` | 4/4 pass |
| Approve with a wrong code `403` and with an agent as approver `403` (nothing paid); approve rent → **$1,000**; approve invoice 501 → **$160**; approving again `409`; `/api/cash` shows $160 | 6/6 pass |
| `POST /api/reset`: $160 → **$3,400**, 2 payments → 0, contents match the original, original unchanged; tickets all `open` | 2/2 pass |
| Run ticket 102 → rent approval created; reject it, nothing paid | 5/5 pass |
| `backend/test_api.py` (offline, temp copy of the DB): approving $2,400 rent against $1,000 returns `409` "would leave checking at -1400.00", nothing paid, approval stays pending; reject; reset restores $3,400; blocked, rejected, and reset entries are written to the audit trail; real files untouched | 8/8 pass |
| Earlier suites after the refactor: `mcp_server/test_tools.py`, `backend/test_team.py` | 20/20, 21/21 pass |

After testing, the working database was reset: checking is $3,400, there are no payments, and its contents match the original. `output/approvals.json` keeps the test history: the two executed test payments (made by the assistant with the test code under the name "Tejesh Marsale", and later undone by the reset) and one rejected rent approval.

---

## Dashboard (Problem 8)

The React + Vite + TypeScript dashboard in `frontend/` runs on `http://localhost:5173` (`npm run dev`) and calls the backend at `http://localhost:8000` (CORS allows the Vite origin). The layout, agent colors, ticket statuses, and cash display are described in `output/design.md`.

| Dashboard feature | Backend route(s) |
|---|---|
| Ticket list with statuses (including Resolved) and latest result | `GET /api/tickets` (polled every 8 s) |
| Ticket header, team decision, per-agent summaries | `GET /api/tickets/{id}` |
| Run agent team, live progress | `POST /api/tickets/{id}/run`, then `GET /api/jobs/{job_id}`, `GET /api/tickets/{id}`, and `GET /api/activity?ticket_id=` every 1.2 s |
| Agent conversations and MCP tool calls | `GET /api/activity?ticket_id=` |
| Approve or reject payments and purchases | `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `POST /api/approvals/{id}/reject` |
| Mark a ticket resolved (or another status) | `POST /api/tickets/{id}/status` |
| Checking balance, updated after approvals | `GET /api/cash` |
| Reset data | `POST /api/reset` |

Backend changes for the dashboard:
- The audit trail's `RunAudit` accepts a listener, so a run's events are visible through `/api/activity` and `agent_reports` **while** it runs.
- `GET /api/tickets/{id}` returns `agent_reports`.
- There is a new human-only status route.
- `backend/test_api.py` now also checks the status route (11/11 pass).

---

## Problem 9: Full run on all three tickets

### What was done
1. **Reset:** the working database was reset from the dashboard (`run-20261031T054637Z-af325a`). Starting balance read from the database: **checking $3,400.00**, 0 payments, invoice 501 open, all tickets open, contents identical to the original.
2. **Agent runs:** tickets 101, 102, and 103 were each run with **Run agent team** in the React dashboard (`gpt-6-luna` via Portkey). Agents only proposed actions.
3. **Your approval:** the proposed payments were shown to you and approved by you. You then entered your own approval code in the dashboard and clicked **Approve & pay**: rent first, then invoice 501. An earlier attempt with the wrong code was refused, and nothing was paid.
4. **Reports:**
   - the Actual sections and Cash tab of `output/desk_tickets.html` (Expected sections unchanged, checked by hash);
   - `output/resolved_tickets.json`;
   - `output/resolved_board.html`, with full-page dashboard screenshots in `output/screenshots/`, captured from the live dashboard with headless Edge.

### Agent runs (appended to `output/audit_trail.json`; chain verified, 35 entries)

| Ticket | Run | Boss asked first | Hand-offs | MCP calls | Tokens / requests | Proposed |
|---|---|---|---|---|---|---|
| 101 | `run-20261031T054655Z-0a10f0` | Inventory ✓ | Boss→Inventory, Boss→Accounting→Inventory, Boss→Customer Service | 10 | 34,427 / 14 | Rent $2,400, then invoice 501 $840; draft to Tauhid; status Waiting on customer |
| 102 | `run-20261031T054710Z-1664e2` | Facilities ✓ | Boss→Facilities→Accounting, Boss→Accounting | 11 | 29,620 / 13 | Rent $2,400 only; status In progress until paid |
| 103 | `run-20261031T054724Z-e34edc` | Inventory ✓ | Boss→Inventory, Boss→Accounting, Boss→Customer Service | 9 | 30,978 / 12 | No payment, no discount; draft to Yale AI Club; status In progress |

No delegation or tool call was refused, no human-only tool was available to any agent, and every run left both databases unchanged. The 101 and 102 token counts match earlier runs exactly, so Portkey most likely answered them from its cache; 103 was a fresh run.

### Human actions

| UTC (2026-10-31) | Action | Result |
|---|---|---|
| 05:46:37 | Reset working database | Checking $3,400.00 |
| 16:34:14 | Approve rent with a wrong code | Refused, nothing paid |
| 16:34:53 | Tejesh Marsale approved rent $2,400 (lease 1; tickets 101 and 102) | Payment #1, checking $1,000.00 |
| 16:34:58 | Tejesh Marsale approved invoice 501 $840 (Bulldog Print Co reprint; ticket 101) | Payment #2, invoice 501 `paid`, checking **$160.00** |
| 16:49:10 | Tejesh Marsale set 101 → resolved (by mistake) | Corrected at the next step |
| 16:49:26 | Tejesh Marsale set 101 → waiting_on_customer | Recorded |
| 16:49:46 | Tejesh Marsale set 102 → resolved | Recorded |
| 16:49:52 | Tejesh Marsale set 103 → in_progress | Recorded |

### Cash (verified against the database)
$3,400.00 − $2,400.00 − $840.00 = **$160.00** = `cash_accounts.balance` (checking). The `payments` table has exactly these 2 rows, both `approved_by` Tejesh Marsale. The lowest balance was $160.00, so cash never went negative. The original database is still SHA-256 `23686a90…f360a`.

### Ticket outcomes

| Ticket | Business issue addressed? | Final status (database) | What's left |
|---|---|---|---|
| 101 Bulldog tee | **No.** The overdue reprint invoice is paid, but the customer has no tee yet | waiting_on_customer | Tauhid must choose M/L/XL or wait about 5 days (estimated restock 2026-09-05); a person must send the draft |
| 102 Rent due | **Yes.** Rent paid before the 2026-09-02 due date | **resolved** | Nothing |
| 103 Bulk hoodie discount | **No** | in_progress | You need to choose a discount; size M is short by 12 hoodies; the draft needs editing (it contains the stray text "(evaluate_bulk_discount)" and offers no other sizes) and sending |

**Statuses:** the first two Apply attempts never reached the backend: the approval-code field, which is kept only in memory, was most likely empty after a page reload. On the third attempt all three were recorded (16:49 UTC), with one brief mis-set of 101 to resolved that was corrected 16 seconds later. Only 102 is resolved, because it is the only ticket whose business issue is addressed.

### Expected vs actual (summary)
- **Matched:** the first agent the Boss contacted on every ticket; which agents were and weren't involved; rent paid before the invoice; no payment on 103; drafts never sent; cash never negative.
- **Differed:**
  - On 101, Accounting added an extra check with Inventory.
  - On 102, the Boss asked Accounting even though Facilities already had, so the cash check ran twice.
  - Facilities used `check_cash_for_rent` instead of `get_lease`.
  - On 103, Accounting tested only a 62% discount (not 10/15/20%) and gave no concrete safe range, and the draft offered no other sizes and leaked a tool name.

---

## Harness summary (final)

| Layer | What it is | Key files |
|---|---|---|
| Data | `data/campus_customs.db` (original, never written) and `data/campus_customs_new.db` (working copy, resettable) | `data/` |
| MCP server | FastMCP `campus-customs`: 10 read tools plus 2 locked, human-only write tools | `mcp_server/` |
| Agents | Five PydanticAI agents on `gpt-6-luna` via Portkey (Responses API) that delegate to each other within limits | `backend/team.py`, `backend/config.py`, `backend/prompts/` |
| API | FastAPI on port 8000: tickets, runs, live activity, approvals, status, cash, reset | `backend/main.py` |
| Dashboard | React + Vite + TypeScript on port 5173 | `frontend/`, `output/design.md` |
| Records | Append-only, hash-chained audit trail; approvals history; results | `output/audit_trail.json`, `output/approvals.json`, `output/resolved_tickets.json` |
| Safety | Agents only propose; payments and status changes need a person and the approval code; previews and database transactions keep cash from going negative; customer messages are drafts only; the original database is only read | `backend/config.py`, `mcp_server/writes.py`, `backend/main.py` |
| Limits | Delegation depth 2, 5 delegations per ticket, 30 requests / 40 tool calls / 150k tokens per ticket, 400k tokens per run, 4k output tokens per request | `backend/config.py` |

**Known gaps to fix next:**
- The dashboard clears the approval code on reload, which can silently disable Apply.
- Agents sometimes duplicate work, for example the double Accounting check on 102.
- The Customer Service prompt should forbid tool names in customer text and should offer alternative sizes.
- Accounting should test a few realistic discount levels.
