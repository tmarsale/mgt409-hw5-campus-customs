import type { AgentId, TicketStatus } from "./types";

export interface AgentLook {
  id: AgentId;
  name: string;
  role: string;
  color: string;
  icon: (props: { size?: number }) => React.JSX.Element;
}

const svg = (size: number, children: React.ReactNode) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9}
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
);

export const AGENTS: Record<AgentId, AgentLook> = {
  boss: {
    id: "boss", name: "Boss", role: "Coordinates the team", color: "var(--agent-boss)",
    icon: ({ size = 20 }) => svg(size, <><path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5L3 8z" /><path d="M5 19h14" /></>),
  },
  inventory: {
    id: "inventory", name: "Inventory", role: "Stock & restocking", color: "var(--agent-inventory)",
    icon: ({ size = 20 }) => svg(size, <><path d="M21 8l-9-5-9 5v8l9 5 9-5V8z" /><path d="M3 8l9 5 9-5M12 13v8" /></>),
  },
  accounting: {
    id: "accounting", name: "Accounting", role: "Cash & payments", color: "var(--agent-accounting)",
    icon: ({ size = 20 }) => svg(size, <><circle cx="12" cy="12" r="9" /><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .9-3 2s1.3 1.8 3 2 3 .9 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5M12 6.5V8m0 8v1.5" /></>),
  },
  facilities: {
    id: "facilities", name: "Facilities", role: "Lease & shop space", color: "var(--agent-facilities)",
    icon: ({ size = 20 }) => svg(size, <><path d="M4 21V5l8-3 8 3v16" /><path d="M9 21v-5h6v5M8 8h2M14 8h2M8 12h2M14 12h2M2 21h20" /></>),
  },
  customer_service: {
    id: "customer_service", name: "Customer Service", role: "Customer replies", color: "var(--agent-cs)",
    icon: ({ size = 20 }) => svg(size, <><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /><path d="M8.5 11h.01M12 11h.01M15.5 11h.01" /></>),
  },
};

export const AGENT_ORDER: AgentId[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

export function agentLook(id: string | null | undefined): AgentLook | null {
  return id && id in AGENTS ? AGENTS[id as AgentId] : null;
}

export function AgentAvatar({ id, size = 36, pulse = false }: { id: AgentId; size?: number; pulse?: boolean }) {
  const a = AGENTS[id];
  const Icon = a.icon;
  return (
    <span className={`avatar${pulse ? " pulse" : ""}`} style={{ "--c": a.color, width: size, height: size } as React.CSSProperties}
          title={a.name}>
      <Icon size={Math.round(size * 0.55)} />
    </span>
  );
}

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_on_customer: "Waiting on customer",
  resolved: "Resolved",
};

export function StatusBadge({ status, running = false }: { status: TicketStatus; running?: boolean }) {
  if (running) return <span className="badge badge-running"><span className="dot" />Agents working</span>;
  return <span className={`badge badge-${status}`}><span className="dot" />{STATUS_LABEL[status]}</span>;
}

export const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export const time = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
