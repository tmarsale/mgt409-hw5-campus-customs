# Campus Customs Agent Desk: Five AI Agents, One Ticket Desk

**MGT 409 · AI Foundations for Managers · Homework 5**

Campus Customs is a small Yale apparel shop with three open tickets: a customer order for an out-of-stock tee (101), a $2,400 rent notice (102), and a bulk hoodie discount request (103). In this project, a team of **five AI agents** (Boss, Inventory, Accounting, Facilities, Customer Service) works those tickets.

- **Shop data:** the agents read everything through an **MCP server**.
- **Proposals only:** they propose payments and customer replies.
- **Human approval:** a person approves every payment in a **React dashboard** before anything is paid.

| Part | Technology | Folder |
|---|---|---|
| Shop data | SQLite: the original and a working copy | [`hw5/data`](hw5/data) |
| MCP server | FastMCP: 10 read tools, plus 2 write tools that only a human can unlock | [`hw5/mcp_server`](hw5/mcp_server) |
| AI agents | PydanticAI with `gpt-6-luna` through Portkey (OpenAI Responses API); agents delegate to each other within limits | [`hw5/backend/team.py`](hw5/backend/team.py), [`config.py`](hw5/backend/config.py), [`prompts/`](hw5/backend/prompts) |
| Backend API | FastAPI on port 8000: tickets, agent runs, live activity, approvals, cash, reset | [`hw5/backend/main.py`](hw5/backend/main.py) |
| Dashboard | React 19 + TypeScript + Vite 8 on port 5173 | [`hw5/frontend`](hw5/frontend) |
| Audit trail | Append-only, hash-chained JSON log of every agent run and human action | [`hw5/output/audit_trail.json`](hw5/output/audit_trail.json) |

## Results (Problem 9)

| Ticket | Outcome | Final status |
|---|---|---|
| 101 Bulldog tee | Size S is out of stock. The overdue $840 reprint invoice was paid with human approval. The customer must choose another size or wait about 5 days. | Waiting on customer |
| 102 Rent due | The $2,400 rent was paid with human approval before its due date | **Resolved** |
| 103 Bulk hoodie discount | Only 8 of 20 in size M. No discount approved yet, and the reply draft needs editing. | In progress |

Checking went **$3,400.00 → $1,000.00 → $160.00** and never went negative. The committed `campus_customs_new.db` is in this final state. The original `campus_customs.db` is unchanged (SHA-256 `23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a`).

## Documentation and deliverables

| File | What it is |
|---|---|
| [`hw5/AI_prompts.md`](hw5/AI_prompts.md) | Every prompt for Problems 1–11, with follow-ups |
| [`hw5/output/harness.md`](hw5/output/harness.md) | **Start here.** Database, MCP tools, agent roles, safety controls, limits, API routes, dashboard, results, and the harness summary |
| [`hw5/mcp_server/README.md`](hw5/mcp_server/README.md) | All 12 MCP tools |
| [`hw5/output/mcp_smoke.json`](hw5/output/mcp_smoke.json) | Problem 4: MCP tools called over a real connection, including by Claude Code |
| [`hw5/output/desk_tickets.html`](hw5/output/desk_tickets.html) | Problems 6, 9, 10: Expected vs Actual plan for each ticket, the Cash tab, and the Reflection (open in a browser) |
| [`hw5/output/design.md`](hw5/output/design.md) | Problem 8: dashboard layout and design choices |
| [`hw5/output/resolved_tickets.json`](hw5/output/resolved_tickets.json) | Problem 9: final status, outcome, agent contributions, and human approvals for each ticket |
| [`hw5/output/resolved_board.html`](hw5/output/resolved_board.html) | Problem 9: results board with dashboard screenshots (open in a browser) |
| [`hw5/output/screenshots/`](hw5/output/screenshots) | Full-page dashboard screenshots for tickets 101, 102, and 103 |
| [`hw5/output/audit_trail.json`](hw5/output/audit_trail.json) | Every agent run (delegations, MCP tool calls with results, decisions) and human action |
| [`hw5/output/approvals.json`](hw5/output/approvals.json) | Payments the agents proposed and what a human decided |
| [`hw5/output/github_url.txt`](hw5/output/github_url.txt) | This repository's URL |

## Folder layout

```
hw5/
├── AI_prompts.md
├── .env.example              # settings template (placeholders only)
├── .mcp.json                 # registers the MCP server with Claude Code
├── data/
│   ├── campus_customs.db     # original, never written
│   └── campus_customs_new.db # working copy (final Problem 9 state)
├── mcp_server/               # FastMCP server: server.py, queries.py (reads), writes.py (human-only)
├── backend/                  # FastAPI app + the five PydanticAI agents
│   ├── main.py               # API routes
│   ├── team.py               # agents, delegation, limits
│   ├── config.py             # model, tool lists, limits
│   ├── run_team.py           # run the team from the command line
│   ├── audit.py, approvals.py, mcp_client.py
│   ├── prompts/              # boss, inventory, accounting, facilities, customer_service, shop_rules
│   └── test_team.py, test_api.py
├── frontend/                 # React + Vite + TypeScript dashboard
└── output/                   # deliverables listed above
```

## Setup

You need **Python 3.12**, **Node.js 20+** (tested with 24), and a **Portkey API key** that can reach `gpt-6-luna`. The commands are for Windows PowerShell; on macOS or Linux, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.

```powershell
cd hw5

# 1. Python packages (one virtual environment for the MCP server and the backend)
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt

# 2. Settings: copy the template and fill in your own values
copy .env.example .env
#    PORTKEY_API_KEY=...                (your key; never commit .env)
#    OPENAI_MODEL=gpt-6-luna            (any other model is refused)
#    CAMPUS_CUSTOMS_APPROVAL_CODE=...   (a private code you'll type in the dashboard to approve payments)

# 3. Dashboard packages
cd frontend
npm install
cd ..
```

`backend/requirements.txt` pins `jiter` and `regex` to versions that Windows Application Control allowed on the original PC. Elsewhere you can remove those two lines.

## Running it

### 1. MCP server

The backend and the agent team **start the MCP server for you** over stdio, so you don't need to run it separately. To run it on its own or test it:

```powershell
.venv\Scripts\python.exe mcp_server/server.py        # stdio server (waits for an MCP client)
.venv\Scripts\python.exe mcp_server/test_tools.py    # 20 checks; write tests use a temporary copy
```

In Claude Code, opening the `hw5` folder loads `.mcp.json`, which registers the server as `campus-customs`.

### 2. FastAPI backend (port 8000)

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>. All routes are listed in `output/harness.md`.

### 3. React dashboard (port 5173)

In a second terminal:

```powershell
cd frontend
npm run dev
```

Open **<http://localhost:5173>**. Use `localhost`, because the dev server doesn't answer on `127.0.0.1`.

1. Pick a ticket and press **Run agent team**. The agent cards and conversation feed update live.
2. Enter your name and approval code in **Approvals** to pay a proposed payment.
3. Use **Set ticket status** to change a ticket's status.

### Command-line run (optional)

```powershell
.venv\Scripts\python.exe backend/run_team.py 101 102 103   # test mode: agents propose, nothing is paid
```

## Resetting the database for a fresh run

The committed working copy holds the final Problem 9 state ($160.00, two payments, statuses set). To start over, copy the original over the working copy. The original is only read.

- **In the dashboard:** click **Reset data** (top right) and confirm.
- **From the API:**
  ```powershell
  Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/reset -ContentType application/json -Body '{"confirm": true}'
  ```

Afterwards checking is $3,400.00, there are no payments, all tickets are open, and pending approvals are voided. The audit trail keeps the history.

## Safety rules built in

- **Agents only propose.** Payments can only be `pending_human_approval`, and customer messages can only be drafts; there is no send tool.
- **Payments need a person.** You must enter a name and the approval code from `.env`. The MCP write tools stay locked unless the backend unlocks them for a single approved call.
- **Cash never goes negative.** Every payment is previewed first and re-checked inside a database transaction.
- **The original database is never written.**
- **Limits:** delegation depth 2; 5 delegations, 30 model requests, 40 tool calls, and 150k tokens per ticket; 400k tokens per run.

## Tests

```powershell
.venv\Scripts\python.exe mcp_server/test_tools.py   # MCP tools and write locks (20 checks)
.venv\Scripts\python.exe backend/test_team.py       # delegation limits, offline, no tokens (21 checks)
.venv\Scripts\python.exe backend/test_api.py        # approvals, overdraft refusal, status, reset on a temp DB (11 checks)
```

`test_api.py` uses FastAPI's test client, which needs one extra package: `.venv\Scripts\python.exe -m pip install httpx`.
