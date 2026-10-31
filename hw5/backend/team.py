"""The five Campus Customs agents and how they delegate to each other.

Every agent:
  - runs on gpt-6-luna through Portkey (config.MODEL_NAME),
  - sees only its own subset of the campus-customs MCP tools (never the
    human-only write tools),
  - can hand part of a ticket to any other agent with `delegate`, within the
    depth, count, and usage limits in config.py,
  - returns an AgentReport, where payments can only be `pending_human_approval`
    and customer messages can only be `draft`.
"""

import os
import sys
from dataclasses import dataclass, replace
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, RunUsage, Tool, ToolDefinition, UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset, StdioTransport
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

import config
from audit import RunAudit

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]


# --- What every agent returns ------------------------------------------------


class PaymentRequest(BaseModel):
    kind: Literal["rent", "invoice"]
    ref_id: int = Field(description="Lease id for rent, invoice id for a vendor invoice.")
    amount: float
    reason: str
    status: Literal["pending_human_approval"] = "pending_human_approval"


class CustomerDraft(BaseModel):
    to: str
    subject: str
    body: str
    status: Literal["draft"] = "draft"


class AgentReport(BaseModel):
    ticket_id: int
    summary: str
    key_facts: list[str] = Field(description="Each fact followed by the MCP tool it came from.")
    recommendation: str
    payment_requests: list[PaymentRequest] = Field(
        default_factory=list, description="Proposed payments only; a human approves and records them.")
    customer_draft: CustomerDraft | None = Field(default=None, description="Draft reply; never sent by an agent.")
    proposed_ticket_status: Literal["open", "in_progress", "waiting_on_customer", "resolved"] | None = Field(
        default=None, description="Suggestion only; a human changes ticket status.")
    needs_human_approval: bool
    open_questions: list[str] = Field(default_factory=list)


# --- Per-ticket state shared by every agent working on it --------------------


@dataclass
class DelegationBudget:
    max_delegations: int
    used: int = 0


@dataclass
class TeamDeps:
    ticket_id: int
    chain: tuple[str, ...]  # who asked whom, e.g. ("boss", "facilities")
    budget: DelegationBudget


def delegation_refusal(deps: TeamDeps, to_agent: str) -> str | None:
    """Why a delegation is not allowed, or None if it is."""
    me = deps.chain[-1]
    if to_agent not in config.TEAM:
        return f"'{to_agent}' is not on the team {config.TEAM}."
    if to_agent == me:
        return f"{me} cannot delegate to itself."
    if to_agent in deps.chain:
        return (f"{to_agent} is already working on this request ({' -> '.join(deps.chain)}); "
                "delegating back would create a loop. Answer with what you have.")
    if len(deps.chain) - 1 >= config.MAX_DELEGATION_DEPTH:
        return f"Delegation depth limit ({config.MAX_DELEGATION_DEPTH}) reached. Answer with what you have."
    if deps.budget.used >= deps.budget.max_delegations:
        return f"Delegation limit for this ticket ({deps.budget.max_delegations}) used up. Answer with what you have."
    return None


async def _hide_delegate_when_exhausted(ctx: RunContext[TeamDeps], tool_def: ToolDefinition) -> ToolDefinition | None:
    """Don't even offer `delegate` once depth or count is used up (saves tokens)."""
    d = ctx.deps
    if len(d.chain) - 1 >= config.MAX_DELEGATION_DEPTH or d.budget.used >= d.budget.max_delegations:
        return None
    return tool_def


def load_instructions(name: str) -> str:
    rules = (config.PROMPTS_DIR / "shop_rules.md").read_text(encoding="utf-8")
    role = (config.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return f"{role}\n\n{rules}"


def usage_dict(usage: RunUsage) -> dict[str, int]:
    return {
        "requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }


# --- Model and MCP connection ------------------------------------------------


def make_model() -> Model:
    """gpt-6-luna through the Portkey gateway. The key comes from PORTKEY_API_KEY.

    Uses the Responses API: gpt-6-luna rejects function tools on /v1/chat/completions.
    """
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        sys.exit("PORTKEY_API_KEY is not set (put it in HW5/.env or the environment).")
    client = AsyncOpenAI(
        api_key=key,
        base_url=config.PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
        max_retries=2,
    )
    return OpenAIResponsesModel(config.MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def mcp_server_env() -> dict[str, str]:
    """A minimal environment for the MCP server: no API keys, and writes stay locked."""
    keep = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["CAMPUS_CUSTOMS_DB"] = str(config.WORKING_DB)
    return env


# --- The team ----------------------------------------------------------------


class CampusTeam:
    def __init__(self, audit: RunAudit, model: Model | None = None, mcp_client: Any = None):
        """`model` and `mcp_client` are only overridden by the offline tests."""
        self.audit = audit
        self.model = model or make_model()
        self.mcp = MCPToolset(
            mcp_client or StdioTransport(command=sys.executable, args=[str(config.MCP_SERVER)],
                                         env=mcp_server_env(), cwd=str(config.HW5_DIR)),
            id="campus-customs",
            process_tool_call=self._log_tool_call,
        )
        self.agents = {name: self._build(name) for name in config.TEAM}

    def _build(self, name: str) -> Agent[TeamDeps, AgentReport]:
        allowed = frozenset(config.AGENT_TOOLS[name])
        if allowed & config.HUMAN_ONLY_TOOLS:
            raise RuntimeError(f"{name} must not get human-only tools {allowed & config.HUMAN_ONLY_TOOLS}.")
        return Agent(
            self.model,
            name=name,
            deps_type=TeamDeps,
            output_type=AgentReport,
            instructions=load_instructions(name),
            toolsets=[self.mcp.filtered(lambda ctx, td, allowed=allowed: td.name in allowed)],
            tools=[Tool(self._delegate, name="delegate", prepare=_hide_delegate_when_exhausted)],
            model_settings=config.MODEL_SETTINGS,
            retries=config.AGENT_RETRIES,
        )

    async def _log_tool_call(self, ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
        agent, ticket = ctx.deps.chain[-1], ctx.deps.ticket_id
        if name in config.HUMAN_ONLY_TOOLS or name not in config.AGENT_TOOLS[agent]:
            self.audit.log("mcp_tool_refused", agent, ticket, tool=name, arguments=args)
            return {"refused": True, "reason": f"{agent} is not allowed to call {name}; a human must do this."}
        try:
            result = await call_tool(name, args)
        except Exception as e:
            self.audit.log("mcp_tool_error", agent, ticket, tool=name, arguments=args, error=str(e))
            raise
        self.audit.log("mcp_tool_call", agent, ticket, tool=name, arguments=args, result=result)
        return result

    async def _delegate(self, ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict[str, Any]:
        """Ask another Campus Customs agent to handle part of this ticket and get its report back.

        Args:
            to_agent: The teammate to ask: boss, inventory, accounting, facilities, or customer_service.
            task: One short, specific request that says what you need back.
        """
        deps = ctx.deps
        me = deps.chain[-1]
        refusal = delegation_refusal(deps, to_agent)
        if refusal:
            self.audit.log("delegation_refused", me, deps.ticket_id, to_agent=to_agent, task=task, reason=refusal)
            return {"refused": True, "reason": refusal}
        deps.budget.used += 1
        self.audit.log("delegation", me, deps.ticket_id, to_agent=to_agent, task=task,
                       depth=len(deps.chain), delegations_used=deps.budget.used)
        prompt = f"Ticket {deps.ticket_id}. Request from {me}: {task}"
        try:
            report = await self.run_agent(to_agent, prompt, replace(deps, chain=deps.chain + (to_agent,)), ctx.usage)
        except UsageLimitExceeded:
            raise  # a hard cap stops the whole ticket
        except Exception as e:
            return {"error": f"{to_agent} could not finish: {type(e).__name__}: {e}"}
        return report.model_dump()

    async def run_agent(self, name: str, prompt: str, deps: TeamDeps, usage: RunUsage) -> AgentReport:
        self.audit.log("agent_started", name, deps.ticket_id, prompt=prompt, chain=list(deps.chain))
        try:
            result = await self.agents[name].run(
                prompt, deps=deps, usage=usage, usage_limits=config.TICKET_USAGE_LIMITS)
        except Exception as e:
            self.audit.log("agent_failed", name, deps.ticket_id, error=f"{type(e).__name__}: {e}")
            raise
        self.audit.log("agent_finished", name, deps.ticket_id, report=result.output.model_dump(),
                       ticket_usage_so_far=usage_dict(usage))
        return result.output

    async def handle_ticket(self, ticket_id: int) -> tuple[AgentReport, RunUsage, int]:
        """The Boss takes the ticket; specialists are pulled in through delegate()."""
        deps = TeamDeps(ticket_id, ("boss",), DelegationBudget(config.MAX_DELEGATIONS_PER_TICKET))
        usage = RunUsage()
        prompt = (f"Handle ticket {ticket_id}. Check it with your tools, delegate to the right specialists, "
                  "and return the team's final recommendation for the human owner. This is a test run: "
                  "propose payments and status changes, but nothing will be executed.")
        report = await self.run_agent("boss", prompt, deps, usage)
        return report, usage, deps.budget.used
