import { useState } from "react";
import { STATUS_LABEL, StatusBadge, TYPE_LABEL, money } from "../agents";
import type { TicketDetail, TicketStatus } from "../types";

interface Props {
  detail: TicketDetail;
  running: boolean;
  otherRunning: boolean;
  canSign: boolean;
  onRun: () => void;
  onStatus: (s: TicketStatus) => Promise<void>;
}

const STATUSES: TicketStatus[] = ["open", "in_progress", "waiting_on_customer", "resolved"];

export function TicketHeader({ detail, running, otherRunning, canSign, onRun, onStatus }: Props) {
  const t = detail.ticket;
  const d = detail.last_decision;
  const [next, setNext] = useState<TicketStatus>(d?.proposed_ticket_status ?? "resolved");
  const [saving, setSaving] = useState(false);

  const facts = [
    t.sku && `${t.qty ?? ""} × ${t.sku}${t.size ? ` (${t.size})` : ""}`,
    t.invoice_id && `Invoice ${t.invoice_id}`,
    t.lease_id && `Lease ${t.lease_id}`,
  ].filter(Boolean);

  return (
    <section className="panel ticket-head" aria-labelledby="ticket-title">
      <div className="th-top">
        <div>
          <p className="eyebrow">Ticket #{t.id} · {TYPE_LABEL[t.type] ?? t.type}</p>
          <h2 id="ticket-title" className="th-title">{t.subject}</h2>
          <p className="muted">From <strong className="text">{t.requester}</strong>{facts.length > 0 && <> · {facts.join(" · ")}</>}</p>
          {t.notes && <p className="th-notes">“{t.notes}”</p>}
        </div>
        <div className="th-actions">
          <StatusBadge status={t.status} running={running} />
          <button className="btn btn-primary btn-lg" onClick={onRun} disabled={running || otherRunning}>
            {running ? <><span className="spinner" aria-hidden="true" /> Agents working…</> : d ? "Run agent team again" : "Run agent team"}
          </button>
          {otherRunning && !running && <span className="muted small">Another ticket is running.</span>}
        </div>
      </div>

      {d && !running && (
        <div className="decision">
          <div className="decision-main">
            <h3>Team decision</h3>
            <p>{d.summary}</p>
            <p className="muted">{d.recommendation}</p>
            {d.key_facts.length > 0 && (
              <details>
                <summary>Key facts ({d.key_facts.length})</summary>
                <ul>{d.key_facts.map((f, i) => <li key={i}>{f}</li>)}</ul>
              </details>
            )}
          </div>
          <dl className="decision-side">
            <div><dt>Proposed status</dt><dd>{d.proposed_ticket_status ? STATUS_LABEL[d.proposed_ticket_status] : "—"}</dd></div>
            <div><dt>Payments proposed</dt><dd>{d.payment_requests.length === 0 ? "None" :
              d.payment_requests.map((p) => `${p.kind === "rent" ? "Rent" : `Invoice ${p.ref_id}`} ${money(p.amount)}`).join(", ")}</dd></div>
            <div><dt>Customer reply</dt><dd>{d.customer_draft ? "Draft ready (not sent)" : "None"}</dd></div>
            <div><dt>Cost of run</dt><dd>{d.usage.total_tokens.toLocaleString()} tokens · {d.usage.requests} requests</dd></div>
          </dl>
        </div>
      )}

      <form className="status-form" onSubmit={async (e) => {
        e.preventDefault();
        setSaving(true);
        try { await onStatus(next); } finally { setSaving(false); }
      }}>
        <label htmlFor="status-select">Set ticket status</label>
        <select id="status-select" value={next} onChange={(e) => setNext(e.target.value as TicketStatus)}>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
        <button className="btn btn-ghost btn-sm" type="submit" disabled={!canSign || saving || next === t.status || running}>
          {saving ? "Saving…" : "Apply"}
        </button>
        {!canSign && <span className="muted small">Needs your name and approval code (right panel).</span>}
      </form>
    </section>
  );
}
