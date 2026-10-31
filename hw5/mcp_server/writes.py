"""The two Campus Customs actions that change the working database.

Both are locked by default. They run only when a human has:
  1. set CAMPUS_CUSTOMS_ALLOW_WRITES=1 for the server process, and
  2. supplied the approval code from CAMPUS_CUSTOMS_APPROVAL_CODE, which is
     never given to the AI agents.
They also refuse to touch the original data/campus_customs.db.
"""

import hmac
import os
import sqlite3

from queries import PAYMENT_KINDS, _money, _today, check_payment, db_path

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}
TICKET_STATUSES = ("open", "in_progress", "waiting_on_customer", "resolved")


def _authorize(approved_by: str, approval_code: str) -> None:
    if os.environ.get("CAMPUS_CUSTOMS_ALLOW_WRITES") != "1":
        raise PermissionError("Writes are disabled. A human must set CAMPUS_CUSTOMS_ALLOW_WRITES=1.")
    expected = os.environ.get("CAMPUS_CUSTOMS_APPROVAL_CODE", "")
    if not expected or not hmac.compare_digest(approval_code or "", expected):
        raise PermissionError("Missing or wrong human approval code.")
    name = (approved_by or "").strip()
    if not name or name.lower() in AGENT_NAMES or "agent" in name.lower():
        raise PermissionError("approved_by must name the human who approved this action.")


def _connect_rw() -> sqlite3.Connection:
    path = db_path()
    if path.name == "campus_customs.db":
        raise PermissionError("The original database is never changed.")
    if not path.exists():
        raise FileNotFoundError(f"Working database not found: {path}")
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def record_payment(kind: str, ref_id: int, amount: float, approved_by: str,
                   approval_code: str, account: str = "checking") -> dict:
    """Record one human-approved payment and take it out of the cash account."""
    _authorize(approved_by, approval_code)
    if kind not in PAYMENT_KINDS:
        raise ValueError(f"kind must be one of {PAYMENT_KINDS}.")
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        problems = check_payment(conn, kind, ref_id, amount)
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            problems.append(f"Cash account '{account}' does not exist.")
        elif acct["balance"] - amount < 0:
            problems.append(f"Paying {amount:.2f} would leave {account} at {acct['balance'] - amount:.2f}.")
        if problems:
            conn.execute("ROLLBACK")
            return {"executed": False, "problems": problems}
        today = _today(conn).isoformat()
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account, today, approved_by.strip()),
        )
        conn.execute("UPDATE cash_accounts SET balance = balance - ? WHERE name = ?", (amount, account))
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
        new_balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()[0]
        if new_balance < 0:  # belt and braces: never commit a negative balance
            conn.execute("ROLLBACK")
            return {"executed": False, "problems": ["Balance would go negative."]}
        conn.execute("COMMIT")
        return {"executed": True, "payment_id": cur.lastrowid, "kind": kind, "ref_id": ref_id,
                "amount": _money(amount), "account": account, "balance_after": _money(new_balance),
                "approved_by": approved_by.strip(), "paid_at": today}
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def update_ticket_status(ticket_id: int, status: str, approved_by: str, approval_code: str) -> dict:
    """Change a ticket's status after a human has approved it."""
    _authorize(approved_by, approval_code)
    if status not in TICKET_STATUSES:
        raise ValueError(f"status must be one of {TICKET_STATUSES}.")
    conn = _connect_rw()
    try:
        row = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise ValueError(f"Ticket {ticket_id} does not exist.")
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        return {"executed": True, "ticket_id": ticket_id, "old_status": row["status"],
                "new_status": status, "approved_by": approved_by.strip()}
    finally:
        conn.close()
