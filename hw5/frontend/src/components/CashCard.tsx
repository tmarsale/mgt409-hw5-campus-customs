import { useEffect, useRef, useState } from "react";
import { money } from "../agents";
import type { Cash } from "../types";

export function CashCard({ cash }: { cash: Cash | null }) {
  const prev = useRef<number | null>(null);
  const [delta, setDelta] = useState<number | null>(null);

  useEffect(() => {
    if (!cash) return;
    if (prev.current !== null && prev.current !== cash.balance) {
      setDelta(cash.balance - prev.current);
      const t = setTimeout(() => setDelta(null), 4000);
      prev.current = cash.balance;
      return () => clearTimeout(t);
    }
    prev.current = cash.balance;
  }, [cash]);

  if (!cash) return <section className="panel cash"><p className="muted">Loading cash…</p></section>;
  const after = cash.balance_after_pending_approvals;
  return (
    <section className="panel cash" aria-labelledby="cash-title">
      <div className="panel-head">
        <h2 id="cash-title">Checking balance</h2>
        <span className="muted small">as of {cash.as_of}</span>
      </div>
      <p className={`balance${delta !== null ? (delta < 0 ? " flash-down" : " flash-up") : ""}`} aria-live="polite">
        {money(cash.balance)}
        {delta !== null && <span className="delta">{delta < 0 ? "−" : "+"}{money(Math.abs(delta))}</span>}
      </p>
      {cash.pending_approvals_total > 0 ? (
        <p className={`after ${cash.pending_approvals_keep_cash_non_negative ? "" : "bad"}`}>
          After pending approvals: <strong>{money(after)}</strong>
        </p>
      ) : (
        <p className="after muted">No payments waiting for approval.</p>
      )}
      <dl className="cash-list">
        {cash.upcoming_rent.map((r) => (
          <div key={r.lease_id}>
            <dt>Rent · {r.landlord}</dt>
            <dd>{money(r.monthly_rent)} <span className="muted">due {r.next_due} ({r.days_until_due}d)</span></dd>
          </div>
        ))}
        {cash.open_invoices.map((i) => (
          <div key={i.invoice_id}>
            <dt>Invoice {i.invoice_id} · {i.vendor}</dt>
            <dd>{money(i.amount)} <span className={i.days_overdue > 0 ? "overdue" : "muted"}>
              {i.days_overdue > 0 ? `${i.days_overdue}d overdue` : `due ${i.due_date}`}</span></dd>
          </div>
        ))}
        {cash.open_invoices.length === 0 && <div><dt>Open invoices</dt><dd className="muted">None</dd></div>}
      </dl>
      {cash.payments_recorded.length > 0 && (
        <div className="paid">
          <h3>Paid</h3>
          <ul>
            {cash.payments_recorded.map((p) => (
              <li key={p.id}><span>{p.kind === "rent" ? "Rent" : `Invoice ${p.ref_id}`}</span>
                <span>{money(p.amount)}</span><span className="muted">by {p.approved_by}</span></li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
