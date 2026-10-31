# Campus Customs Agent Desk: Dashboard Design

The dashboard (HW5 Problem 8) is a React + Vite + TypeScript app in `frontend/`. From it you can manage the three tickets, watch the five AI agents work, approve payments, and see the checking balance. It talks only to the FastAPI backend at `http://localhost:8000`. The backend allows the Vite origin `http://localhost:5173` through CORS.

## Running it

Two terminals, both from the HW5 folder:

```powershell
# 1. Backend (needs PORTKEY_API_KEY, plus CAMPUS_CUSTOMS_APPROVAL_CODE in HW5/.env for approvals)
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000

# 2. Dashboard
cd frontend
npm install        # first time only
npm run dev        # http://localhost:5173
```

To point the dashboard at another backend, set `VITE_API_URL` (for example in `frontend/.env`). The default is `http://localhost:8000`.

---

## Layout

A three-column workspace under a top bar. Your eye moves left to right: pick a ticket, watch the team, then decide about the money.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ CC  Campus Customs Agent Desk   [store date] [model] [original DB ✓] [Reset] │  top bar
├──────────────┬────────────────────────────────────────────┬──────────────────┤
│ TICKETS      │ TICKET HEADER                              │ CHECKING BALANCE │
│ #101 card    │  subject · requester · status · [Run team] │  $3,400.00       │
│ #102 card    │  Team decision (summary, facts, proposals) │  after pending … │
│ #103 card    │  Set ticket status [select] [Apply]        │  rent, invoices, │
│              ├────────────────────────────────────────────┤  paid list       │
│              │ AGENT TEAM: 5 cards, one per agent         ├──────────────────┤
│              ├────────────────────────────────────────────┤ APPROVALS        │
│              │ ACTIVITY & CONVERSATIONS (live feed)       │  name + code     │
│              │  hand-offs, replies, MCP tool calls,       │  pending cards   │
│              │  decision, customer draft                  │  [Approve][Reject]│
└──────────────┴────────────────────────────────────────────┴──────────────────┘
```

| Area | What it shows | Why it's there |
|---|---|---|
| **Top bar** | Brand, store date (2026-08-31), model (`gpt-6-luna` · Portkey), a green "Original DB untouched" check, and **Reset data**. | Constant context and safety status. Reset sits in the corner and asks for confirmation, since it erases payments. |
| **Tickets (left)** | One card per ticket: number, type icon, subject, requester, **status badge**, a 3-line summary of the latest team result, and "N payments awaiting approval". | Shows the whole queue at a glance. Clicking a card selects the ticket. |
| **Ticket header (center top)** | Subject, requester, SKU, invoice, or lease, the customer's note, status badge, and the main **Run agent team** button. After a run: a pink **Team decision** card (summary, recommendation, key facts, proposed status, payments proposed, whether a customer draft exists, tokens used) and a **Set ticket status** control. | The one main action (run) and the result you act on are together. |
| **Agent team (center)** | Five cards, always in the same order: Boss, Inventory, Accounting, Facilities, Customer Service. | You see who worked, who was skipped, and what each one did. |
| **Activity & conversations (center bottom)** | A chat-style feed of the run, oldest at the top. A **Latest run / All history** switch. | It shows how the agents talked to each other and which tools they used. |
| **Checking balance (right top)** | The balance, the balance after all pending approvals, upcoming rent, open invoices (overdue in amber), and a **Paid** list. | Money is the limit on every decision, so it stays in view. The column is sticky on wide screens. |
| **Approvals (right)** | Your name and the approval code, then one card per pending payment, and a "Recent decisions" history. | All the human decisions are in one place. |

**Responsive:** at 1280 px and below, the right column moves under the workspace as two side-by-side panels. Below 860 px everything stacks in one column (tested at 375 px with no sideways scrolling).

---

## Visual style

- **Black and pink**, as the workspace rules ask: a near-black background (`#09090d`) with faint pink and violet glows, dark panels (`#14141c`), light text (`#f4f1f6`), and **hot pink (`#ff3d9a`)** for the brand, primary buttons, the selected ticket, the team decision, and focus rings.
- **Hierarchy:** one pink primary button per area (Run agent team, Approve & pay). Everything else is a ghost (outlined) button. Big numbers only for money.
- **Cards and rounded corners** (14–16 px), with generous spacing and soft shadows. Only tool calls are drawn in a monospaced font, so they read as machine actions.
- **Motion with a purpose:** working agents pulse, the "Agents working" badge blinks, the balance flashes pink when it drops, and new toasts slide in. All motion is turned off for users who prefer reduced motion.
- **Accessibility:** light text on near-black for high contrast (not formally measured), real `<button>`s and labelled inputs, a skip link, visible focus rings, `aria-live` for the feed, balance, and toasts, `aria-current` on the selected ticket, and a native `<dialog>` for the reset confirmation.
- **Clear loading and error states:** skeleton bars while loading, an error banner and "Backend offline" chip if the API can't be reached, a notice if approvals are switched off, plain-English error toasts (for example "Wrong approval code. Nothing was paid."), and an error boundary around each center panel so one bad record can't blank the page.

---

## How the five agents look

Each agent has its own color and icon, used everywhere it appears: its card, avatar, chat bubbles, and tool-call dots.

| Agent | Color | Icon | Role line |
|---|---|---|---|
| **Boss** | Hot pink `#ff3d9a` (the brand color: the Boss leads) | Crown | Coordinates the team |
| **Inventory** | Amber `#ffb547` | Box | Stock & restocking |
| **Accounting** | Mint green `#3ddc97` | Dollar coin | Cash & payments |
| **Facilities** | Sky blue `#5aa9ff` | Building | Lease & shop space |
| **Customer Service** | Lavender `#b18cff` | Speech bubble | Customer replies |

The colors are far apart in hue, so the agents are easy to tell apart on the dark background, and each also has an icon and its name (never color alone).

**Agent cards** have a colored top border and a state label:

| State | Look | Meaning |
|---|---|---|
| Working… | Avatar pulses, card glows in the agent's color | The agent is running right now (live). |
| Done | Green "DONE" | The agent finished; the card shows its summary (up to 6 lines, full text on hover), who asked it ("Asked by Boss, Accounting"), and how many MCP tools it called. |
| Not involved | Card dimmed, "Not needed for this ticket." | The Boss didn't need this agent. Ticket 102, for example, uses no Inventory or Customer Service. |
| Failed | Red | The agent hit an error or a limit. |

**Conversation feed:**
- **Hand-off:** two avatars with an arrow, "**Boss** asked **Inventory**", and the task text, in a bubble tinted with the asking agent's color.
- **Reply:** "**Inventory** replied to **Boss**" with its summary and an expandable list of key facts.
- **MCP tool call:** a compact dashed row with the agent's color dot and the call itself, for example `check_order_fulfillment(ticket_id=101)`.
- **Team decision:** a pink-highlighted block.
- **Customer reply:** shown as an email (To, Subject, body) with a lavender **"Draft · not sent"** tag, because agents never send messages.
- **Guardrail line** (green): "proposed payments keep checking at $160.00. Nothing paid yet."
- **Human actions** (pink dots, under *All history*): approvals, wrong-code attempts, status changes, resets.

During a run the dashboard polls the backend every 1.2 s. The backend now exposes the in-progress run's events (before the run reaches the audit trail), so the cards and feed fill in as the agents work. A "typing" indicator shows at the bottom of the feed. While a ticket is running, only the new run is shown, never the previous run's results.

---

## Ticket statuses

| Status | Badge | When |
|---|---|---|
| **Open** | Grey | New, or reset. |
| **In progress** | Amber | A human set it while work continues (the team suggests this for the rent ticket until it's paid). |
| **Waiting on customer** | Lavender | A reply draft is waiting on the customer's choice (101, 103). |
| **Resolved** | Green | A human closed it. Resolved tickets stay in the list with a green badge, and the "N open" counter drops. |
| **Agents working** | Pink, blinking | Shown in place of the status while the team runs on that ticket. |

Agents only *suggest* a status (shown in the Team decision card as "Proposed status"). Only a human changes it, with **Set ticket status → Apply**, which needs your name and the approval code. It calls `POST /api/tickets/{id}/status`, which runs the locked `update_ticket_status` MCP tool and is recorded in the audit trail.

---

## Cash balance and approvals

- **Checking balance** is a large number from `GET /api/cash` (the `cash_accounts` table, through MCP). Under it: **"After pending approvals: $X"**, which turns red if the pending payments together would overdraw the account.
- The list shows upcoming rent (with days until due), each open invoice (amber when overdue), and a **Paid** list of recorded payments with the name of the person who approved each one.
- **Approving a payment:**
  1. Type your name (remembered in the browser) and the approval code (kept only in memory, never saved).
  2. Each pending card shows the type (**Rent** in blue, **Purchase · invoice** in amber), the amount, the lease or invoice, the ticket(s) it came from, the agents' reason, and **"Checking after this"**, which counts down in rent-first order.
  3. **Approve & pay** is disabled until both fields are filled, and also disabled if the payment would make the running balance negative. The backend also previews the payment and refuses an overdraft, and the MCP server re-checks it inside a transaction.
  4. After a payment the balance updates right away, with a pink flash and a "−$2,400.00" delta, and a toast confirms it ("Paid $2,400.00 (rent). Checking is now $1,000.00.").
  5. **Reject** records the decision and pays nothing.
- If the same bill is proposed by two tickets (rent from 101 and 102), it appears **once**, tagged with both tickets.
- **Reset data** asks for confirmation, then copies the original database over the working copy. Checking goes back to $3,400, every ticket reopens, and pending approvals are voided. The original database is only read.

---

## Test run (2026-10-31)

The dashboard was run with `npm run dev` against the backend started with `uvicorn main:app --reload --port 8000` and a test-only approval code, then exercised in a browser:

| Step | Result |
|---|---|
| Page loads; tickets, cash, approvals, and health come from the backend (CORS from `localhost:5173` works) | ✅ |
| Reset data through the confirmation dialog | ✅ $3,400.00, all tickets Open, toast shown |
| Run agent team on ticket 101 | ✅ Boss, Inventory, Accounting, Customer Service Done; Facilities "Not involved"; two approvals created (rent $2,400, invoice 501 $840) |
| Run on ticket 102 while watching live | ✅ Boss, Facilities, Accounting showed "Working…" with pulsing avatars; hand-offs and tool calls streamed in; rent proposal merged into the existing rent approval (tagged #101, #102); "team finished" toast |
| Approve with a wrong code | ✅ "Wrong approval code. Nothing was paid."; balance unchanged |
| Approve rent, then invoice 501 | ✅ $3,400 → **$1,000** → **$160**, with flash, delta, toasts; Paid list shows both; Approvals empty; invoice gone from open bills |
| Mark ticket 101 Resolved | ✅ Green "Resolved" badge in the list and header; counter "2 open" |
| Run on ticket 103 | ✅ Customer reply shown as an email with "Draft · not sent" |
| Run 102 again after rent was paid | ✅ Team saw rent already recorded and proposed no payment |
| *All history* view | ✅ Shows human actions (wrong code, approvals, status change) |
| Phone width (375 px) | ✅ Single column, no sideways scrolling |
| Console | ✅ No errors after the fixes (the only 403 was the deliberate wrong-code test) |
| `npm run build` (TypeScript + Vite production build) | ✅ |
| Backend suites after the dashboard changes | ✅ `test_api.py` 11/11, `test_team.py` 21/21, `test_tools.py` 20/20 |

Afterwards the working database was reset (checking $3,400, no payments, contents match the original), and both servers were stopped.
