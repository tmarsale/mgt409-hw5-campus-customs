"""FastAPI backend for the Campus Customs dashboard (HW5 Problem 7).

Run from the backend/ folder:

    uvicorn main:app --reload --port 8000

Interactive docs: http://127.0.0.1:8000/docs

Shop data always comes through the campus-customs MCP server, which reads
data/campus_customs_new.db. Agents only propose payments. A payment runs only
when a human approves it here with the approval code, and the MCP server
refuses any payment that would make cash negative. The original
data/campus_customs.db is never written; /api/reset only reads it.
"""

import asyncio
import hmac
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from approvals import ApprovalStore
from audit import file_sha256, load_trail, log_human_action
from mcp_client import ShopMCP, ToolFailed
from run_team import run_tickets

mcp = ShopMCP()
approvals = ApprovalStore(config.APPROVALS_FILE)
jobs: dict[str, dict] = {}          # agent runs started through the API (kept in memory)
state: dict[str, Any] = {"running_job": None}
write_lock = asyncio.Lock()          # one payment or reset at a time


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await mcp.start()
    yield
    await mcp.stop()


app = FastAPI(
    title="Campus Customs desk API",
    version="1.0",
    description="Tickets, agent runs, activity, human approvals, cash, and reset for the HW5 dashboard.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,  # the React dashboard (Problem 8) runs on its own dev port
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _read(tool: str, args: dict | None = None) -> dict:
    try:
        return await mcp.read(tool, args)
    except ToolFailed as e:
        raise HTTPException(404 if "does not exist" in str(e) else 400, str(e))


# --- Audit trail helpers -----------------------------------------------------

KIND = {
    "agent_started": "agent", "agent_finished": "agent", "agent_failed": "agent",
    "delegation": "delegation", "delegation_refused": "delegation",
    "mcp_tool_call": "tool", "mcp_tool_error": "tool", "mcp_tool_refused": "tool",
    "ticket_decision": "decision",
}


def _summary(e: dict) -> str:
    ev, who = e["event"], e.get("agent") or "system"
    if ev == "agent_started":
        return f"{who} started: {e.get('prompt', '')}"
    if ev == "agent_finished":
        return f"{who} finished: {e['report']['summary']}"
    if ev == "agent_failed":
        return f"{who} failed: {e.get('error')}"
    if ev == "delegation":
        return f"{who} asked {e['to_agent']}: {e['task']}"
    if ev == "delegation_refused":
        return f"{who} could not ask {e['to_agent']}: {e['reason']}"
    if ev == "mcp_tool_call":
        return f"{who} called {e['tool']}({', '.join(f'{k}={v}' for k, v in e['arguments'].items())})"
    if ev in ("mcp_tool_error", "mcp_tool_refused"):
        return f"{who} {ev.split('_')[-1]} {e['tool']}: {e.get('error') or e.get('reason', '')}"
    if ev == "ticket_decision":
        return f"Boss decision: {e['decision']['summary']}"
    if ev.startswith("human_"):
        return e.get("summary", ev.replace("_", " "))
    return ev.replace("_", " ")


def _live_runs() -> list[dict]:
    """The events of an agent run still in progress (not yet in the audit trail)."""
    job = jobs.get(state["running_job"] or "")
    return [job["live"]] if job and job.get("live") else []


def _activity(limit: int, ticket_id: int | None, kind: str | None, include_results: bool) -> list[dict]:
    items: list[dict] = []
    runs = load_trail(config.AUDIT_TRAIL).get("runs", []) + _live_runs()
    for run in reversed(runs):
        for e in reversed(list(run["events"])):
            if ticket_id is not None and e.get("ticket_id") != ticket_id:
                continue
            k = KIND.get(e["event"], "human" if e["event"].startswith("human_") else "system")
            base = {"run_id": run["run_id"], "seq": e["seq"], "at": e["at"], "event": e["event"],
                    "agent": e.get("agent"), "ticket_id": e.get("ticket_id")}
            # Customer messages (always drafts) come from the Boss's final decision.
            draft = e.get("decision", {}).get("customer_draft") if e["event"] == "ticket_decision" else None
            if draft and kind in (None, "message"):
                items.append({**base, "kind": "message", "summary": f"Draft to {draft['to']}: {draft['subject']}",
                              "detail": draft})
            if kind not in (None, k):
                continue
            detail = {key: v for key, v in e.items() if key not in ("seq", "at", "event", "agent", "ticket_id")}
            if not include_results:
                detail.pop("result", None)
            items.append({**base, "kind": k, "summary": _summary(e), "detail": detail})
            if len(items) >= limit:
                return items[:limit]
    return items[:limit]


def _latest_decisions() -> dict[int, dict]:
    latest: dict[int, dict] = {}
    for run in load_trail(config.AUDIT_TRAIL).get("runs", []):
        for e in run["events"]:
            if e["event"] == "ticket_decision":
                latest[e["ticket_id"]] = {"run_id": run["run_id"], "at": e["at"], **e["decision"], "usage": e["usage"]}
    return latest


def _agent_reports(ticket_id: int) -> dict:
    """What each agent reported in the latest (or in-progress) run on this ticket."""
    runs = load_trail(config.AUDIT_TRAIL).get("runs", []) + _live_runs()
    for run in reversed(runs):
        events = [e for e in run["events"] if e.get("ticket_id") == ticket_id]
        if not any(e["event"] in ("agent_started", "agent_finished") for e in events):
            continue
        agents: dict[str, dict] = {}
        for e in events:
            a = e.get("agent")
            if not a or a not in config.TEAM:
                continue
            info = agents.setdefault(a, {"agent": a, "status": "idle", "asked_by": [], "tasks": 0,
                                         "tool_calls": 0, "summary": None, "recommendation": None,
                                         "key_facts": [], "last_at": e["at"]})
            info["last_at"] = e["at"]
            if e["event"] == "agent_started":
                asker = e["chain"][-2] if len(e["chain"]) > 1 else "human"
                if asker not in info["asked_by"]:
                    info["asked_by"].append(asker)
                info["status"] = "working"
                info["tasks"] += 1
            elif e["event"] == "agent_finished":
                r = e["report"]
                info.update(status="done", summary=r["summary"], recommendation=r["recommendation"],
                            key_facts=r["key_facts"])
            elif e["event"] == "agent_failed":
                info.update(status="failed", summary=e.get("error"))
            elif e["event"] == "mcp_tool_call":
                info["tool_calls"] += 1
        in_progress = any(run is live for live in _live_runs())
        return {"run_id": run["run_id"], "in_progress": in_progress, "agents": list(agents.values())}
    return {"run_id": None, "in_progress": False, "agents": []}


# --- 0. Health -----------------------------------------------------------------


@app.get("/api/health", tags=["system"])
async def health() -> dict:
    """Is the backend up, which model and database does it use, and is the original database untouched?"""
    overview = await _read("get_desk_overview")
    return {
        "status": "ok",
        "model": config.MODEL_NAME,
        "gateway": "Portkey",
        "store_date": overview["today"],
        "working_db": str(config.WORKING_DB.relative_to(config.HW5_DIR)),
        "original_db_unchanged": file_sha256(config.ORIGINAL_DB) == config.ORIGINAL_DB_SHA256,
        "approvals_enabled": bool(config.approval_code()),
        "agent_run_in_progress": state["running_job"],
    }


# --- 1. Tickets ----------------------------------------------------------------


@app.get("/api/tickets", tags=["tickets"])
async def list_tickets() -> dict:
    """Every ticket (101, 102, 103) with its current status, pending approvals, and the latest agent result."""
    overview = await _read("get_desk_overview")
    latest = _latest_decisions()
    pending = approvals.query("pending")
    tickets = []
    for t in overview["tickets"]:
        last = latest.get(t["id"])
        tickets.append({
            **t,
            "pending_approvals": sum(t["id"] in a["ticket_ids"] for a in pending),
            "last_run": None if last is None else {
                "run_id": last["run_id"], "at": last["at"], "summary": last["summary"],
                "recommendation": last["recommendation"],
                "proposed_ticket_status": last["proposed_ticket_status"],
            },
        })
    return {"today": overview["today"], "tickets": tickets}


@app.get("/api/tickets/{ticket_id}", tags=["tickets"])
async def get_ticket(ticket_id: int) -> dict:
    """One ticket with its linked lease or invoice, the latest team decision, and its approvals."""
    detail = await _read("get_ticket", {"ticket_id": ticket_id})
    return {
        **detail,
        "last_decision": _latest_decisions().get(ticket_id),
        "agent_reports": _agent_reports(ticket_id),
        "approvals": approvals.query(ticket_id=ticket_id),
    }


class StatusBody(BaseModel):
    status: Literal["open", "in_progress", "waiting_on_customer", "resolved"]
    approved_by: str = Field(min_length=1)
    approval_code: str = Field(min_length=1)


@app.post("/api/tickets/{ticket_id}/status", tags=["tickets"])
async def set_ticket_status(ticket_id: int, body: StatusBody) -> dict:
    """A human changes a ticket's status (for example, marks it resolved). Needs the approval code."""
    expected = config.approval_code()
    if not expected:
        raise HTTPException(503, "Approvals are off. Set CAMPUS_CUSTOMS_APPROVAL_CODE in HW5/.env and restart.")
    await _read("get_ticket", {"ticket_id": ticket_id})  # 404 for an unknown ticket
    if not hmac.compare_digest(body.approval_code, expected):
        log_human_action(config.AUDIT_TRAIL, "status_change_denied", "error", ticket_id,
                         attempted_by=body.approved_by, summary=f"Wrong approval code for ticket {ticket_id} status")
        raise HTTPException(403, "Wrong approval code. Status not changed.")
    async with write_lock:
        try:
            result = await mcp.write_with_approval("update_ticket_status", {
                "ticket_id": ticket_id, "status": body.status,
                "approved_by": body.approved_by, "approval_code": body.approval_code})
        except ToolFailed as e:
            raise HTTPException(403, f"MCP server refused the change: {e}")
    log_human_action(config.AUDIT_TRAIL, "ticket_status_changed", "ok", ticket_id, change=result,
                     summary=f"{body.approved_by} set ticket {ticket_id} to {body.status} "
                             f"(was {result['old_status']})")
    return result


# --- 2. Run the agent team -----------------------------------------------------


async def _run_job(job: dict) -> None:
    def listen(run_id: str, event: dict) -> None:
        job["live"] = job.get("live") or {"run_id": run_id, "events": []}
        job["live"]["events"].append(event)
        job["run_id"] = run_id

    try:
        run = await run_tickets([job["ticket_id"]], mode="dashboard run (agents propose; humans approve payments)",
                                listener=listen)
        created = approvals.add_from_run(run)
        result = run["results"][0] if run["results"] else None
        job.update(status="finished" if run["status"] == "ok" else run["status"], run_id=run["run_id"],
                   decision=result and result["decision"], usage=result and result["usage"],
                   delegations_used=result and result["delegations_used"], guardrails=run["guardrails"],
                   approvals=[a["id"] for a in created])
    except Exception as e:  # recorded in the audit trail by run_tickets
        job.update(status="failed", error=f"{type(e).__name__}: {e}")
    finally:
        job["finished_at"] = _now()
        job.pop("live", None)  # the run is in the audit trail now
        state["running_job"] = None


def _public(job: dict) -> dict:
    out = {k: v for k, v in job.items() if k != "live"}
    out["events_so_far"] = len(job["live"]["events"]) if job.get("live") else None
    return out


@app.post("/api/tickets/{ticket_id}/run", tags=["agents"], status_code=202)
async def run_ticket(ticket_id: int, response: Response,
                     wait: bool = Query(False, description="Wait for the run to finish (about 1 minute).")) -> dict:
    """Start the five-agent team on one ticket. Returns a job to poll at /api/jobs/{job_id}."""
    await _read("get_ticket", {"ticket_id": ticket_id})  # 404 for an unknown ticket
    if state["running_job"]:
        raise HTTPException(409, f"Agent run {state['running_job']} is still in progress.")
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    job = {"job_id": job_id, "ticket_id": ticket_id, "status": "running", "started_at": _now(),
           "finished_at": None, "run_id": None}
    jobs[job_id] = job
    state["running_job"] = job_id
    task = asyncio.create_task(_run_job(job))
    if wait:
        await task
        response.status_code = 200
    return _public(job)


@app.get("/api/jobs/{job_id}", tags=["agents"])
async def get_job(job_id: str) -> dict:
    """Status and result of an agent run started through the API."""
    if job_id not in jobs:
        raise HTTPException(404, f"Job {job_id} not found (jobs are kept until the backend restarts).")
    return _public(jobs[job_id])


@app.get("/api/runs", tags=["agents"])
async def list_runs(limit: int = Query(10, ge=1, le=100)) -> dict:
    """Recent entries in the audit trail (agent runs and human actions), newest first."""
    runs = load_trail(config.AUDIT_TRAIL).get("runs", [])
    return {"runs": [{
        "run_id": r["run_id"], "mode": r["mode"], "status": r["status"], "started_at": r["started_at"],
        "finished_at": r.get("finished_at"), "tickets": r.get("tickets"), "total_tokens": r.get("run_total_tokens"),
        "events": len(r["events"]),
    } for r in reversed(runs[-limit:])]}


# --- 3. Activity ---------------------------------------------------------------


@app.get("/api/activity", tags=["agents"])
async def activity(
    limit: int = Query(50, ge=1, le=500),
    ticket_id: int | None = None,
    kind: Literal["agent", "delegation", "tool", "decision", "message", "human", "system"] | None = None,
    include_results: bool = Query(False, description="Include full MCP tool results."),
) -> dict:
    """Recent agent activity, delegations, MCP tool calls, decisions, customer drafts, and human actions."""
    return {"items": _activity(limit, ticket_id, kind, include_results)}


# --- 4. Human approval of payments ---------------------------------------------


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the person approving.")
    approval_code: str = Field(min_length=1, description="The human approval code from HW5/.env.")


class RejectBody(BaseModel):
    rejected_by: str = Field(min_length=1)
    reason: str = ""


@app.get("/api/approvals", tags=["approvals"])
async def list_approvals(status: Literal["pending", "executed", "rejected", "failed", "voided"] | None = None,
                         ticket_id: int | None = None) -> dict:
    """Payments the agents proposed (rent and vendor invoices/purchases) and what a human decided."""
    items = approvals.query(status, ticket_id)
    return {"approvals_enabled": bool(config.approval_code()), "approvals": items,
            "pending_total": round(sum(a["amount"] for a in items if a["status"] == "pending"), 2)}


@app.post("/api/approvals/{approval_id}/approve", tags=["approvals"])
async def approve(approval_id: str, body: ApproveBody) -> dict:
    """A human approves a proposed payment; it is executed through MCP if cash stays non-negative."""
    expected = config.approval_code()
    if not expected:
        raise HTTPException(503, "Approvals are off. Set CAMPUS_CUSTOMS_APPROVAL_CODE in HW5/.env and restart.")
    async with write_lock:
        item = approvals.get(approval_id)
        if item is None:
            raise HTTPException(404, f"Approval {approval_id} not found.")
        if item["status"] != "pending":
            raise HTTPException(409, f"Approval {approval_id} is already {item['status']}.")
        ticket = item["ticket_ids"][0]
        if not hmac.compare_digest(body.approval_code, expected):
            log_human_action(config.AUDIT_TRAIL, "approval_denied", "error", ticket, approval_id=approval_id,
                             attempted_by=body.approved_by, summary=f"Wrong approval code for {approval_id}")
            raise HTTPException(403, "Wrong approval code. Nothing was paid.")

        payment = {"kind": item["kind"], "ref_id": item["ref_id"], "amount": item["amount"]}
        preview = await _read("preview_payments", {"payments": [payment]})
        if not preview["all_valid"]:
            problems = preview["payments"][0]["problems"]
            log_human_action(config.AUDIT_TRAIL, "payment_blocked", "error", ticket, approval_id=approval_id,
                             payment=payment, problems=problems, summary=f"Payment blocked: {'; '.join(problems)}")
            raise HTTPException(409, {"message": "Payment not executed.", "problems": problems})
        try:
            result = await mcp.write_with_approval(
                "record_payment", {**payment, "approved_by": body.approved_by, "approval_code": body.approval_code})
        except ToolFailed as e:
            log_human_action(config.AUDIT_TRAIL, "payment_refused", "error", ticket, approval_id=approval_id,
                             attempted_by=body.approved_by, error=str(e), summary=f"MCP server refused payment: {e}")
            raise HTTPException(403, f"MCP server refused the payment: {e}")
        if not result.get("executed"):
            raise HTTPException(409, {"message": "Payment not executed.", "problems": result.get("problems")})
        item = approvals.decide(approval_id, "executed", body.approved_by, result)
    log_human_action(config.AUDIT_TRAIL, "payment_executed", "ok", ticket, approval_id=approval_id,
                     approved_by=body.approved_by, payment=result,
                     summary=f"{body.approved_by} approved {item['label'].lower()} of ${item['amount']:,.2f}; "
                             f"checking now ${result['balance_after']:,.2f}")
    return {"approval": item, "payment": result, "checking_balance": result["balance_after"]}


@app.post("/api/approvals/{approval_id}/reject", tags=["approvals"])
async def reject(approval_id: str, body: RejectBody) -> dict:
    """A human rejects a proposed payment. Nothing is paid."""
    async with write_lock:
        item = approvals.get(approval_id)
        if item is None:
            raise HTTPException(404, f"Approval {approval_id} not found.")
        if item["status"] != "pending":
            raise HTTPException(409, f"Approval {approval_id} is already {item['status']}.")
        item = approvals.decide(approval_id, "rejected", body.rejected_by, {"reason": body.reason})
    log_human_action(config.AUDIT_TRAIL, "payment_rejected", "ok", item["ticket_ids"][0], approval_id=approval_id,
                     rejected_by=body.rejected_by, reason=body.reason,
                     summary=f"{body.rejected_by} rejected {item['label'].lower()} of ${item['amount']:,.2f}")
    return {"approval": item}


# --- 5. Cash -------------------------------------------------------------------


@app.get("/api/cash", tags=["cash"])
async def cash() -> dict:
    """The checking balance now, open bills, and the balance if every pending approval were paid."""
    cp = await _read("get_cash_position")
    checking = next(a for a in cp["cash_accounts"] if a["name"] == "checking")
    pending_total = round(sum(a["amount"] for a in approvals.query("pending")), 2)
    after = round(checking["balance"] - pending_total, 2)
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["as_of"],
        "total_cash": cp["total_cash"],
        "open_invoices": cp["open_invoices"],
        "open_invoices_total": cp["open_invoices_total"],
        "upcoming_rent": cp["upcoming_rent"],
        "payments_recorded": cp["payments_recorded"],
        "pending_approvals_total": pending_total,
        "balance_after_pending_approvals": after,
        "pending_approvals_keep_cash_non_negative": after >= 0,
    }


# --- 6. Reset ------------------------------------------------------------------


class ResetBody(BaseModel):
    confirm: bool = Field(description="Must be true. Erases payments and status changes in the working copy.")


def _dump(path) -> list[str]:
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        return list(conn.iterdump())
    finally:
        conn.close()


@app.post("/api/reset", tags=["system"])
async def reset(body: ResetBody) -> dict:
    """Copy the original database over the working copy for a fresh run. The original is only read."""
    if not body.confirm:
        raise HTTPException(400, "Send {\"confirm\": true} to reset the working database.")
    if state["running_job"]:
        raise HTTPException(409, "An agent run is in progress; reset after it finishes.")
    async with write_lock:
        before = await _read("get_cash_position")
        src = sqlite3.connect(f"{config.ORIGINAL_DB.as_uri()}?mode=ro", uri=True)  # read-only: original never changes
        dst = sqlite3.connect(config.WORKING_DB)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        voided = approvals.void_pending("working database was reset")
        after = await _read("get_cash_position")
        matches = _dump(config.WORKING_DB) == _dump(config.ORIGINAL_DB)
        original_ok = file_sha256(config.ORIGINAL_DB) == config.ORIGINAL_DB_SHA256
    result = {
        "reset": True,
        "working_db_matches_original": matches,
        "original_db_unchanged": original_ok,
        "checking_before": before["cash_accounts"][0]["balance"],
        "checking_after": after["cash_accounts"][0]["balance"],
        "payments_before": len(before["payments_recorded"]),
        "payments_after": len(after["payments_recorded"]),
        "pending_approvals_voided": voided,
    }
    log_human_action(config.AUDIT_TRAIL, "database_reset", "ok", None, **result,
                     summary=f"Working database reset to the original (checking ${result['checking_after']:,.2f})")
    return result


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"name": "Campus Customs desk API", "docs": "/docs", "routes": [
        "GET /api/health", "GET /api/tickets", "GET /api/tickets/{ticket_id}", "POST /api/tickets/{ticket_id}/status",
        "POST /api/tickets/{ticket_id}/run", "GET /api/jobs/{job_id}", "GET /api/runs", "GET /api/activity",
        "GET /api/approvals", "POST /api/approvals/{approval_id}/approve",
        "POST /api/approvals/{approval_id}/reject", "GET /api/cash", "POST /api/reset"]}
