# AI Prompts Log: Homework 5

This file records the prompts I gave the AI assistant for each problem in Homework 5. Each section lists the problem number and title, the prompt I typed, and any follow-up prompts, with a sentence explaining what was missing or needed correction.

All AI agents in Homework 5 use only `gpt-6-luna`, routed through Portkey.

---

## Problem 1: Vibe coder prompts

### Original prompt

> For Homework 5, I've already created the `Homework/HW5` folder in Lecture 2.
> Please create `AI_prompts.md` inside this folder to keep track of the prompts I use throughout the assignment.
> Put one section for each problem, including:
>
> 1. The problem number and title.
> 2. At least one prompt I actually typed, in my own words.
> 3. Any follow-up prompts, with one sentence explaining what was missing or needed correction.
>
> Record my prompts exactly as I type them and keep updating this file as we complete each problem.
> Also, remember that all AI agents in HW5 must use only `gpt-6-luna` through Portkey.
> Start with Problem 1: Vibe coder prompts. Don't start Problem 2 yet.

### Follow-up prompts

None so far.

### What was missing or needed correction

Not applicable. No follow-up was needed.

---

## Problem 2: Study the Campus Customs database

### Original prompt

> For Problem 2, open `data/campus_customs.db` and look through every table and its fields.
>
> Make a copy of the original database named `data/campus_customs_new.db`. We will use this working copy for the rest of the homework, so keep the original unchanged.
>
> Also, review the three open tickets and understand how they connect to the other tables.
>
> Create `output/harness.md`. For each table, list its fields and briefly explain why that table matters for the AI agents.
>
> Keep the explanation simple and easy to understand. We will continue adding to this file in later problems.
>
> Record this prompt in `AI_prompts.md` under Problem 2 and give me a short summary of what you found.

### Follow-up prompts

> One small correction for Problem 2: the correct HW5 title is "Study the Campus Customs database," not "Analyze the database" from HW4.
>
> Please update the heading in `AI_prompts.md` and record this as a follow-up. Keep everything else unchanged.

### What was missing or needed correction

The assistant used the Problem 2 title from HW4 ("Analyze the database") instead of the HW5 title, so the heading was changed to "Study the Campus Customs database."

---

## Problem 3: Build the MCP server

### Original prompt

> For Problem 3, create an MCP server inside `mcp_server/` using FastMCP.
>
> Connect the server to our working database, `data/campus_customs_new.db`, without modifying the original database.
>
> Create three clearly named tools that will help the agents resolve tickets 101, 102, and 103. Use only actual information from the database, not made-up data.
>
> Update `output/harness.md` to explain each tool, which tables it reads, which ticket it supports, and why it's useful.
>
> Also create `mcp_server/README.md` explaining what the MCP server does, which database it uses, and the three tools available.
>
> We don't need to run or connect the MCP server yet.
>
> Record this prompt in `AI_prompts.md` under Problem 3: Build the MCP server.

### Follow-up prompts

None so far.

### What was missing or needed correction

Not applicable. No follow-up was needed.

---

## Problem 4: Connect the MCP server to Claude Code

### Original prompt

> For Problem 4, I want to connect the MCP server we built in Problem 3 to Claude Code so it can use the tools.
>
> 1. Create `.mcp.json` at the project root with the MCP server configuration.
> 2. Test all three tools through the actual MCP connection:
>    * `check_order_fulfillment` for Ticket 101
>    * `check_cash_for_rent` for Ticket 102
>    * `evaluate_bulk_discount` for Ticket 103
> 3. Save the test results in `output/mcp_smoke.json`, including the prompt used, tool name, and actual response for each test.
> 4. Verify that the results match the information in `data/campus_customs_new.db`.
> 5. Record this prompt and any follow-ups in `AI_prompts.md`.
>
> Please confirm that Claude Code can actually call all three MCP tools, not just test the Python functions directly.
> Keep the original database unchanged and summarize the test results when finished.

### Follow-up prompts

> Reopen session in HW5

### What was missing or needed correction

Claude Code connected to the server and saw all three tools, but the Claude Code CLI was not logged in, so it could not make the tool calls; the follow-up opened a new Claude Code session in the HW5 folder so `.mcp.json` loads and Claude Code itself can call the tools.

---

## Problem 5: Build the multi-agent team

### Original prompt

> For Problem 5, I want to build the Campus Customs multi-agent team using PydanticAI.
>
> 1. Create five agents: Boss, Inventory, Accounting, Facilities, and Customer Service. Give each agent detailed instructions in `backend/prompts/` based on its responsibilities and the shop rules.
> 2. Allow all five agents to communicate and delegate tasks to each other. Set reasonable limits to prevent endless loops and unnecessary token usage.
> 3. Expand our existing MCP server with any additional tools needed to handle tickets 101, 102, and 103. All shop information must come through MCP using `data/campus_customs_new.db`.
> 4. Use only `gpt-6-luna` through Portkey for every agent.
> 5. Create an append-only `output/audit_trail.json` to record agent activities and decisions without deleting previous runs.
> 6. Update `output/harness.md` with agent roles, MCP tools, database tables, safety controls, and token limits. Also update `mcp_server/README.md` with the complete tool list.
>
> Make sure payments require human approval, cash balances cannot go negative, and customer messages remain drafts.
> Please test the agent setup and delegation without executing payments or changing ticket statuses yet.
> Record this prompt in `AI_prompts.md` under Problem 5 and summarize what you implemented.

### Follow-up prompts

> Yes, tune prompts

(My answer when the assistant asked whether the agents should also weigh the overdue $840 invoice on ticket 101.)

### What was missing or needed correction

In the first test run, the team handled ticket 101 without mentioning the overdue $840 Bulldog Print Co invoice or the 5-day reprint time, even though the MCP tool returned both. So the Boss, Inventory, Accounting, and Customer Service prompts were tuned to report that blocker, preview rent and the invoice together, and give the customer an estimated restock time.

---

## Problem 6: Expected plans for the desk tickets

### Original prompt

> For Problem 6, create `output/desk_tickets.html` with five tabs: Ticket 101, Ticket 102, Ticket 103, Cash, and Reflection.
> For each ticket, write an Expected section explaining:
>
> 1. Which agent the Boss should contact first and why.
> 2. Which other agents should be involved and how they should delegate work to each other.
> 3. Which MCP tools they should use.
>
> Ticket 101 is about the out-of-stock T-shirt and overdue vendor invoice. Ticket 102 is about the $2,400 rent payment. Ticket 103 is about the bulk hoodie discount and limited inventory.
> Keep the plans realistic and involve only the agents needed for each ticket. Leave space for the Actual results, which we will add after running the agents.
> Leave the Cash and Reflection tabs blank or mark them "Coming later."
> Make the HTML easy to open directly in a browser. Record this prompt in `AI_prompts.md` under Problem 6.

### Follow-up prompts

None so far.

### What was missing or needed correction

Not applicable. No follow-up was needed.

---

## Problem 7: Build the FastAPI backend

### Original prompt

> For Problem 7, create the FastAPI backend in `backend/main.py` to connect our five AI agents to the React dashboard we will build in Problem 8.
> The backend should have six capabilities:
>
> 1. Show tickets 101, 102, and 103 and their current status.
> 2. Run the agent team on a selected ticket.
> 3. Return recent agent activities, messages, and MCP tool calls.
> 4. Allow a human to approve and execute proposed payments or purchases.
> 5. Show the current checking account balance.
> 6. Reset the working database to its original values for a fresh run.
>
> Make sure payments require human approval and cannot create a negative cash balance. Keep the original database unchanged.
> The backend should run from the `backend/` folder using:
> `uvicorn main:app --reload --port 8000`
> Please test the routes and update `output/harness.md` with each route's URL and purpose.
> Record this prompt in `AI_prompts.md` under Problem 7. Don't start Problem 8 yet.

### Follow-up prompts

None so far.

### What was missing or needed correction

Not applicable. No follow-up was needed.

---

## Problem 8: Build the React dashboard

### Original prompt

> For Problem 8, build a React + Vite + TypeScript dashboard in `frontend/` where I can manage tickets, watch our five AI agents work, and approve payments.
> The dashboard should:
>
> 1. Display all three tickets and let me select one to run the agent team.
> 2. Show each agent's activities and conversations while working on a ticket.
> 3. Display ticket status, including resolved tickets, and a short summary of what each agent accomplished.
> 4. Allow me to review and approve proposed payments or purchases.
> 5. Display the current checking balance and update it after approved payments.
>
> Connect the dashboard to our FastAPI backend at `http://localhost:8000` and allow requests from the Vite frontend at `http://localhost:5173`.
> Make the dashboard visually appealing, professional, and easy to use, with distinct appearances for the five agents.
> Create `output/design.md` explaining the layout, design choices, agent displays, ticket statuses, and cash balance.
> Please run and test the dashboard, record this prompt in `AI_prompts.md`, and don't start Problem 9 yet.

### Follow-up prompts

> The dashboard is not opening at `http://localhost:5173`.
>
> Please start both the FastAPI backend on port 8000 and the React frontend on port 5173, and keep them running so I can access the dashboard in my browser.
>
> Verify that the dashboard loads, connects to the backend, and displays all three tickets, the agent activity, and the checking balance.
>
> Please don't make unnecessary code changes or start Problem 9 yet.

> Help me set it

> added the code

> .env updated

### What was missing or needed correction

The servers had been stopped after testing, so the dashboard wasn't reachable. The follow-ups restarted both servers and enabled approvals. The approval code first landed in `.env.example` instead of `.env`, and the new `.env` set `OPENAI_MODEL=gpt-5.6-luna`, which the backend refuses, so the backend was started with `OPENAI_MODEL=gpt-6-luna` until `.env` is fixed.

---

## Problem 9: Run the team on all tickets and compare with the plan

### Original prompt

> For Problem 9, I want to run our five-agent team on all three tickets and compare the actual results with our expected plans.
>
> 1. Reset `data/campus_customs_new.db` to its original values and record the starting checking balance.
> 2. Run tickets 101, 102, and 103 through the React dashboard. Let the agents investigate and propose actions, but ask for my approval before executing any payments or purchases.
> 3. Update the Actual sections in `output/desk_tickets.html` with the agents involved, their delegations, MCP tools used, and outcomes. Keep the Expected sections unchanged.
> 4. Complete the Cash tab showing the starting balance, each approved payment or purchase, and the final balance verified against the database.
> 5. Create `output/resolved_tickets.json` with each ticket's final status, outcome, agent contributions, and human approvals.
> 6. Create `output/resolved_board.html` with actual dashboard screenshots for all three tickets.
> 7. Append the agent runs to `output/audit_trail.json` and finish `output/harness.md`.
>
> Make sure all financial calculations are accurate, no payments happen without my approval, and the checking balance never goes negative.
> Do not mark a ticket resolved unless its business issue has actually been addressed. If a ticket cannot be fully resolved, explain what's blocking it rather than forcing a resolved status.
> Record this prompt in `AI_prompts.md` under Problem 9 and summarize the final results.

### Follow-up prompts

My answers to the assistant's approval questions (chosen in the app, not typed):
- Payments: "Approve both" (rent $2,400, then invoice 501 $840).
- Statuses: "Honest statuses" (102 Resolved, 101 Waiting on customer, 103 In progress).
- "Done, both approved", after I approved both payments in the dashboard with my own approval code.
- "Done, all three set" and later "Done, saw 3 green toasts", for the status changes.

> I'll retry Apply

> done

### What was missing or needed correction

- **Approval code:** the assistant's approval attempt used the code from the chat, which didn't match my `.env`, so it was refused and nothing was paid. I approved both payments myself in the dashboard.
- **Statuses:** my first two attempts to set the statuses never reached the backend, most likely because the approval-code field was empty after a page reload. On the retry, all three were recorded. I briefly set 101 to Resolved by mistake and corrected it to Waiting on customer 16 seconds later. The reports were then updated with the recorded statuses and new screenshots.

### Final results

- **Cash:** $3,400.00 at the start. Rent of $2,400 took it to $1,000.00, and invoice 501 of $840 took it to **$160.00**. This matches the database, and the balance never went negative.
- **Ticket 102: Resolved.** Rent was paid before the due date.
- **Ticket 101: Waiting on customer.** The reprint invoice is paid, but the customer still has to choose a size or wait about 5 days.
- **Ticket 103: In progress.** It still needs a discount decision, has a 12-hoodie shortfall in size M, and needs the draft edited and sent.

---

## Problem 10: Reflection

### Original prompt

> For Problem 10, complete the Reflection tab in `output/desk_tickets.html` using our actual results from the three tickets.
> Here are my observations:
>
> * Ticket 101: The agents identified the T-shirt shortage, the overdue $840 vendor invoice, and the vendor dependency, but couldn't immediately fulfill the order. The final status was Waiting on customer.
> * Ticket 102: The agents coordinated the $2,400 rent payment through human approval, and we successfully resolved the ticket.
> * Ticket 103: The agents evaluated the profitability of the bulk hoodie order but couldn't fulfill the request for 20 hoodies because only 8 were in stock. The ticket remained In progress.
>
> Using these observations and our actual agent runs, compare the Expected and Actual plans for each ticket.
> Also explain which tasks could have been handled more simply by a single agent with tools, identify three additional business problems our current agents could solve, and three problems they cannot solve without additional tools or capabilities.
> Keep the reflection in my natural writing style, detailed but easy to understand. Use actual evidence from the ticket tabs, cash records, and agent activities rather than generic explanations. Don't invent results.
> Update only the Reflection tab, preserve the other sections, and record this prompt in `AI_prompts.md` under Problem 10.

### Follow-up prompts

None so far.

### What was missing or needed correction

Not applicable. No follow-up was needed.

---

## Problem 11: Publish to GitHub

### Original prompt

> For Problem 11, prepare my completed HW5 project for submission to a public GitHub repository.
>
> 1. Organize everything inside an `hw5/` folder, including the frontend, backend, MCP server, agent prompts, documentation, and outputs.
> 2. Include both SQLite databases: `data/campus_customs.db` and `data/campus_customs_new.db`, as required by the assignment.
> 3. Create `.gitignore` to exclude my real `.env`, API keys, virtual environments, caches, and unnecessary files.
> 4. Include `.env.example` with placeholder values only.
> 5. Create a `README.md` explaining how to install dependencies, start the MCP server, FastAPI backend, and React dashboard, and reset the database for a fresh run.
> 6. Verify all required output files, screenshots, and documentation are included.
> 7. Check the files and Git history for real credentials or sensitive information before publishing.
> 8. Push the project to a public GitHub repository and save the URL in `output/github_url.txt`.
>
> Please preserve the original HW5 working project and don't reset the database, change ticket statuses, or execute any payments during packaging.
> Record this prompt in `AI_prompts.md`. Once published, verify the repository is publicly accessible and give me the URL for Canvas.

### Follow-up prompts

None so far.

### What was missing or needed correction

Not applicable. No follow-up was needed.
