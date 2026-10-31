import { useEffect, useMemo, useRef, useState } from "react";
import { AgentAvatar, agentLook, money, time } from "../agents";
import type { ActivityItem, AgentId } from "../types";

interface Props {
  items: ActivityItem[];          // newest first, from the API
  latestRunId: string | null;
  running: boolean;
}

function args(a: Record<string, unknown> | undefined) {
  if (!a) return "";
  return Object.entries(a)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(", ");
}

function Name({ id }: { id: string | null | undefined }) {
  const a = agentLook(id);
  if (!a) return <strong>{id === "human" ? "You" : id ?? "System"}</strong>;
  return <strong style={{ color: a.color }}>{a.name}</strong>;
}

function Row({ item, askedBy }: { item: ActivityItem; askedBy: Record<string, string> }) {
  const d = item.detail;
  const who = item.agent as AgentId | null;
  if (item.kind === "message") {
    // A customer draft carries its decision's event name, so handle it before the switch.
    return (
      <li className="feed-draft">
        <div className="bubble-head"><AgentAvatar id="customer_service" size={24} /> <strong>Customer reply</strong>
          <span className="draft-tag">Draft · not sent</span><time>{time(item.at)}</time></div>
        <div className="email">
          <div><span className="muted">To</span> {d.to}</div>
          <div><span className="muted">Subject</span> {d.subject}</div>
          <p>{d.body}</p>
        </div>
      </li>
    );
  }
  switch (item.event) {
    case "delegation":
      return (
        <li className="feed-msg" style={{ "--c": agentLook(who)?.color } as React.CSSProperties}>
          <div className="msg-avatars"><AgentAvatar id={who!} size={30} /><span className="msg-arrow">→</span><AgentAvatar id={d.to_agent} size={30} /></div>
          <div className="bubble">
            <div className="bubble-head"><Name id={who} /> asked <Name id={d.to_agent} /><time>{time(item.at)}</time></div>
            <p>{d.task}</p>
          </div>
        </li>
      );
    case "delegation_refused":
      return (
        <li className="feed-line warn">
          <span className="line-icon">⚠</span>
          <span><Name id={who} /> couldn't ask <Name id={d.to_agent} />: {d.reason}</span>
          <time>{time(item.at)}</time>
        </li>
      );
    case "agent_started":
      if ((d.chain ?? []).length > 1) return null; // shown as the delegation message instead
      return (
        <li className="feed-line">
          <AgentAvatar id={who!} size={22} />
          <span><Name id={who} /> picked up the ticket</span>
          <time>{time(item.at)}</time>
        </li>
      );
    case "agent_finished": {
      const r = d.report;
      const to = askedBy[`${item.run_id}:${who}`];
      return (
        <li className="feed-msg reply" style={{ "--c": agentLook(who)?.color } as React.CSSProperties}>
          <div className="msg-avatars"><AgentAvatar id={who!} size={30} /></div>
          <div className="bubble">
            <div className="bubble-head">
              <Name id={who} /> {to && to !== "human" ? <>replied to <Name id={to} /></> : "reported"}
              <time>{time(item.at)}</time>
            </div>
            <p>{r.summary}</p>
            {r.key_facts?.length > 0 && (
              <details>
                <summary>{r.key_facts.length} key fact{r.key_facts.length > 1 ? "s" : ""}</summary>
                <ul>{r.key_facts.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
              </details>
            )}
          </div>
        </li>
      );
    }
    case "agent_failed":
      return <li className="feed-line bad"><span className="line-icon">✕</span><span><Name id={who} /> failed: {d.error}</span><time>{time(item.at)}</time></li>;
    case "mcp_tool_call":
    case "mcp_tool_error":
    case "mcp_tool_refused":
      return (
        <li className={`feed-tool${item.event !== "mcp_tool_call" ? " bad" : ""}`}>
          <span className="tool-dot" style={{ background: agentLook(who)?.color }} aria-hidden="true" />
          <span className="tool-who">{agentLook(who)?.name}</span>
          <code>{d.tool}({args(d.arguments)})</code>
          {item.event !== "mcp_tool_call" && <span className="tool-err">{d.error ?? d.reason}</span>}
          <time>{time(item.at)}</time>
        </li>
      );
    case "ticket_decision":
      return (
        <li className="feed-decision">
          <div className="bubble-head"><AgentAvatar id="boss" size={24} /> <strong>Team decision</strong><time>{time(item.at)}</time></div>
          <p>{d.decision.summary}</p>
          <p className="muted">{d.decision.recommendation}</p>
        </li>
      );
    case "guardrail_payment_preview":
      if (!d.preview) return null;
      return (
        <li className="feed-line ok">
          <span className="line-icon">✓</span>
          <span>Guardrail: proposed payments keep checking at {money(d.preview.ending_balance)}{d.preview.all_valid ? "" : " (INVALID)"}. Nothing paid yet.</span>
          <time>{time(item.at)}</time>
        </li>
      );
    case "run_started":
      return <li className="feed-divider"><span>Run started · {time(item.at)}</span></li>;
    case "run_finished":
      return <li className="feed-divider"><span>Run finished · databases {d.databases_unchanged ? "unchanged by agents" : "changed"}</span></li>;
    default:
      if (item.kind === "human") {
        return (
          <li className="feed-line human">
            <span className="line-icon">●</span><span>{item.summary}</span><time>{time(item.at)}</time>
          </li>
        );
      }
      return null;
  }
}

export function ActivityFeed({ items, latestRunId, running }: Props) {
  const [scope, setScope] = useState<"latest" | "all">("latest");
  const listRef = useRef<HTMLOListElement>(null);

  const shown = useMemo(() => {
    const chrono = [...items].reverse(); // the API lists a decision's draft just before it, so it lands right after
    return scope === "all" || !latestRunId ? chrono : chrono.filter((i) => i.run_id === latestRunId);
  }, [items, scope, latestRunId]);

  const askedBy = useMemo(() => {
    const m: Record<string, string> = {};
    for (const i of shown) {
      if (i.event === "agent_started" && i.agent) {
        const chain: string[] = i.detail.chain ?? [];
        m[`${i.run_id}:${i.agent}`] = chain.length > 1 ? chain[chain.length - 2] : "human";
      }
    }
    return m;
  }, [shown]);

  useEffect(() => {
    if (running && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [shown.length, running]);

  const tools = shown.filter((i) => i.kind === "tool").length;
  const delegations = shown.filter((i) => i.event === "delegation").length;

  return (
    <section className="panel feed-panel" aria-labelledby="feed-title">
      <div className="panel-head">
        <h2 id="feed-title">Activity &amp; conversations</h2>
        <div className="seg" role="group" aria-label="Which runs to show">
          <button className={scope === "latest" ? "on" : ""} onClick={() => setScope("latest")} aria-pressed={scope === "latest"}>Latest run</button>
          <button className={scope === "all" ? "on" : ""} onClick={() => setScope("all")} aria-pressed={scope === "all"}>All history</button>
        </div>
      </div>
      {shown.length > 0 && (
        <p className="muted small feed-stats">{delegations} hand-offs · {tools} MCP tool calls{running ? " · live" : ""}</p>
      )}
      {shown.length === 0 ? (
        <div className="empty">
          <p><strong>No activity yet.</strong></p>
          <p className="muted">Press <em>Run agent team</em> to watch the Boss hand the ticket to the right specialists.</p>
        </div>
      ) : (
        <ol className="feed" ref={listRef} aria-live={running ? "polite" : "off"}>
          {shown.map((i) => <Row key={`${i.run_id}-${i.seq}-${i.kind}`} item={i} askedBy={askedBy} />)}
          {running && <li className="feed-line typing"><span className="typing-dots"><i /><i /><i /></span> Agents are working…</li>}
        </ol>
      )}
    </section>
  );
}
