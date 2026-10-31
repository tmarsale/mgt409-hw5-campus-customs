import type { ActivityItem, Approval, Cash, Health, Job, TicketDetail, TicketStatus, TicketSummary } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; problems?: string[] };
    if (d.message) return [d.message, ...(d.problems ?? [])].join(" ");
    if (Array.isArray(detail)) return detail.map((x) => x?.msg ?? String(x)).join("; ");
  }
  return "Unexpected response from the backend.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_URL}. Is uvicorn running?`);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, describe(body?.detail));
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/api/health"),
  tickets: () => request<{ today: string; tickets: TicketSummary[] }>("/api/tickets"),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number) => post<Job>(`/api/tickets/${id}/run`),
  job: (jobId: string) => request<Job>(`/api/jobs/${jobId}`),
  activity: (ticketId: number, limit = 300) =>
    request<{ items: ActivityItem[] }>(`/api/activity?ticket_id=${ticketId}&limit=${limit}`),
  approvals: () => request<{ approvals_enabled: boolean; approvals: Approval[]; pending_total: number }>("/api/approvals"),
  approve: (id: string, approvedBy: string, code: string) =>
    post<{ approval: Approval; checking_balance: number }>(`/api/approvals/${id}/approve`, {
      approved_by: approvedBy,
      approval_code: code,
    }),
  reject: (id: string, rejectedBy: string, reason: string) =>
    post<{ approval: Approval }>(`/api/approvals/${id}/reject`, { rejected_by: rejectedBy, reason }),
  setStatus: (id: number, status: TicketStatus, approvedBy: string, code: string) =>
    post<{ old_status: TicketStatus; new_status: TicketStatus }>(`/api/tickets/${id}/status`, {
      status,
      approved_by: approvedBy,
      approval_code: code,
    }),
  cash: () => request<Cash>("/api/cash"),
  reset: () => post<{ checking_after: number; pending_approvals_voided: number }>("/api/reset", { confirm: true }),
};
