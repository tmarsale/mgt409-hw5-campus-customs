import { useState } from "react";
import { money } from "../agents";
import type { Approval, Cash } from "../types";

interface Props {
  approvals: Approval[];
  enabled: boolean;
  cash: Cash | null;
  approver: string;
  code: string;
  onApprover: (v: string) => void;
  onCode: (v: string) => void;
  onApprove: (a: Approval) => Promise<void>;
  onReject: (a: Approval) => Promise<void>;
}

export function ApprovalsPanel({ approvals, enabled, cash, approver, code, onApprover, onCode, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const pending = approvals.filter((a) => a.status === "pending").sort((a, b) => Number(a.kind !== "rent") - Number(b.kind !== "rent"));
  const history = approvals.filter((a) => a.status !== "pending").slice(-5).reverse();
  const ready = enabled && approver.trim() !== "" && code !== "";

  let running = cash?.balance ?? 0;
  const act = async (a: Approval, fn: (a: Approval) => Promise<void>) => {
    setBusy(a.id);
    try { await fn(a); } finally { setBusy(null); }
  };

  return (
    <section className="panel approvals" aria-labelledby="appr-title">
      <div className="panel-head">
        <h2 id="appr-title">Approvals</h2>
        {pending.length > 0 && <span className="count">{pending.length}</span>}
      </div>

      {!enabled && (
        <p className="notice">Approvals are off. Add <code>CAMPUS_CUSTOMS_APPROVAL_CODE</code> to <code>HW5/.env</code> and restart the backend.</p>
      )}

      <form className="approver" onSubmit={(e) => e.preventDefault()} aria-label="Approver">
        <label>
          <span>Your name</span>
          <input value={approver} onChange={(e) => onApprover(e.target.value)} placeholder="e.g. Tejesh Marsale" autoComplete="name" />
        </label>
        <label>
          <span>Approval code</span>
          <input type="password" value={code} onChange={(e) => onCode(e.target.value)} placeholder="From HW5/.env" autoComplete="off" />
        </label>
      </form>

      {pending.length === 0 ? (
        <p className="muted empty-small">Nothing waiting. Payments the agents propose show up here.</p>
      ) : (
        <ul className="appr-list">
          {pending.map((a) => {
            running -= a.amount;
            const after = running;
            return (
              <li key={a.id} className="appr-card">
                <div className="appr-top">
                  <span className={`kind kind-${a.kind}`}>{a.kind === "rent" ? "Rent" : "Purchase · invoice"}</span>
                  <span className="appr-amount">{money(a.amount)}</span>
                </div>
                <p className="appr-title">{a.kind === "rent" ? `Lease ${a.ref_id}` : `Invoice ${a.ref_id}`}
                  <span className="muted"> · ticket {a.ticket_ids.map((t) => `#${t}`).join(", ")}</span></p>
                <p className="appr-reason">{a.reason}</p>
                <p className={`appr-after ${after < 0 ? "bad" : ""}`}>Checking after this: <strong>{money(after)}</strong>{after < 0 && " — would go negative"}</p>
                <div className="appr-actions">
                  <button className="btn btn-primary" disabled={!ready || busy !== null || after < 0} onClick={() => act(a, onApprove)}>
                    {busy === a.id ? "Paying…" : "Approve & pay"}
                  </button>
                  <button className="btn btn-ghost" disabled={!approver.trim() || busy !== null} onClick={() => act(a, onReject)}>Reject</button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {pending.length > 0 && !ready && enabled && (
        <p className="muted small">Enter your name and the approval code to approve.</p>
      )}

      {history.length > 0 && (
        <details className="history">
          <summary>Recent decisions</summary>
          <ul>
            {history.map((a) => (
              <li key={a.id}>
                <span className={`hist hist-${a.status}`}>{a.status}</span>
                <span>{a.kind === "rent" ? "Rent" : `Invoice ${a.ref_id}`} {money(a.amount)}</span>
                <span className="muted">{a.decided_by}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
