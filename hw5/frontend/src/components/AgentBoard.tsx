import { AGENT_ORDER, AGENTS, AgentAvatar, agentLook } from "../agents";
import type { AgentReport } from "../types";

interface Props {
  reports: AgentReport[];
  running: boolean;
  hasRun: boolean;
}

const STATE_LABEL = { idle: "Not involved", working: "Working…", done: "Done", failed: "Failed" } as const;

export function AgentBoard({ reports, running, hasRun }: Props) {
  const byId = new Map(reports.map((r) => [r.agent, r]));
  return (
    <section className="panel" aria-labelledby="team-title">
      <div className="panel-head">
        <h2 id="team-title">Agent team</h2>
        <span className="muted small">
          {running ? "Live: updates every second" : hasRun ? "What each agent did on the latest run" : "Run the team to see their work"}
        </span>
      </div>
      <div className="agent-grid">
        {AGENT_ORDER.map((id) => {
          const a = AGENTS[id];
          const r = byId.get(id);
          const st = r?.status ?? "idle";
          const askers = (r?.asked_by ?? []).map((x) => (x === "human" ? "you" : agentLook(x)?.name ?? x));
          return (
            <article key={id} className={`agent-card state-${st}`} style={{ "--c": a.color } as React.CSSProperties}
                     aria-label={`${a.name}: ${STATE_LABEL[st]}`}>
              <header>
                <AgentAvatar id={id} size={38} pulse={st === "working"} />
                <div>
                  <h3>{a.name}</h3>
                  <p className="muted small">{a.role}</p>
                </div>
                <span className={`agent-state s-${st}`}>{STATE_LABEL[st]}</span>
              </header>
              {r ? (
                <>
                  <p className="agent-summary" title={r.summary ?? undefined}>
                    {r.summary ?? (st === "working" ? "Looking into it…" : "")}
                  </p>
                  <footer className="agent-foot">
                    <span>Asked by {askers.length ? askers.join(", ") : "—"}</span>
                    <span>{r.tool_calls} tool call{r.tool_calls === 1 ? "" : "s"}</span>
                  </footer>
                </>
              ) : (
                <p className="agent-summary muted">
                  {running ? "Standing by…" : hasRun ? "Not needed for this ticket." : "Waiting for a run."}
                </p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
