"""Database queries behind the Campus Customs MCP tools.

Every number returned here comes straight from the working database
(data/campus_customs_new.db). Lookups use a read-only connection. The two
write actions (record_payment, update_ticket_status) live in writes.py and
are locked unless a human enables them.
"""

import os
import sqlite3
from datetime import date
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"


def db_path() -> Path:
    """Return the working database path (overridable with CAMPUS_CUSTOMS_DB)."""
    return Path(os.environ.get("CAMPUS_CUSTOMS_DB", DEFAULT_DB_PATH)).resolve()


def connect() -> sqlite3.Connection:
    path = db_path()
    if not path.exists():
        raise FileNotFoundError(f"Working database not found: {path}")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _today(conn: sqlite3.Connection) -> date:
    """The store's 'today' comes from the desk table, not the real calendar."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def _ticket(conn: sqlite3.Connection, ticket_id: int, expected_type: str) -> dict:
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise ValueError(f"Ticket {ticket_id} does not exist.")
    if row["type"] != expected_type:
        raise ValueError(
            f"Ticket {ticket_id} is a '{row['type']}' ticket; this tool handles '{expected_type}' tickets."
        )
    return dict(row)


def _money(value: float) -> float:
    return round(value, 2)


def check_order_fulfillment(ticket_id: int) -> dict:
    """Ticket 101: can a customer order be filled, and what is blocking it?"""
    with connect() as conn:
        today = _today(conn)
        ticket = _ticket(conn, ticket_id, "customer_order")

        stock = conn.execute(
            "SELECT name, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        ).fetchone()
        other_sizes = conn.execute(
            "SELECT size, qty FROM inventory WHERE sku = ? AND size != ? AND qty > 0",
            (ticket["sku"], ticket["size"]),
        ).fetchall()
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)
        ).fetchone()

        invoice = None
        if ticket["invoice_id"] is not None:
            row = conn.execute(
                """SELECT i.id, i.amount, i.due_date, i.status, i.description,
                          v.name AS vendor_name, v.specialty, v.lead_days
                   FROM invoices i JOIN vendors v ON v.id = i.vendor_id
                   WHERE i.id = ?""",
                (ticket["invoice_id"],),
            ).fetchone()
            if row is not None:
                due = date.fromisoformat(row["due_date"])
                invoice = {
                    "invoice_id": row["id"],
                    "description": row["description"],
                    "amount": _money(row["amount"]),
                    "due_date": row["due_date"],
                    "status": row["status"],
                    "days_overdue": max((today - due).days, 0),
                    "vendor": row["vendor_name"],
                    "vendor_specialty": row["specialty"],
                    "vendor_lead_days": row["lead_days"],
                }

    in_stock = stock["qty"] if stock else 0
    requested = ticket["qty"] or 0
    return {
        "today": today.isoformat(),
        "ticket": ticket,
        "product": stock["name"] if stock else None,
        "location": stock["location"] if stock else None,
        "requested_qty": requested,
        "in_stock_qty": in_stock,
        "can_fill_now": in_stock >= requested,
        "shortfall": max(requested - in_stock, 0),
        "other_sizes_in_stock": {r["size"]: r["qty"] for r in other_sizes},
        "list_price": _money(price["list_price"]) if price else None,
        "unit_cost": _money(price["unit_cost"]) if price else None,
        "linked_invoice": invoice,
    }


def check_cash_for_rent(ticket_id: int) -> dict:
    """Ticket 102: is there enough cash for rent, alongside the other open bills?"""
    with connect() as conn:
        today = _today(conn)
        ticket = _ticket(conn, ticket_id, "rent_notice")

        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone()
        if lease is None:
            raise ValueError(f"Ticket {ticket_id} does not link to an existing lease.")
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()
        open_invoices = conn.execute(
            """SELECT i.id, i.amount, i.due_date, i.description, v.name AS vendor_name
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.status = 'open' ORDER BY i.due_date"""
        ).fetchall()
        payments = conn.execute("SELECT kind, ref_id, amount, paid_at FROM payments").fetchall()

    cash = sum(a["balance"] for a in accounts)
    rent = lease["monthly_rent"]
    invoices_total = sum(i["amount"] for i in open_invoices)
    return {
        "today": today.isoformat(),
        "ticket": ticket,
        "lease": {
            "lease_id": lease["id"],
            "space_name": lease["space_name"],
            "landlord": lease["landlord"],
            "monthly_rent": _money(rent),
            "next_due": lease["next_due"],
            "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
        },
        "cash_accounts": [
            {"name": a["name"], "balance": _money(a["balance"]), "as_of": a["date"]} for a in accounts
        ],
        "total_cash": _money(cash),
        "open_invoices": [
            {
                "invoice_id": i["id"],
                "vendor": i["vendor_name"],
                "amount": _money(i["amount"]),
                "due_date": i["due_date"],
                "days_overdue": max((today - date.fromisoformat(i["due_date"])).days, 0),
                "description": i["description"],
            }
            for i in open_invoices
        ],
        "open_invoices_total": _money(invoices_total),
        "payments_already_recorded": [dict(p) for p in payments],
        "cash_after_rent": _money(cash - rent),
        "cash_after_rent_and_open_invoices": _money(cash - rent - invoices_total),
        "can_pay_rent": cash >= rent,
        "can_pay_rent_and_open_invoices": cash >= rent + invoices_total,
    }


def evaluate_bulk_discount(ticket_id: int, discount_percent: float | None = None) -> dict:
    """Ticket 103: how much stock is there, and what would a discount do to margin?"""
    if discount_percent is not None and not 0 <= discount_percent <= 100:
        raise ValueError("discount_percent must be between 0 and 100.")

    with connect() as conn:
        today = _today(conn)
        ticket = _ticket(conn, ticket_id, "price_override")

        sizes = conn.execute(
            "SELECT size, qty, name, location FROM inventory WHERE sku = ?", (ticket["sku"],)
        ).fetchall()
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)
        ).fetchone()
    if price is None:
        raise ValueError(f"No pricing found for {ticket['sku']}.")

    stock_by_size = {r["size"]: r["qty"] for r in sizes}
    requested = ticket["qty"] or 0
    in_size = stock_by_size.get(ticket["size"], 0)
    cost, list_price = price["unit_cost"], price["list_price"]

    result = {
        "today": today.isoformat(),
        "ticket": ticket,
        "product": sizes[0]["name"] if sizes else None,
        "location": sizes[0]["location"] if sizes else None,
        "requested_qty": requested,
        "requested_size": ticket["size"],
        "in_stock_requested_size": in_size,
        "shortfall_in_requested_size": max(requested - in_size, 0),
        "stock_by_size": stock_by_size,
        "total_stock_all_sizes": sum(stock_by_size.values()),
        "unit_cost": _money(cost),
        "list_price": _money(list_price),
        "margin_per_unit_at_list": _money(list_price - cost),
        "max_discount_percent_before_loss": _money((list_price - cost) / list_price * 100),
        "order_revenue_at_list": _money(list_price * requested),
        "order_profit_at_list": _money((list_price - cost) * requested),
    }
    if discount_percent is not None:
        unit_price = list_price * (1 - discount_percent / 100)
        result["proposed_discount"] = {
            "discount_percent": discount_percent,
            "unit_price": _money(unit_price),
            "margin_per_unit": _money(unit_price - cost),
            "order_revenue": _money(unit_price * requested),
            "order_profit": _money((unit_price - cost) * requested),
            "below_cost": unit_price < cost,
        }
    return result


# --- General lookups added in Problem 5 for the multi-agent team -----------


def get_desk_overview() -> dict:
    """Today's date, every ticket, and the headline cash and bill figures."""
    with connect() as conn:
        today = _today(conn)
        desk = conn.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
        tickets = conn.execute(
            "SELECT id, type, requester, subject, status, created_at FROM tickets ORDER BY id"
        ).fetchall()
        cash = conn.execute("SELECT COALESCE(SUM(balance), 0) FROM cash_accounts").fetchone()[0]
        open_bills = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM invoices WHERE status = 'open'"
        ).fetchone()
        leases = conn.execute("SELECT id, monthly_rent, next_due FROM leases ORDER BY next_due").fetchall()
        payments = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    return {
        "today": today.isoformat(),
        "desk_notes": desk["notes"],
        "tickets": [dict(t) for t in tickets],
        "open_ticket_ids": [t["id"] for t in tickets if t["status"] == "open"],
        "total_cash": _money(cash),
        "open_invoice_count": open_bills[0],
        "open_invoices_total": _money(open_bills[1]),
        "upcoming_rent": [
            {
                "lease_id": l["id"],
                "monthly_rent": _money(l["monthly_rent"]),
                "next_due": l["next_due"],
                "days_until_due": (date.fromisoformat(l["next_due"]) - today).days,
            }
            for l in leases
        ],
        "payments_recorded": payments,
    }


def get_ticket(ticket_id: int) -> dict:
    """One ticket of any type, plus the lease or invoice it links to."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise ValueError(f"Ticket {ticket_id} does not exist.")
        ticket = dict(row)
        lease = invoice = None
        if ticket["lease_id"] is not None:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone()
        if ticket["invoice_id"] is not None:
            invoice = conn.execute(
                """SELECT i.*, v.name AS vendor_name FROM invoices i
                   JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?""",
                (ticket["invoice_id"],),
            ).fetchone()
        today = _today(conn)
    return {
        "today": today.isoformat(),
        "ticket": ticket,
        "linked_lease": dict(lease) if lease else None,
        "linked_invoice": dict(invoice) if invoice else None,
    }


def check_stock(sku: str, size: str | None = None) -> dict:
    """Stock for a SKU (every size, or one size) with its cost and list price."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT size, qty, name, location FROM inventory WHERE sku = ? ORDER BY size", (sku,)
        ).fetchall()
        price = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if not rows:
        raise ValueError(f"SKU {sku} is not in inventory.")
    by_size = {r["size"]: r["qty"] for r in rows}
    result = {
        "sku": sku,
        "product": rows[0]["name"],
        "location": rows[0]["location"],
        "stock_by_size": by_size,
        "total_stock": sum(by_size.values()),
        "unit_cost": _money(price["unit_cost"]) if price else None,
        "list_price": _money(price["list_price"]) if price else None,
    }
    if size is not None:
        result["size"] = size
        result["in_stock_qty"] = by_size.get(size, 0)
    return result


def list_vendors() -> dict:
    """Every vendor with its specialty, lead time, and open invoices."""
    with connect() as conn:
        today = _today(conn)
        vendors = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        invoices = conn.execute(
            "SELECT id, vendor_id, amount, due_date, status FROM invoices WHERE status = 'open'"
        ).fetchall()
    return {
        "today": today.isoformat(),
        "vendors": [
            {
                **dict(v),
                "open_invoices": [
                    {
                        "invoice_id": i["id"],
                        "amount": _money(i["amount"]),
                        "due_date": i["due_date"],
                        "days_overdue": max((today - date.fromisoformat(i["due_date"])).days, 0),
                    }
                    for i in invoices
                    if i["vendor_id"] == v["id"]
                ],
            }
            for v in vendors
        ],
    }


def get_lease(lease_id: int) -> dict:
    """A lease with its rent, due date, days until due, and rent already paid."""
    with connect() as conn:
        today = _today(conn)
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            raise ValueError(f"Lease {lease_id} does not exist.")
        paid = conn.execute(
            "SELECT id, amount, paid_at, approved_by FROM payments WHERE kind = 'rent' AND ref_id = ?",
            (lease_id,),
        ).fetchall()
    return {
        "today": today.isoformat(),
        "lease": dict(lease),
        "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
        "rent_payments_recorded": [dict(p) for p in paid],
    }


def get_cash_position() -> dict:
    """Cash, every open invoice, upcoming rent, and what is left after paying them."""
    with connect() as conn:
        today = _today(conn)
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()
        invoices = conn.execute(
            """SELECT i.id, i.amount, i.due_date, i.description, v.name AS vendor_name
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.status = 'open' ORDER BY i.due_date"""
        ).fetchall()
        leases = conn.execute("SELECT * FROM leases ORDER BY next_due").fetchall()
        payments = conn.execute("SELECT * FROM payments ORDER BY id").fetchall()
    cash = sum(a["balance"] for a in accounts)
    bills = sum(i["amount"] for i in invoices)
    rent = sum(l["monthly_rent"] for l in leases)
    return {
        "today": today.isoformat(),
        "cash_accounts": [
            {"name": a["name"], "balance": _money(a["balance"]), "as_of": a["date"]} for a in accounts
        ],
        "total_cash": _money(cash),
        "open_invoices": [
            {
                "invoice_id": i["id"],
                "vendor": i["vendor_name"],
                "amount": _money(i["amount"]),
                "due_date": i["due_date"],
                "days_overdue": max((today - date.fromisoformat(i["due_date"])).days, 0),
                "description": i["description"],
            }
            for i in invoices
        ],
        "open_invoices_total": _money(bills),
        "upcoming_rent": [
            {
                "lease_id": l["id"],
                "landlord": l["landlord"],
                "monthly_rent": _money(l["monthly_rent"]),
                "next_due": l["next_due"],
                "days_until_due": (date.fromisoformat(l["next_due"]) - today).days,
            }
            for l in leases
        ],
        "payments_recorded": [dict(p) for p in payments],
        "cash_after_rent": _money(cash - rent),
        "cash_after_rent_and_open_invoices": _money(cash - rent - bills),
    }


PAYMENT_KINDS = ("rent", "invoice")


def check_payment(conn: sqlite3.Connection, kind: str, ref_id: int, amount: float) -> list[str]:
    """Problems with one proposed payment (an empty list means it is valid)."""
    problems = []
    if kind not in PAYMENT_KINDS:
        return [f"kind must be one of {PAYMENT_KINDS}, not '{kind}'."]
    if amount <= 0:
        problems.append("amount must be greater than 0.")
    if kind == "rent":
        lease = conn.execute("SELECT monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,)).fetchone()
        if lease is None:
            return problems + [f"Lease {ref_id} does not exist."]
        if round(amount, 2) != round(lease["monthly_rent"], 2):
            problems.append(f"Rent for lease {ref_id} is {lease['monthly_rent']:.2f}, not {amount:.2f}.")
        due = date.fromisoformat(lease["next_due"])
        already = conn.execute(
            "SELECT COUNT(*) FROM payments WHERE kind = 'rent' AND ref_id = ? AND paid_at >= ?",
            (ref_id, date.fromordinal(due.toordinal() - 31).isoformat()),
        ).fetchone()[0]
        if already:
            problems.append(f"Rent for lease {ref_id} due {lease['next_due']} is already recorded as paid.")
    else:
        invoice = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
        if invoice is None:
            return problems + [f"Invoice {ref_id} does not exist."]
        if invoice["status"] != "open":
            problems.append(f"Invoice {ref_id} is '{invoice['status']}', not open.")
        if round(amount, 2) != round(invoice["amount"], 2):
            problems.append(f"Invoice {ref_id} is for {invoice['amount']:.2f}, not {amount:.2f}.")
    return problems


def preview_payments(payments: list[dict], account: str = "checking") -> dict:
    """Dry run: check a batch of payments in order without paying anything.

    Each payment is {"kind": "rent" | "invoice", "ref_id": int, "amount": float}.
    Cash is drawn down in the order given, and the batch fails if the account
    would go negative at any point.
    """
    with connect() as conn:
        today = _today(conn)
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            raise ValueError(f"Cash account '{account}' does not exist.")
        balance = acct["balance"]
        items, all_valid = [], True
        for p in payments:
            kind, ref_id, amount = p.get("kind"), int(p.get("ref_id", 0)), float(p.get("amount", 0))
            problems = check_payment(conn, kind, ref_id, amount)
            balance -= amount
            if balance < 0:
                problems.append(f"Paying this would leave {account} at {balance:.2f} (negative).")
            all_valid = all_valid and not problems
            items.append({
                "kind": kind,
                "ref_id": ref_id,
                "amount": _money(amount),
                "balance_after": _money(balance),
                "valid": not problems,
                "problems": problems,
            })
    return {
        "today": today.isoformat(),
        "account": account,
        "starting_balance": _money(acct["balance"]),
        "ending_balance": _money(balance),
        "payments": items,
        "all_valid": all_valid,
        "cash_stays_non_negative": balance >= 0,
        "executed": False,
        "requires_human_approval": True,
        "note": "Preview only. Nothing was paid. A human must approve before record_payment can run.",
    }
