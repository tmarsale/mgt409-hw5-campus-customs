import type { Health } from "../types";

interface Props {
  health: Health | null;
  offline: boolean;
  onReset: () => void;
  resetDisabled: boolean;
}

export function TopBar({ health, offline, onReset, resetDisabled }: Props) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="logo" aria-hidden="true">CC</span>
        <div>
          <h1>Campus Customs <span className="brand-accent">Agent Desk</span></h1>
          <p className="tagline">Five AI agents work the ticket desk. You approve the money.</p>
        </div>
      </div>
      <div className="topbar-meta">
        {offline ? (
          <span className="chip chip-bad" role="status">Backend offline</span>
        ) : health ? (
          <>
            <span className="chip">Store date <strong>{health.store_date}</strong></span>
            <span className="chip">Model <strong>{health.model}</strong> · {health.gateway}</span>
            <span className={`chip ${health.original_db_unchanged ? "chip-ok" : "chip-bad"}`}>
              Original DB {health.original_db_unchanged ? "untouched" : "CHANGED"}
            </span>
          </>
        ) : (
          <span className="chip">Connecting…</span>
        )}
        <button className="btn btn-ghost btn-sm" onClick={onReset} disabled={resetDisabled}
                title="Copy the original database over the working copy">
          Reset data
        </button>
      </div>
    </header>
  );
}
