"""Payments the agents proposed, waiting for a human (output/approvals.json).

An approval starts as `pending` when an agent run proposes a payment. A human
then `approve`s it (the payment is executed through MCP) or `reject`s it.
Resetting the database voids anything still pending.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = ("pending", "executed", "rejected", "failed", "voided")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ApprovalStore:
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8")).get("approvals", [])

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        doc = {"description": "Payments proposed by the agent team and what a human decided.", "approvals": items}
        tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def query(self, status: str | None = None, ticket_id: int | None = None) -> list[dict]:
        items = self._load()
        return [a for a in items
                if (status is None or a["status"] == status) and (ticket_id is None or ticket_id in a["ticket_ids"])]

    def get(self, approval_id: str) -> dict | None:
        return next((a for a in self._load() if a["id"] == approval_id), None)

    def add_from_run(self, run: dict) -> list[dict]:
        """Create a pending approval for each payment the run proposed (no duplicates)."""
        items, touched = self._load(), []
        for result in run.get("results", []):
            for p in result["decision"].get("payment_requests", []):
                same = next((a for a in items if a["status"] == "pending"
                             and (a["kind"], a["ref_id"]) == (p["kind"], p["ref_id"])), None)
                if same:  # the same bill was proposed again: keep one approval, remember both runs
                    if run["run_id"] not in same["run_ids"]:
                        same["run_ids"].append(run["run_id"])
                    if result["ticket_id"] not in same["ticket_ids"]:
                        same["ticket_ids"].append(result["ticket_id"])
                    touched.append(same)
                    continue
                item = {
                    "id": f"appr-{uuid.uuid4().hex[:8]}",
                    "status": "pending",
                    "kind": p["kind"],
                    "label": "Rent payment" if p["kind"] == "rent" else "Vendor invoice (purchase) payment",
                    "ref_id": p["ref_id"],
                    "amount": p["amount"],
                    "reason": p["reason"],
                    "proposed_at": _now(),
                    "proposed_by": "agent team",
                    "ticket_ids": [result["ticket_id"]],
                    "run_ids": [run["run_id"]],
                    "decided_at": None,
                    "decided_by": None,
                    "outcome": None,
                }
                items.append(item)
                touched.append(item)
        self._save(items)
        return touched

    def decide(self, approval_id: str, status: str, by: str, outcome: Any) -> dict:
        if status not in STATUSES:
            raise ValueError(status)
        items = self._load()
        item = next(a for a in items if a["id"] == approval_id)
        item.update(status=status, decided_at=_now(), decided_by=by, outcome=outcome)
        self._save(items)
        return item

    def void_pending(self, reason: str) -> int:
        items = self._load()
        n = 0
        for a in items:
            if a["status"] == "pending":
                a.update(status="voided", decided_at=_now(), decided_by="system", outcome={"reason": reason})
                n += 1
        self._save(items)
        return n
