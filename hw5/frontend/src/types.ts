export type AgentId = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";
export type TicketStatus = "open" | "in_progress" | "waiting_on_customer" | "resolved";
export type ApprovalStatus = "pending" | "executed" | "rejected" | "failed" | "voided";
export type ActivityKind = "agent" | "delegation" | "tool" | "decision" | "message" | "human" | "system";

export interface Health {
  status: string;
  model: string;
  gateway: string;
  store_date: string;
  original_db_unchanged: boolean;
  approvals_enabled: boolean;
  agent_run_in_progress: string | null;
}

export interface TicketSummary {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: TicketStatus;
  created_at: string;
  pending_approvals: number;
  last_run: {
    run_id: string;
    at: string;
    summary: string;
    recommendation: string;
    proposed_ticket_status: TicketStatus | null;
  } | null;
}

export interface PaymentRequest {
  kind: "rent" | "invoice";
  ref_id: number;
  amount: number;
  reason: string;
  status: "pending_human_approval";
}

export interface CustomerDraft {
  to: string;
  subject: string;
  body: string;
  status: "draft";
}

export interface Decision {
  run_id: string;
  at: string;
  ticket_id: number;
  summary: string;
  key_facts: string[];
  recommendation: string;
  payment_requests: PaymentRequest[];
  customer_draft: CustomerDraft | null;
  proposed_ticket_status: TicketStatus | null;
  needs_human_approval: boolean;
  open_questions: string[];
  usage: { requests: number; tool_calls: number; total_tokens: number };
}

export interface AgentReport {
  agent: AgentId;
  status: "idle" | "working" | "done" | "failed";
  asked_by: string[];
  tasks: number;
  tool_calls: number;
  summary: string | null;
  recommendation: string | null;
  key_facts: string[];
  last_at: string;
}

export interface TicketDetail {
  today: string;
  ticket: {
    id: number;
    type: string;
    requester: string;
    subject: string;
    sku: string | null;
    size: string | null;
    qty: number | null;
    lease_id: number | null;
    invoice_id: number | null;
    status: TicketStatus;
    notes: string | null;
    created_at: string;
  };
  linked_lease: Record<string, unknown> | null;
  linked_invoice: Record<string, unknown> | null;
  last_decision: Decision | null;
  agent_reports: { run_id: string | null; in_progress: boolean; agents: AgentReport[] };
  approvals: Approval[];
}

export interface ActivityItem {
  run_id: string;
  seq: number;
  at: string;
  event: string;
  kind: ActivityKind;
  agent: AgentId | null;
  ticket_id: number | null;
  summary: string;
  detail: Record<string, any>;
}

export interface Approval {
  id: string;
  status: ApprovalStatus;
  kind: "rent" | "invoice";
  label: string;
  ref_id: number;
  amount: number;
  reason: string;
  proposed_at: string;
  ticket_ids: number[];
  run_ids: string[];
  decided_at: string | null;
  decided_by: string | null;
  outcome: Record<string, any> | null;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
  total_cash: number;
  open_invoices: { invoice_id: number; vendor: string; amount: number; due_date: string; days_overdue: number; description: string }[];
  open_invoices_total: number;
  upcoming_rent: { lease_id: number; landlord: string; monthly_rent: number; next_due: string; days_until_due: number }[];
  payments_recorded: { id: number; kind: string; ref_id: number; amount: number; paid_at: string; approved_by: string }[];
  pending_approvals_total: number;
  balance_after_pending_approvals: number;
  pending_approvals_keep_cash_non_negative: boolean;
}

export interface Job {
  job_id: string;
  ticket_id: number;
  status: "running" | "finished" | "failed" | "partial";
  started_at: string;
  finished_at: string | null;
  run_id: string | null;
  error?: string;
  approvals?: string[];
  events_so_far?: number | null;
}
