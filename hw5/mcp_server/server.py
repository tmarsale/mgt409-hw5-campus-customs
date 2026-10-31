"""Campus Customs MCP server.

Exposes the tools the HW5 agents use to resolve the open tickets in
data/campus_customs_new.db. Lookups are read-only. The two write tools
(record_payment, update_ticket_status) stay locked until a human enables
them and supplies an approval code. Run with:  python mcp_server/server.py
"""

from fastmcp import FastMCP

import queries
import writes

mcp = FastMCP("campus-customs")


@mcp.tool
def check_order_fulfillment(ticket_id: int) -> dict:
    """Check whether a customer_order ticket (e.g. ticket 101) can be filled.

    Returns stock for the requested SKU and size, other sizes in stock, the
    price, and any linked vendor invoice with its due date, days overdue,
    and the vendor's lead time.
    """
    return queries.check_order_fulfillment(ticket_id)


@mcp.tool
def check_cash_for_rent(ticket_id: int) -> dict:
    """Check whether the store can pay the rent in a rent_notice ticket (e.g. ticket 102).

    Returns the lease, days until rent is due, cash balances, every open
    vendor invoice, payments already recorded, and the cash left after rent
    and after rent plus all open invoices.
    """
    return queries.check_cash_for_rent(ticket_id)


@mcp.tool
def evaluate_bulk_discount(ticket_id: int, discount_percent: float | None = None) -> dict:
    """Evaluate a price_override ticket (e.g. ticket 103) for a bulk discount.

    Returns stock in the requested size and across all sizes, unit cost,
    list price, margin, and the largest discount before selling at a loss.
    If discount_percent (0-100) is given, also returns the discounted unit
    price, order revenue, order profit, and whether it falls below cost.
    """
    return queries.evaluate_bulk_discount(ticket_id, discount_percent)


@mcp.tool
def get_desk_overview() -> dict:
    """Today's store date, every ticket with its status, total cash, open bills, and upcoming rent."""
    return queries.get_desk_overview()


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Read one ticket of any type, plus the lease or vendor invoice it links to."""
    return queries.get_ticket(ticket_id)


@mcp.tool
def check_stock(sku: str, size: str | None = None) -> dict:
    """Stock for a SKU in every size (or one size), with location, unit cost, and list price."""
    return queries.check_stock(sku, size)


@mcp.tool
def list_vendors() -> dict:
    """Every vendor with its specialty, delivery lead time, and open invoices (with days overdue)."""
    return queries.list_vendors()


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """A lease's landlord, rent, next due date, days until due, and rent payments already recorded."""
    return queries.get_lease(lease_id)


@mcp.tool
def get_cash_position() -> dict:
    """All cash accounts, every open invoice, upcoming rent, recorded payments, and cash left after paying them."""
    return queries.get_cash_position()


@mcp.tool
def preview_payments(payments: list[dict], account: str = "checking") -> dict:
    """Dry run a batch of payments in order WITHOUT paying anything.

    Each item is {"kind": "rent" | "invoice", "ref_id": <lease or invoice id>, "amount": <number>}.
    Checks the amount matches the bill, the bill is still unpaid, and the cash
    account never goes negative. Always returns executed=false and
    requires_human_approval=true.
    """
    return queries.preview_payments(payments, account)


@mcp.tool
def record_payment(kind: str, ref_id: int, amount: float, approved_by: str,
                   approval_code: str, account: str = "checking") -> dict:
    """HUMAN-APPROVED ONLY. Record a rent or invoice payment and deduct it from cash.

    Locked unless the server runs with CAMPUS_CUSTOMS_ALLOW_WRITES=1 and the
    human's approval code is supplied. Refuses any payment that would make
    the cash balance negative.
    """
    return writes.record_payment(kind, ref_id, amount, approved_by, approval_code, account)


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, approved_by: str, approval_code: str) -> dict:
    """HUMAN-APPROVED ONLY. Change a ticket's status (open, in_progress, waiting_on_customer, resolved).

    Locked unless the server runs with CAMPUS_CUSTOMS_ALLOW_WRITES=1 and the
    human's approval code is supplied.
    """
    return writes.update_ticket_status(ticket_id, status, approved_by, approval_code)


if __name__ == "__main__":
    mcp.run()
