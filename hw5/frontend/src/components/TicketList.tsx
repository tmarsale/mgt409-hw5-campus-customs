import { StatusBadge, TYPE_LABEL } from "../agents";
import type { TicketSummary } from "../types";

interface Props {
  tickets: TicketSummary[];
  selected: number | null;
  runningTicket: number | null;
  onSelect: (id: number) => void;
}

const TYPE_ICON: Record<string, string> = {
  customer_order: "M6 7h12l-1 13H7L6 7zM9 7a3 3 0 0 1 6 0",
  rent_notice: "M4 21V9l8-6 8 6v12M9 21v-6h6v6",
  price_override: "M20 12l-8 8-9-9V4h7l10 8zM7.5 7.5h.01",
};

export function TicketList({ tickets, selected, runningTicket, onSelect }: Props) {
  return (
    <nav className="panel ticket-list" aria-label="Tickets">
      <div className="panel-head">
        <h2>Tickets</h2>
        <span className="muted small">{tickets.filter((t) => t.status !== "resolved").length} open</span>
      </div>
      <ul>
        {tickets.map((t) => (
          <li key={t.id}>
            <button
              className={`ticket-card${selected === t.id ? " selected" : ""}`}
              onClick={() => onSelect(t.id)}
              aria-current={selected === t.id ? "true" : undefined}
            >
              <span className="ticket-icon" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
                     strokeLinecap="round" strokeLinejoin="round"><path d={TYPE_ICON[t.type] ?? TYPE_ICON.customer_order} /></svg>
              </span>
              <span className="ticket-main">
                <span className="ticket-top">
                  <span className="ticket-id">#{t.id}</span>
                  <StatusBadge status={t.status} running={runningTicket === t.id} />
                </span>
                <span className="ticket-subject">{t.subject}</span>
                <span className="ticket-meta">{TYPE_LABEL[t.type] ?? t.type} · {t.requester}</span>
                {t.last_run ? (
                  <span className="ticket-last">{t.last_run.summary}</span>
                ) : (
                  <span className="ticket-last muted">Agents haven't worked on this yet.</span>
                )}
                {t.pending_approvals > 0 && (
                  <span className="ticket-flag">{t.pending_approvals} payment{t.pending_approvals > 1 ? "s" : ""} awaiting approval</span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
