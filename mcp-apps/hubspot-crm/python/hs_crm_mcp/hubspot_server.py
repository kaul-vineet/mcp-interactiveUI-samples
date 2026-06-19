"""HubSpot MCP server — bootstrap only. Tools in hubspot_tools.py, client in hubspot_client.py."""

import sys
from pathlib import Path

import structlog
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware

from .hubspot_settings import get_settings
from .hubspot_tools import TOOL_SPECS, PROMPT_SPECS
from shared_mcp.telemetry import wrap_specs

TOOL_SPECS = wrap_specs(TOOL_SPECS)

log = structlog.get_logger("hs")
settings = get_settings()

WIDGET_URI = "ui://widget/hubspot.html"
WIDGET_HTML_PATH = Path(__file__).parent.parent / "web" / "widget.html"

mcp = FastMCP(
    "ask-hubspot-crm",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.resource(WIDGET_URI, mime_type="text/html;profile=mcp-app")
async def hubspot_widget() -> str:
    """Serve the single-file React widget."""
    return WIDGET_HTML_PATH.read_text(encoding="utf-8")


# Register tools
for _spec in TOOL_SPECS:
    mcp.tool(
        name=_spec["name"],
        description=_spec["description"],
        meta={"ui": {"resourceUri": WIDGET_URI}},
    )(_spec["handler"])

# Register prompts
for _spec in PROMPT_SPECS:
    mcp.prompt(name=_spec["name"], description=_spec["description"])(_spec["handler"])


def _validate_env() -> None:
    """Check required env vars and print status banner."""
    token = settings.hubspot_access_token
    print("  +-- Environment " + "-" * 33)
    tag = "[OK] " + token[:16] + "..." if token else "[MISSING]"
    print(f"  | HUBSPOT_ACCESS_TOKEN  {tag}")
    print(f"  | PORT                  {settings.port}")
    print("  +" + "-" * 50)
    if not token:
        log.error("missing_env_vars", vars=["HUBSPOT_ACCESS_TOKEN"])
        print("\n  [ERROR] Missing required env var: HUBSPOT_ACCESS_TOKEN")
        sys.exit(1)


def main() -> None:
    """Entry point for the HubSpot MCP server."""
    _validate_env()
    log.info("starting", port=settings.port)
    print(f"\n  [*] Ask - HubSpot CRM starting on port {settings.port}")

    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "mcp-session-id"],
    )
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
