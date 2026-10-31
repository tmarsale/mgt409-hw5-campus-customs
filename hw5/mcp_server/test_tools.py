"""Checks the Problem 5 MCP tools over a real (in-process) MCP client.

- Lookups are compared with the working database.
- preview_payments must catch wrong amounts and negative cash.
- record_payment / update_ticket_status must stay locked without a human
  approval, and must refuse a negative balance and the original database.
Write tests run only on a temporary copy; the real databases are hashed
before and after to prove they were not touched.

    .venv\\Scripts\\python.exe mcp_server/test_tools.py
"""

import asyncio
import hashlib
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
WORKING, ORIGINAL = DATA / "campus_customs_new.db", DATA / "campus_customs.db"
os.environ["CAMPUS_CUSTOMS_DB"] = str(WORKING)
for k in ("CAMPUS_CUSTOMS_ALLOW_WRITES", "CAMPUS_CUSTOMS_APPROVAL_CODE"):
    os.environ.pop(k, None)
sys.path.insert(0, str(HERE))

from fastmcp import Client  # noqa: E402

import server  # noqa: E402

logging.getLogger("fastmcp").setLevel(logging.CRITICAL)  # expected refusals would print tracebacks

EXPECTED_TOOLS = {
    "check_order_fulfillment", "check_cash_for_rent", "evaluate_bulk_discount", "get_desk_overview",
    "get_ticket", "check_stock", "list_vendors", "get_lease", "get_cash_position", "preview_payments",
    "record_payment", "update_ticket_status",
}
results: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


async def call(c: Client, tool: str, args: dict | None = None):
    r = await c.call_tool(tool, args or {}, raise_on_error=False)
    text = " ".join(getattr(b, "text", "") for b in r.content)
    return r.is_error, (r.structured_content if not r.is_error else text)


async def main() -> int:
    before = {p.name: sha(p) for p in (ORIGINAL, WORKING)}
    ro = sqlite3.connect(f"{WORKING.as_uri()}?mode=ro", uri=True)
    db_cash = ro.execute("SELECT SUM(balance) FROM cash_accounts").fetchone()[0]
    db_open = [r[0] for r in ro.execute("SELECT id FROM tickets WHERE status = 'open' ORDER BY id")]
    db_lease = ro.execute("SELECT monthly_rent, next_due FROM leases WHERE id = 1").fetchone()
    db_tee = dict(ro.execute("SELECT size, qty FROM inventory WHERE sku = 'CC-TEE-WHITE'").fetchall())
    db_lead = ro.execute("SELECT lead_days FROM vendors WHERE name = 'Bulldog Print Co'").fetchone()[0]
    ro.close()

    async with Client(server.mcp) as c:
        names = {t.name for t in await c.list_tools()}
        check("server lists all 12 tools", names == EXPECTED_TOOLS)

        _, d = await call(c, "get_desk_overview")
        check("get_desk_overview: today, open tickets, cash match DB",
              d["today"] == "2026-08-31" and d["open_ticket_ids"] == db_open and d["total_cash"] == db_cash)
        _, t = await call(c, "get_ticket", {"ticket_id": 102})
        check("get_ticket 102 links lease 1", t["linked_lease"]["id"] == 1 and t["ticket"]["type"] == "rent_notice")
        _, s = await call(c, "check_stock", {"sku": "CC-TEE-WHITE", "size": "S"})
        check("check_stock tee matches DB", s["stock_by_size"] == db_tee and s["in_stock_qty"] == 0)
        _, v = await call(c, "list_vendors")
        bp = next(x for x in v["vendors"] if x["name"] == "Bulldog Print Co")
        check("list_vendors: Bulldog lead time and overdue invoice 501",
              bp["lead_days"] == db_lead and bp["open_invoices"][0]["invoice_id"] == 501
              and bp["open_invoices"][0]["days_overdue"] == 3)
        _, l = await call(c, "get_lease", {"lease_id": 1})
        check("get_lease 1 matches DB", (l["lease"]["monthly_rent"], l["lease"]["next_due"]) == tuple(db_lease)
              and l["days_until_due"] == 2)
        _, cp = await call(c, "get_cash_position")
        check("get_cash_position: 3400 cash, 1000 after rent, 160 after rent + invoice",
              (cp["total_cash"], cp["cash_after_rent"], cp["cash_after_rent_and_open_invoices"]) == (3400, 1000, 160))

        _, ok = await call(c, "preview_payments", {"payments": [
            {"kind": "rent", "ref_id": 1, "amount": 2400}, {"kind": "invoice", "ref_id": 501, "amount": 840}]})
        check("preview rent + invoice 501: valid, ends at 160, not executed",
              ok["all_valid"] and ok["ending_balance"] == 160 and ok["executed"] is False
              and ok["requires_human_approval"] is True)
        _, bad = await call(c, "preview_payments", {"payments": [
            {"kind": "rent", "ref_id": 1, "amount": 2400}, {"kind": "invoice", "ref_id": 501, "amount": 840},
            {"kind": "invoice", "ref_id": 501, "amount": 840}]})
        check("preview that overdraws cash is flagged invalid",
              not bad["all_valid"] and not bad["cash_stays_non_negative"] and bad["ending_balance"] == -680)
        _, wrong = await call(c, "preview_payments", {"payments": [{"kind": "rent", "ref_id": 1, "amount": 2000}]})
        check("preview with wrong rent amount is flagged invalid", not wrong["all_valid"])

        err, msg = await call(c, "record_payment", {"kind": "rent", "ref_id": 1, "amount": 2400,
                                                    "approved_by": "Owner", "approval_code": "x"})
        check("record_payment locked when writes are disabled", err and "disabled" in msg)
        err, msg = await call(c, "update_ticket_status", {"ticket_id": 101, "status": "resolved",
                                                          "approved_by": "Owner", "approval_code": "x"})
        check("update_ticket_status locked when writes are disabled", err and "disabled" in msg)

        # --- write path, on a temporary copy only ---
        tmpdir = Path(tempfile.mkdtemp())
        try:
            tmp = tmpdir / "campus_customs_test_copy.db"
            shutil.copyfile(WORKING, tmp)
            os.environ.update(CAMPUS_CUSTOMS_DB=str(tmp), CAMPUS_CUSTOMS_ALLOW_WRITES="1",
                              CAMPUS_CUSTOMS_APPROVAL_CODE="test-human-code")
            pay = {"kind": "rent", "ref_id": 1, "amount": 2400, "approved_by": "Store owner"}

            err, msg = await call(c, "record_payment", {**pay, "approval_code": "guess"})
            check("record_payment refuses a wrong approval code", err and "approval code" in msg)
            err, msg = await call(c, "record_payment", {**pay, "approved_by": "accounting",
                                                        "approval_code": "test-human-code"})
            check("record_payment refuses an agent as approver", err and "human" in msg)

            with sqlite3.connect(tmp) as w:
                w.execute("UPDATE cash_accounts SET balance = 1000")
            _, r = await call(c, "record_payment", {**pay, "approval_code": "test-human-code"})
            with sqlite3.connect(tmp) as w:
                n = w.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
                bal = w.execute("SELECT balance FROM cash_accounts").fetchone()[0]
            check("record_payment refuses a payment that would make cash negative",
                  r["executed"] is False and n == 0 and bal == 1000)

            with sqlite3.connect(tmp) as w:
                w.execute("UPDATE cash_accounts SET balance = 3400")
            _, r1 = await call(c, "record_payment", {**pay, "approval_code": "test-human-code"})
            _, r2 = await call(c, "record_payment", {"kind": "invoice", "ref_id": 501, "amount": 840,
                                                     "approved_by": "Store owner", "approval_code": "test-human-code"})
            _, r3 = await call(c, "record_payment", {**pay, "approval_code": "test-human-code"})
            with sqlite3.connect(tmp) as w:
                inv = w.execute("SELECT status FROM invoices WHERE id = 501").fetchone()[0]
            check("approved rent then invoice: 1000 then 160 left, invoice marked paid",
                  r1["executed"] and r1["balance_after"] == 1000 and r2["executed"] and r2["balance_after"] == 160
                  and inv == "paid")
            check("record_payment refuses paying the same rent twice", r3["executed"] is False)
            _, st = await call(c, "update_ticket_status", {"ticket_id": 102, "status": "resolved",
                                                           "approved_by": "Store owner",
                                                           "approval_code": "test-human-code"})
            check("update_ticket_status works with human approval (temp copy)", st["new_status"] == "resolved")

            os.environ["CAMPUS_CUSTOMS_DB"] = str(ORIGINAL)
            err, msg = await call(c, "record_payment", {**pay, "approval_code": "test-human-code"})
            check("writes refuse the original database", err and "original" in msg)
        finally:
            os.environ["CAMPUS_CUSTOMS_DB"] = str(WORKING)
            for k in ("CAMPUS_CUSTOMS_ALLOW_WRITES", "CAMPUS_CUSTOMS_APPROVAL_CODE"):
                os.environ.pop(k, None)
            shutil.rmtree(tmpdir, ignore_errors=True)

    after = {p.name: sha(p) for p in (ORIGINAL, WORKING)}
    check("real databases unchanged", after == before)
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
