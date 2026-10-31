"""Settings for the Campus Customs agent team: model, Portkey, and limits.

Everything that controls cost or safety lives here so it is set in one place.
"""

import os
import sys
from pathlib import Path

from pydantic_ai import ModelSettings, UsageLimits

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

HW5_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = HW5_DIR / "backend"
PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER = HW5_DIR / "mcp_server" / "server.py"
WORKING_DB = HW5_DIR / "data" / "campus_customs_new.db"
ORIGINAL_DB = HW5_DIR / "data" / "campus_customs.db"
AUDIT_TRAIL = HW5_DIR / "output" / "audit_trail.json"
APPROVALS_FILE = HW5_DIR / "output" / "approvals.json"
# Fingerprint of the untouched original database (recorded in Problem 2).
ORIGINAL_DB_SHA256 = "23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a"

try:  # a local .env is optional; the key may already be in the environment
    from dotenv import load_dotenv

    load_dotenv(HW5_DIR / ".env")
except ImportError:
    pass

# --- Model -------------------------------------------------------------------
# HW5 rule: every agent uses gpt-6-luna through Portkey. OPENAI_MODEL is read so
# the name lives in one place, but any other model is refused.
ALLOWED_MODEL = "gpt-6-luna"
MODEL_NAME = os.getenv("OPENAI_MODEL", ALLOWED_MODEL)
if MODEL_NAME != ALLOWED_MODEL:
    sys.exit(f"OPENAI_MODEL is '{MODEL_NAME}', but HW5 agents may only use '{ALLOWED_MODEL}'.")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# --- Human approval ----------------------------------------------------------
# The code a human types in the dashboard to approve a payment. Set it in HW5/.env.
# Approvals are switched off while it is missing. It is never passed to an agent.
def approval_code() -> str:
    return os.environ.get("CAMPUS_CUSTOMS_APPROVAL_CODE", "")

# --- Team --------------------------------------------------------------------
TEAM = ("boss", "inventory", "accounting", "facilities", "customer_service")

# MCP tools each agent may see. The write tools are never listed here.
AGENT_TOOLS = {
    "boss": {"get_desk_overview", "get_ticket", "get_cash_position"},
    "inventory": {"get_ticket", "check_order_fulfillment", "check_stock", "evaluate_bulk_discount", "list_vendors"},
    "accounting": {"get_ticket", "get_cash_position", "check_cash_for_rent", "preview_payments",
                   "evaluate_bulk_discount", "list_vendors"},
    "facilities": {"get_ticket", "get_lease", "check_cash_for_rent"},
    "customer_service": {"get_ticket", "check_order_fulfillment", "check_stock", "evaluate_bulk_discount"},
}
HUMAN_ONLY_TOOLS = {"record_payment", "update_ticket_status"}

# --- Limits (loops and token use) -------------------------------------------
MAX_DELEGATION_DEPTH = 2         # Boss -> specialist -> one more specialist, no deeper
MAX_DELEGATIONS_PER_TICKET = 5   # delegate() calls allowed across the whole ticket
TICKET_USAGE_LIMITS = UsageLimits(  # shared by every agent working on one ticket
    request_limit=30,
    tool_calls_limit=40,
    total_tokens_limit=150_000,
)
RUN_TOKEN_BUDGET = 400_000       # stop starting new tickets once a run has used this many
MODEL_SETTINGS = ModelSettings(max_tokens=4_000, timeout=120)
AGENT_RETRIES = 2                # output-validation retries per agent run
