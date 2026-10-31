import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "./api";
import { money } from "./agents";
import { ActivityFeed } from "./components/ActivityFeed";
import { AgentBoard } from "./components/AgentBoard";
import { ApprovalsPanel } from "./components/ApprovalsPanel";
import { CashCard } from "./components/CashCard";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { TicketHeader } from "./components/TicketHeader";
import { TicketList } from "./components/TicketList";
import { TopBar } from "./components/TopBar";
import type { ActivityItem, Approval, Cash, Health, Job, TicketDetail, TicketStatus, TicketSummary } from "./types";

interface Toast { id: number; tone: "ok" | "bad" | "info"; text: string }

function usePoll(fn: () => void, ms: number) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    const id = setInterval(() => saved.current(), ms);
    return () => clearInterval(id);
  }, [ms]);
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [approvalsOn, setApprovalsOn] = useState(true);
  const [job, setJob] = useState<Job | null>(null);
  const [approver, setApprover] = useState(() => localStorage.getItem("cc-approver") ?? "");
  const [code, setCode] = useState(""); // kept in memory only, never stored
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirmReset, setConfirmReset] = useState(false);

  const running = job?.status === "running";

  const toast = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, tone, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 0) setOffline(true);
    toast("bad", e instanceof Error ? e.message : String(e));
  }, [toast]);

  const loadShared = useCallback(async () => {
    try {
      const [h, t, c, a] = await Promise.all([api.health(), api.tickets(), api.cash(), api.approvals()]);
      setHealth(h); setTickets(t.tickets); setCash(c); setApprovals(a.approvals); setApprovalsOn(a.approvals_enabled);
      setOffline(false);
      setSelected((s) => s ?? t.tickets[0]?.id ?? null);
      if (h.agent_run_in_progress) {
        setJob((j) => j ?? { job_id: h.agent_run_in_progress!, ticket_id: -1, status: "running", started_at: "", finished_at: null, run_id: null });
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) setOffline(true);
    }
  }, []);

  const selectedRef = useRef<number | null>(null);
  selectedRef.current = selected;

  const loadTicket = useCallback(async (id: number) => {
    try {
      const [d, a] = await Promise.all([api.ticket(id), api.activity(id)]);
      if (id !== selectedRef.current) return; // the user picked another ticket meanwhile
      setDetail(d);
      setActivity(a.items);
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) setOffline(true);
    }
  }, []);

  useEffect(() => { loadShared(); }, [loadShared]);
  useEffect(() => {
    if (selected !== null) { setDetail(null); setActivity([]); loadTicket(selected); }
  }, [selected, loadTicket]);

  // Fast polling while agents work, slow otherwise.
  usePoll(async () => {
    if (!running || !job) return;
    try {
      const j = await api.job(job.job_id);
      if (j.ticket_id !== job.ticket_id || j.run_id !== job.run_id) setJob(j);
      if (selected !== null) await loadTicket(selected);
      if (j.status !== "running") {
        setJob(j);
        await loadShared();
        if (j.status === "finished") {
          const n = j.approvals?.length ?? 0;
          toast("ok", `Ticket #${j.ticket_id}: the team finished${n ? ` and proposed ${n} payment${n > 1 ? "s" : ""} for your approval` : ""}.`);
        } else toast("bad", `Ticket #${j.ticket_id}: run ${j.status}. ${j.error ?? ""}`);
      }
    } catch (e) { fail(e); }
  }, 1200);
  usePoll(() => { if (!running) { loadShared(); if (selected !== null) loadTicket(selected); } }, 8000);

  const runTeam = async () => {
    if (selected === null) return;
    try {
      const j = await api.run(selected);
      setJob(j);
      toast("info", `Ticket #${selected}: the Boss is on it.`);
      loadTicket(selected);
    } catch (e) { fail(e); }
  };

  const refreshAfterAction = async () => {
    await loadShared();
    if (selected !== null) await loadTicket(selected);
  };

  const approve = async (a: Approval) => {
    try {
      const r = await api.approve(a.id, approver.trim(), code);
      toast("ok", `Paid ${money(a.amount)} (${a.kind === "rent" ? "rent" : `invoice ${a.ref_id}`}). Checking is now ${money(r.checking_balance)}.`);
    } catch (e) { fail(e); }
    await refreshAfterAction();
  };

  const reject = async (a: Approval) => {
    try {
      await api.reject(a.id, approver.trim(), "Rejected from the dashboard");
      toast("info", `Rejected ${a.kind === "rent" ? "rent" : `invoice ${a.ref_id}`} (${money(a.amount)}). Nothing was paid.`);
    } catch (e) { fail(e); }
    await refreshAfterAction();
  };

  const setStatus = async (s: TicketStatus) => {
    if (selected === null) return;
    try {
      const r = await api.setStatus(selected, s, approver.trim(), code);
      toast("ok", `Ticket #${selected} moved from ${r.old_status.replace(/_/g, " ")} to ${r.new_status.replace(/_/g, " ")}.`);
    } catch (e) { fail(e); }
    await refreshAfterAction();
  };

  const doReset = async () => {
    setConfirmReset(false);
    try {
      const r = await api.reset();
      toast("ok", `Data reset. Checking is ${money(r.checking_after)}; ${r.pending_approvals_voided} pending approval(s) voided.`);
    } catch (e) { fail(e); }
    await refreshAfterAction();
  };

  const onApprover = (v: string) => { setApprover(v); localStorage.setItem("cc-approver", v); };
  const runningTicket = running ? job!.ticket_id : null;
  const thisRunning = running && runningTicket === selected;
  // While this ticket runs, show only the new run (never the previous run's results).
  const liveReports = detail?.agent_reports.in_progress ? detail.agent_reports.agents : [];
  const reports = thisRunning ? liveReports : detail?.agent_reports.agents ?? [];
  const feedRunId = thisRunning ? job?.run_id ?? "pending" : detail?.agent_reports.run_id ?? null;

  return (
    <div className="app">
      <a className="skip" href="#workspace">Skip to ticket</a>
      <TopBar health={health} offline={offline} onReset={() => setConfirmReset(true)} resetDisabled={running || offline} />

      {offline && (
        <div className="banner" role="alert">
          Can't reach the backend. Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <div className="layout">
        <TicketList tickets={tickets} selected={selected} runningTicket={runningTicket} onSelect={setSelected} />

        <main id="workspace" className="workspace">
          {detail ? (
            <>
              <TicketHeader key={detail.ticket.id} detail={detail} running={thisRunning}
                            otherRunning={running && !thisRunning} canSign={approver.trim() !== "" && code !== ""}
                            onRun={runTeam} onStatus={setStatus} />
              <ErrorBoundary label="agent team">
                <AgentBoard reports={reports} running={thisRunning}
                            hasRun={detail.agent_reports.run_id !== null && !thisRunning} />
              </ErrorBoundary>
              <ErrorBoundary label="activity">
                <ActivityFeed items={activity} latestRunId={feedRunId} running={thisRunning} />
              </ErrorBoundary>
            </>
          ) : (
            <section className="panel"><div className="skeleton" /><div className="skeleton short" /></section>
          )}
        </main>

        <aside className="side">
          <CashCard cash={cash} />
          <ApprovalsPanel approvals={approvals} enabled={approvalsOn} cash={cash} approver={approver} code={code}
                          onApprover={onApprover} onCode={setCode} onApprove={approve} onReject={reject} />
        </aside>
      </div>

      <ConfirmDialog
        open={confirmReset}
        title="Reset the shop data?"
        body={<p>This copies the original database over the working copy: payments are erased, checking goes back to $3,400, every ticket reopens, and pending approvals are voided. The original database is not changed, and the audit trail keeps everything.</p>}
        confirmLabel="Reset data"
        onConfirm={doReset}
        onCancel={() => setConfirmReset(false)}
      />

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast toast-${t.tone}`}>{t.text}</div>)}
      </div>
    </div>
  );
}
