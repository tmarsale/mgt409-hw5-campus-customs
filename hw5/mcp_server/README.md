# Campus Customs MCP Server

This is a small [FastMCP](https://gofastmcp.com) server that gives the Homework 5 AI agents everything they know about Campus Customs. It started with three tools in Problem 3 (one per open ticket). Problem 5 added seven lookups for the five-agent team and two write tools that only a human can unlock. Every number it returns comes from the database; nothing is made up.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy made in Problem 2.
- **Never touches:** `data/campus_customs.db`, the original. The write tools refuse to open it.
- All lookups use a **read-only** connection (`mode=ro`).
- The store's "today" comes from the `desk` table (`2026-08-31`), not the computer's clock, so due dates and overdue days match the homework scenario.
- To point at a different file, set the `CAMPUS_CUSTOMS_DB` environment variable. It defaults to `../data/campus_customs_new.db` relative to this folder.

## All 12 tools

### Ticket tools (Problem 3)

| Tool | Ticket | Tables read | What it answers |
|---|---|---|---|
| `check_order_fulfillment(ticket_id)` | 101: customer order | `desk`, `tickets`, `inventory`, `pricing`, `invoices`, `vendors` | Is the item in stock? If not, which other sizes are, and what does the linked vendor invoice say (amount, due date, days overdue, vendor lead time)? |
| `check_cash_for_rent(ticket_id)` | 102: rent notice | `desk`, `tickets`, `leases`, `cash_accounts`, `invoices`, `vendors`, `payments` | When is rent due, how much cash is there, which other bills are open, and how much is left after paying rent and the open bills? |
| `evaluate_bulk_discount(ticket_id, discount_percent=None)` | 103: price override | `desk`, `tickets`, `inventory`, `pricing` | How many are in stock in the requested size and in all sizes, what is the margin, and what is the largest discount before a loss? With a `discount_percent`, it also returns the discounted price, revenue, profit, and whether the price is below cost. |

Each ticket tool checks that the ticket exists and has the right type (for example, `check_cash_for_rent` only accepts `rent_notice` tickets).

### Team lookups (Problem 5, read-only)

| Tool | Tables read | What it answers | Main users |
|---|---|---|---|
| `get_desk_overview()` | `desk`, `tickets`, `cash_accounts`, `invoices`, `leases`, `payments` | Today's date, every ticket and its status, total cash, open bills, upcoming rent, number of payments recorded. | Boss |
| `get_ticket(ticket_id)` | `desk`, `tickets`, `leases`, `invoices`, `vendors` | One ticket of any type plus the lease or invoice it links to. | All agents |
| `check_stock(sku, size=None)` | `inventory`, `pricing` | Stock in every size (or one size), aisle, unit cost, list price. | Inventory, Customer Service |
| `list_vendors()` | `desk`, `vendors`, `invoices` | Each vendor's specialty, lead time, and open invoices with days overdue. | Inventory, Accounting |
| `get_lease(lease_id)` | `desk`, `leases`, `payments` | Landlord, rent, next due date, days until due, rent payments already recorded. | Facilities |
| `get_cash_position()` | `desk`, `cash_accounts`, `invoices`, `vendors`, `leases`, `payments` | All cash, every open invoice, upcoming rent, recorded payments, and cash left after rent and after rent plus open invoices. | Accounting, Boss |
| `preview_payments(payments, account="checking")` | `desk`, `cash_accounts`, `leases`, `invoices`, `payments` | **Dry run, pays nothing.** Checks a batch of payments in order: right amount, bill still unpaid, and cash never negative. Shows the balance after each one. Always returns `executed: false` and `requires_human_approval: true`. | Accounting |

`preview_payments` takes a list like `[{"kind": "rent", "ref_id": 1, "amount": 2400}, {"kind": "invoice", "ref_id": 501, "amount": 840}]`. For tickets 101 and 102 it shows $3,400 → $1,000 after rent → $160 after invoice 501.

### Human-only write tools (Problem 5, locked by default)

| Tool | Tables changed | What it does |
|---|---|---|
| `record_payment(kind, ref_id, amount, approved_by, approval_code, account="checking")` | `payments` (insert), `cash_accounts` (balance down), `invoices` (status `paid` for an invoice payment) | Records one approved rent or invoice payment in a single transaction. |
| `update_ticket_status(ticket_id, status, approved_by, approval_code)` | `tickets` | Sets a ticket to `open`, `in_progress`, `waiting_on_customer`, or `resolved`. |

Both write tools refuse to run unless **all** of these are true:

1. The server was started with `CAMPUS_CUSTOMS_ALLOW_WRITES=1` (a human's choice; the agent team never sets it).
2. `approval_code` matches `CAMPUS_CUSTOMS_APPROVAL_CODE`, a code only the human knows. It is never given to an agent.
3. `approved_by` names a person, not an agent (`boss`, `accounting`, and so on are rejected).
4. The database is not the original `campus_customs.db`.

`record_payment` also re-checks the payment inside the transaction and **refuses any payment that would make the cash balance negative**, a wrong amount, an already-paid invoice, or rent already recorded for that due date.

The five AI agents are never given these two tools (see `backend/config.py`), so in the agent team every payment and status change stays a proposal until a human acts.

## Files

| File | Purpose |
|---|---|
| `server.py` | Creates the FastMCP server and registers the 12 tools. |
| `queries.py` | The read-only SQL behind the ten lookup tools, including the payment preview. It doesn't depend on FastMCP, so it can be tested on its own. |
| `writes.py` | The two human-only write tools and their approval checks. |
| `smoke_test.py` | Problem 4: calls the three ticket tools over MCP and checks them against the database (writes `output/mcp_smoke.json`). |
| `test_tools.py` | Problem 5: checks the new lookups against the database, the payment preview's negative-cash check, and the write locks. Write tests run only on a temporary copy of the database. |
| `requirements.txt` | `fastmcp` |

## Running

From the HW5 folder, create the local virtual environment once:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r mcp_server/requirements.txt
```

`.mcp.json` in the HW5 folder registers the server with Claude Code as `campus-customs`. Claude Code starts it over stdio with `.venv/Scripts/python.exe mcp_server/server.py`. The agent team in `backend/` starts its own copy the same way, with writes locked.

Tests:

```powershell
.venv\Scripts\python.exe mcp_server/test_tools.py
.venv\Scripts\python.exe mcp_server/smoke_test.py
```

`smoke_test.py` rewrites `output/mcp_smoke.json`, so run it only when you want a fresh Problem 4 record.
