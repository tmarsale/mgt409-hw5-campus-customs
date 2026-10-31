"""MCP smoke test: call each tool over a real stdio MCP connection.

Launches the server exactly as configured in ../.mcp.json, calls the three
tools through the MCP protocol, checks each response against the working
database, and writes output/mcp_smoke.json. Run from the HW5 folder:

    .venv/Scripts/python.exe mcp_server/smoke_test.py
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "mcp_smoke.json"

TESTS = [
    {
        "ticket": 101,
        "tool": "check_order_fulfillment",
        "arguments": {"ticket_id": 101},
        "prompt": "Use the campus-customs MCP tool check_order_fulfillment to look up ticket 101, "
        "then briefly report whether the order can be filled and why.",
    },
    {
        "ticket": 102,
        "tool": "check_cash_for_rent",
        "arguments": {"ticket_id": 102},
        "prompt": "Use the campus-customs MCP tool check_cash_for_rent to look up ticket 102, "
        "then briefly report whether the store can pay the rent and how much cash would be left.",
    },
    {
        "ticket": 103,
        "tool": "evaluate_bulk_discount",
        "arguments": {"ticket_id": 103},
        "prompt": "Use the campus-customs MCP tool evaluate_bulk_discount to look up ticket 103 without a "
        "discount, then briefly report the stock situation and the largest discount before a loss.",
    },
]


def expected_from_db() -> dict:
    """Independent SQL lookups used to check the MCP responses."""
    conn = sqlite3.connect(f"{DB.as_uri()}?mode=ro", uri=True)
    q = lambda sql, *a: conn.execute(sql, a).fetchone()
    tee_s = q("SELECT qty FROM inventory WHERE sku='CC-TEE-WHITE' AND size='S'")[0]
    inv = q("SELECT amount, due_date, status FROM invoices WHERE id=501")
    lead = q("SELECT lead_days FROM vendors v JOIN invoices i ON i.vendor_id=v.id WHERE i.id=501")[0]
    rent, rent_due = q("SELECT monthly_rent, next_due FROM leases WHERE id=1")
    cash = q("SELECT SUM(balance) FROM cash_accounts")[0]
    open_total = q("SELECT SUM(amount) FROM invoices WHERE status='open'")[0]
    hood_m = q("SELECT qty FROM inventory WHERE sku='CC-HOOD-NAVY' AND size='M'")[0]
    hood_all = q("SELECT SUM(qty) FROM inventory WHERE sku='CC-HOOD-NAVY'")[0]
    cost, price = q("SELECT unit_cost, list_price FROM pricing WHERE sku='CC-HOOD-NAVY'")
    conn.close()
    return {
        "check_order_fulfillment": {
            "in_stock_qty": tee_s,
            "can_fill_now": tee_s >= 1,
            "linked_invoice.amount": inv[0],
            "linked_invoice.due_date": inv[1],
            "linked_invoice.status": inv[2],
            "linked_invoice.vendor_lead_days": lead,
        },
        "check_cash_for_rent": {
            "lease.monthly_rent": rent,
            "lease.next_due": rent_due,
            "total_cash": cash,
            "open_invoices_total": open_total,
            "cash_after_rent": cash - rent,
            "cash_after_rent_and_open_invoices": cash - rent - open_total,
        },
        "evaluate_bulk_discount": {
            "in_stock_requested_size": hood_m,
            "total_stock_all_sizes": hood_all,
            "unit_cost": cost,
            "list_price": price,
            "margin_per_unit_at_list": price - cost,
        },
    }


def lookup(data: dict, dotted: str):
    for part in dotted.split("."):
        data = data[part]
    return data


async def main() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text())
    expected = expected_from_db()
    results = []

    async with Client(config) as client:
        listed = sorted(t.name for t in await client.list_tools())
        for test in TESTS:
            response = await client.call_tool(test["tool"], test["arguments"])
            data = json.loads(response.content[0].text)
            checks = [
                {"field": f, "expected_from_db": v, "mcp_response": lookup(data, f), "match": lookup(data, f) == v}
                for f, v in expected[test["tool"]].items()
            ]
            results.append(
                {
                    "ticket": test["ticket"],
                    "prompt": test["prompt"],
                    "tool": test["tool"],
                    "arguments": test["arguments"],
                    "response": data,
                    "db_checks": checks,
                    "all_checks_match": all(c["match"] for c in checks),
                }
            )

    OUT.write_text(
        json.dumps(
            {
                "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "transport": "stdio, launched from .mcp.json (server 'campus-customs')",
                "database": "data/campus_customs_new.db (read-only)",
                "tools_listed_by_server": listed,
                "tests": results,
                "all_tests_pass": all(r["all_checks_match"] for r in results),
            },
            indent=2,
        )
    )
    for r in results:
        print(r["ticket"], r["tool"], "PASS" if r["all_checks_match"] else "FAIL")


if __name__ == "__main__":
    asyncio.run(main())
