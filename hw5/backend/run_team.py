"""Run the Campus Customs agent team on tickets.

    .venv\\Scripts\\python.exe backend/run_team.py            # tickets 101, 102, 103
    .venv\\Scripts\\python.exe backend/run_team.py 102        # one ticket

The FastAPI backend (main.py) calls run_tickets() for one ticket at a time.

Agents investigate, delegate, and propose. They never record a payment or
change a ticket status: they have no write tools and their MCP server is
started with writes locked. Payments are executed only when a human approves
them through the backend. Each run is appended to output/audit_trail.json.
"""

import asyncio
import json
import sys
from typing import Any, Callable

from pydantic_ai import UsageLimitExceeded

import config
from audit import RunAudit, file_sha256
from team import CampusTeam, usage_dict


def _settings() -> dict:
    lim = config.TICKET_USAGE_LIMITS
    return {
        "model": config.MODEL_NAME,
        "gateway": "Portkey",
        "agents": list(config.TEAM),
        "agent_tools": {k: sorted(v) for k, v in config.AGENT_TOOLS.items()},
        "human_only_tools": sorted(config.HUMAN_ONLY_TOOLS),
        "max_delegation_depth": config.MAX_DELEGATION_DEPTH,
        "max_delegations_per_ticket": config.MAX_DELEGATIONS_PER_TICKET,
        "ticket_usage_limits": {"request_limit": lim.request_limit, "tool_calls_limit": lim.tool_calls_limit,
                                "total_tokens_limit": lim.total_tokens_limit},
        "run_token_budget": config.RUN_TOKEN_BUDGET,
        "max_output_tokens_per_request": config.MODEL_SETTINGS.get("max_tokens"),
    }


def _structured(result) -> dict:
    """Turn an MCP tool result into a dict."""
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        return json.loads(result)
    return dict(result)


def _quiet(*_args: Any, **_kwargs: Any) -> None:
    pass


async def run_tickets(ticket_ids: list[int], mode: str = "agents propose; humans approve payments",
                      echo: Callable[..., None] = _quiet,
                      listener: Callable[[str, dict], None] | None = None) -> dict:
    """Run the team on each ticket, append the run to the audit trail, and return it.

    `listener(run_id, event)` is called for every event as it happens.
    """
    db_before = {p.name: file_sha256(p) for p in (config.ORIGINAL_DB, config.WORKING_DB)}
    audit = RunAudit(config.AUDIT_TRAIL, mode=mode, settings=_settings(), listener=listener)
    audit.log("run_started", tickets=ticket_ids, db_sha256_before=db_before)
    team = CampusTeam(audit)
    results, status, run_tokens = [], "ok", 0
    guardrails: dict = {}
    try:
        async with team.mcp:
            for tid in ticket_ids:
                if run_tokens >= config.RUN_TOKEN_BUDGET:
                    audit.log("ticket_skipped", ticket_id=tid, reason="run token budget used up")
                    status = "partial"
                    continue
                echo(f"\n=== Ticket {tid} ===", flush=True)
                try:
                    report, usage, delegations = await team.handle_ticket(tid)
                except UsageLimitExceeded as e:
                    audit.log("ticket_stopped_by_limit", ticket_id=tid, error=str(e))
                    echo(f"  stopped by limit: {e}")
                    status = "partial"
                    continue
                u = usage_dict(usage)
                run_tokens += u["total_tokens"]
                results.append({"ticket_id": tid, "decision": report.model_dump(),
                                "delegations_used": delegations, "usage": u})
                audit.log("ticket_decision", "boss", tid, decision=report.model_dump(), usage=u)
                echo(f"  {report.summary}\n  recommendation: {report.recommendation}")
                echo(f"  delegations: {delegations}, tokens: {u['total_tokens']}, requests: {u['requests']}")

            # Guardrail: all proposed payments together must keep cash non-negative.
            pending, seen = [], set()
            for r in results:
                for p in r["decision"]["payment_requests"]:
                    if (p["kind"], p["ref_id"]) not in seen:
                        seen.add((p["kind"], p["ref_id"]))
                        pending.append({"kind": p["kind"], "ref_id": p["ref_id"], "amount": p["amount"]})
            pending.sort(key=lambda p: p["kind"] != "rent")  # rent first
            preview = (_structured(await team.mcp.direct_call_tool("preview_payments", {"payments": pending}))
                       if pending else None)
            audit.log("guardrail_payment_preview", pending_payments=pending, preview=preview)
            drafts = [r["decision"]["customer_draft"] for r in results if r["decision"]["customer_draft"]]
            guardrails = {
                "pending_payments_for_human_approval": pending,
                "pending_payments_valid_and_cash_non_negative": bool(preview and preview["all_valid"]) if pending else True,
                "cash_after_all_pending_payments": preview["ending_balance"] if preview else None,
                "customer_drafts": len(drafts),
                "all_customer_messages_are_drafts": all(d["status"] == "draft" for d in drafts),
                "human_only_tools_given_to_agents": sorted(
                    {t for tools in config.AGENT_TOOLS.values() for t in tools} & config.HUMAN_ONLY_TOOLS),
                "mcp_tool_calls_refused": sum(e["event"] == "mcp_tool_refused" for e in audit.run["events"]),
                "delegations_refused": sum(e["event"] == "delegation_refused" for e in audit.run["events"]),
            }
    except Exception as e:
        status = "error"
        audit.log("run_error", error=f"{type(e).__name__}: {e}")
        raise
    finally:
        db_after = {p.name: file_sha256(p) for p in (config.ORIGINAL_DB, config.WORKING_DB)}
        # Agents can't write, so unchanged hashes show no payment or status change happened during the run.
        guardrails["databases_unchanged"] = db_after == db_before
        audit.log("run_finished", db_sha256_after=db_after, databases_unchanged=db_after == db_before)
        audit.append_to_trail(status, tickets=ticket_ids, results=results, guardrails=guardrails,
                              run_total_tokens=run_tokens)
        echo(f"\nAudit: appended {audit.run_id} to {config.AUDIT_TRAIL.relative_to(config.HW5_DIR)}")
    return audit.run


async def main(ticket_ids: list[int]) -> int:
    run = await run_tickets(ticket_ids, mode="test (no payments executed, no ticket status changes)", echo=print)
    print(json.dumps(run["guardrails"], indent=2))
    return 0 if run["status"] == "ok" else 1


if __name__ == "__main__":
    ids = [int(a) for a in sys.argv[1:]] or [101, 102, 103]
    sys.exit(asyncio.run(main(ids)))
