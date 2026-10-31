"""Offline checks for the agent team: no model calls, no tokens.

A scripted FunctionModel plays each agent so we can force the cases a real
model might try: delegating back to the Boss, delegating to itself, going
too deep, and calling a payment tool. The MCP server runs in-process on the
working database (read-only; writes stay locked). The audit trail is written
to a temporary file, not output/audit_trail.json.

    .venv\\Scripts\\python.exe backend/test_team.py
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

os.environ["CAMPUS_CUSTOMS_DB"] = str(config.WORKING_DB)
for k in ("CAMPUS_CUSTOMS_ALLOW_WRITES", "CAMPUS_CUSTOMS_APPROVAL_CODE"):
    os.environ.pop(k, None)
sys.path.insert(0, str(config.MCP_SERVER.parent))

from pydantic import ValidationError  # noqa: E402
from pydantic_ai import ModelResponse, ToolCallPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402

import server  # noqa: E402  (in-process FastMCP server)
from audit import RunAudit, file_sha256, load_trail  # noqa: E402
from team import (CampusTeam, CustomerDraft, DelegationBudget, PaymentRequest, TeamDeps,  # noqa: E402
                  delegation_refusal)

logging.getLogger("fastmcp").setLevel(logging.CRITICAL)

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}")


# --- Scripted "model": each agent follows a fixed plan, then answers ---------

ROLES = {f"# Role: {title}": name for title, name in [
    ("Boss", "boss"), ("Inventory", "inventory"), ("Accounting", "accounting"),
    ("Facilities", "facilities"), ("Customer Service", "customer_service")]}

PLANS = {
    "boss": [("get_ticket", {"ticket_id": 102}),
             ("delegate", {"to_agent": "facilities", "task": "Confirm lease 1 rent and due date for ticket 102."})],
    "facilities": [("delegate", {"to_agent": "boss", "task": "Can you check this for me?"}),          # loop
                   ("delegate", {"to_agent": "facilities", "task": "Check it again."}),               # self
                   ("delegate", {"to_agent": "accounting", "task": "Can cash cover rent? Preview it."})],
    "accounting": [("get_cash_position", {}),
                   ("preview_payments", {"payments": [{"kind": "rent", "ref_id": 1, "amount": 2400},
                                                      {"kind": "invoice", "ref_id": 501, "amount": 840}]}),
                   ("record_payment", {"kind": "rent", "ref_id": 1, "amount": 2400,            # not allowed
                                       "approved_by": "accounting", "approval_code": "guess"})],
}
tools_seen: dict[str, list[list[str]]] = {}


def scripted(messages, info: AgentInfo) -> ModelResponse:
    role = next(v for k, v in ROLES.items() if info.instructions and info.instructions.startswith(k))
    tools_seen.setdefault(role, []).append(sorted(t.name for t in info.function_tools))
    step = sum(isinstance(m, ModelResponse) for m in messages)
    plan = PLANS.get(role, [])
    if step < len(plan):
        name, args = plan[step]
        return ModelResponse(parts=[ToolCallPart(name, args)])
    report = {"ticket_id": 102, "summary": f"{role} finished", "key_facts": [],
              "recommendation": "test", "needs_human_approval": True}
    if role == "accounting":
        report["payment_requests"] = [{"kind": "rent", "ref_id": 1, "amount": 2400, "reason": "rent due in 2 days"}]
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, report)])


async def main() -> int:
    db_before = {p.name: file_sha256(p) for p in (config.ORIGINAL_DB, config.WORKING_DB)}

    # 1. Delegation rules on their own.
    b = DelegationBudget(config.MAX_DELEGATIONS_PER_TICKET)
    check("refuses delegating to itself", delegation_refusal(TeamDeps(1, ("boss",), b), "boss"))
    check("refuses delegating back up the chain (loop)",
          "loop" in delegation_refusal(TeamDeps(1, ("boss", "inventory"), b), "boss"))
    check("refuses going past the depth limit",
          "depth" in delegation_refusal(TeamDeps(1, ("boss", "inventory", "accounting"), b), "facilities"))
    check("refuses once the per-ticket delegation budget is used",
          "limit" in delegation_refusal(TeamDeps(1, ("boss",), DelegationBudget(5, used=5)), "inventory"))
    check("refuses an unknown agent", delegation_refusal(TeamDeps(1, ("boss",), b), "marketing"))
    check("allows a normal delegation", delegation_refusal(TeamDeps(1, ("boss",), b), "accounting") is None)

    # 2. Output types: payments stay pending, messages stay drafts.
    for bad, label in [(lambda: PaymentRequest(kind="rent", ref_id=1, amount=1, reason="x", status="paid"),
                        "a payment cannot be marked paid by an agent"),
                       (lambda: CustomerDraft(to="a", subject="b", body="c", status="sent"),
                        "a customer message cannot be marked sent")]:
        try:
            bad()
            check(label, False)
        except ValidationError:
            check(label, True)

    # 3. Tool access: nobody gets the human-only tools; every agent can delegate.
    check("no agent is given record_payment or update_ticket_status",
          not any(set(v) & config.HUMAN_ONLY_TOOLS for v in config.AGENT_TOOLS.values()))

    # 4. A scripted ticket run through the real team code and an in-process MCP server.
    with tempfile.TemporaryDirectory() as tmp:
        trail = Path(tmp) / "audit_trail.json"
        audit = RunAudit(trail, mode="offline test", settings={})
        team = CampusTeam(audit, model=FunctionModel(scripted), mcp_client=server.mcp)
        async with team.mcp:
            report, usage, used = await team.handle_ticket(102)
        audit.append_to_trail("ok")
        ev = audit.run["events"]

        def events(kind):
            return [e for e in ev if e["event"] == kind]

        delegs = [(e["agent"], e["to_agent"]) for e in events("delegation")]
        refused = [(e["agent"], e["to_agent"]) for e in events("delegation_refused")]
        check("boss -> facilities -> accounting delegations ran", delegs == [("boss", "facilities"),
                                                                           ("facilities", "accounting")])
        check("facilities -> boss (loop) and facilities -> facilities (self) were refused",
              refused == [("facilities", "boss"), ("facilities", "facilities")])
        check("delegation count matches the budget used", used == 2)
        check("boss and facilities are offered delegate below the depth limit",
              all("delegate" in tools_seen[r][0] for r in ("boss", "facilities")))
        check("delegate is hidden from accounting at the depth limit",
              all("delegate" not in t for t in tools_seen["accounting"]))
        check("each agent sees only its own MCP tools", all(
            set(t) - {"delegate"} <= config.AGENT_TOOLS[r] for r, ts in tools_seen.items() for t in ts))
        check("record_payment was never executed (unknown to accounting)",
              not any(e.get("tool") == "record_payment" for e in events("mcp_tool_call")))
        prev = next(e for e in events("mcp_tool_call") if e["tool"] == "preview_payments")
        check("accounting's payment preview ran over MCP and ends at 160",
              prev["result"]["ending_balance"] == 160 and prev["result"]["executed"] is False)
        check("boss returned a final report", report.ticket_id == 102 and usage.requests > 0)

        # 5. Audit trail: append-only and tamper-evident.
        audit2 = RunAudit(trail, mode="offline test 2", settings={})
        audit2.log("note", text="second run")
        audit2.append_to_trail("ok")
        data = load_trail(trail)
        check("second run appended, first run kept",
              len(data["runs"]) == 2 and data["runs"][1]["prev_run_hash"] == data["runs"][0]["run_hash"])
        data["runs"][0]["events"][0]["event"] = "edited"
        trail.write_text(json.dumps(data), encoding="utf-8")
        try:
            load_trail(trail)
            check("editing an earlier run is detected", False)
        except RuntimeError:
            check("editing an earlier run is detected", True)

    db_after = {p.name: file_sha256(p) for p in (config.ORIGINAL_DB, config.WORKING_DB)}
    check("databases unchanged", db_after == db_before)
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
