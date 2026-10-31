"""Offline checks for the money routes in main.py: no model calls, no tokens.

Runs the FastAPI app in-process against a TEMPORARY copy of the working
database, a temporary approvals file, and a temporary audit trail, so the
real files are never touched. Covers the cases a normal agent run can't
reach: an approval that would overdraw cash, and reset restoring the copy.

    .venv\\Scripts\\python.exe backend/test_api.py
"""

import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

CODE = "offline-test-code"
os.environ["CAMPUS_CUSTOMS_APPROVAL_CODE"] = CODE
logging.getLogger("fastmcp").setLevel(logging.CRITICAL)

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    results.append((name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {extra}")


def main() -> int:
    from audit import file_sha256

    real = {p: file_sha256(p) for p in (config.ORIGINAL_DB, config.WORKING_DB)}
    real_approvals = config.APPROVALS_FILE.read_bytes() if config.APPROVALS_FILE.exists() else None
    real_trail = file_sha256(config.AUDIT_TRAIL)
    tmp = Path(tempfile.mkdtemp())
    try:
        db = tmp / "campus_customs_test_copy.db"
        shutil.copyfile(config.WORKING_DB, db)
        with sqlite3.connect(db) as w:
            w.execute("UPDATE cash_accounts SET balance = 1000 WHERE name = 'checking'")
        config.WORKING_DB = db
        config.APPROVALS_FILE = tmp / "approvals.json"
        config.AUDIT_TRAIL = tmp / "audit_trail.json"
        rent = {"id": "appr-test-rent", "status": "pending", "kind": "rent", "label": "Rent payment", "ref_id": 1,
                "amount": 2400.0, "reason": "test", "proposed_at": "x", "proposed_by": "agent team",
                "ticket_ids": [102], "run_ids": ["test"], "decided_at": None, "decided_by": None, "outcome": None}
        config.APPROVALS_FILE.write_text(json.dumps({"approvals": [rent]}), encoding="utf-8")

        import main  # imported after the paths point at the temp files
        from approvals import ApprovalStore
        from fastapi.testclient import TestClient

        main.approvals = ApprovalStore(config.APPROVALS_FILE)
        with TestClient(main.app) as client:
            cash = client.get("/api/cash").json()
            check("temp copy starts at $1,000 with $2,400 rent pending", cash["balance"] == 1000
                  and cash["pending_approvals_keep_cash_non_negative"] is False)
            r = client.post("/api/approvals/appr-test-rent/approve",
                            json={"approved_by": "Tejesh Marsale", "approval_code": CODE})
            after = client.get("/api/cash").json()
            item = client.get("/api/approvals").json()["approvals"][0]
            check("approval that would overdraw cash -> 409, nothing paid", r.status_code == 409
                  and after["balance"] == 1000 and not after["payments_recorded"], str(r.json())[:160])
            check("blocked approval stays pending for a human to reject", item["status"] == "pending")
            r = client.post("/api/approvals/appr-test-rent/reject", json={"rejected_by": "Tejesh Marsale"})
            check("reject it", r.status_code == 200 and r.json()["approval"]["status"] == "rejected")
            r = client.post("/api/tickets/102/status",
                            json={"status": "resolved", "approved_by": "Tejesh Marsale", "approval_code": "nope"})
            check("status change with a wrong code -> 403", r.status_code == 403)
            r = client.post("/api/tickets/102/status",
                            json={"status": "resolved", "approved_by": "Tejesh Marsale", "approval_code": CODE})
            t = {x["id"]: x["status"] for x in client.get("/api/tickets").json()["tickets"]}
            check("human marks ticket 102 resolved", r.status_code == 200 and t[102] == "resolved", str(t))
            r = client.post("/api/reset", json={"confirm": True})
            body = r.json()
            check("reset restores the temp copy to the original ($3,400)", r.status_code == 200
                  and body["checking_after"] == 3400 and body["working_db_matches_original"], json.dumps(body))
            trail = json.loads(config.AUDIT_TRAIL.read_text(encoding="utf-8"))
            events = [r["events"][0]["event"] for r in trail["runs"]]
            check("blocked payment, rejection, status changes, and reset are in the (temp) audit trail",
                  events == ["human_payment_blocked", "human_payment_rejected", "human_status_change_denied",
                             "human_ticket_status_changed", "human_database_reset"], str(events))
            t = {x["id"]: x["status"] for x in client.get("/api/tickets").json()["tickets"]}
            check("reset puts ticket 102 back to open", t[102] == "open")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    check("real databases unchanged", all(file_sha256(p) == h for p, h in real.items()))
    real_approvals_path = config.HW5_DIR / "output" / "approvals.json"
    check("real approvals file and audit trail unchanged",
          (real_approvals_path.read_bytes() if real_approvals_path.exists() else None) == real_approvals
          and file_sha256(config.HW5_DIR / "output" / "audit_trail.json") == real_trail)
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
