"""HubSpot CRM tool handlers — Companies entity (SF pattern)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from cachetools import TTLCache
from mcp import types
from mcp.types import TextContent

from .hubspot_client import HubSpotAPIError, HubSpotAuthError, get_client

log = structlog.get_logger("hs")
WIDGET_URI = "ui://widget/hubspot.html"


# ── Entity Schemas ────────────────────────────────────────────────────────────

_ENTITY_SCHEMAS: dict[str, dict] = {
    "Company": {
        "columns": [
            {"apiName": "name", "label": "Name"},
            {"apiName": "type", "label": "Type"},
            {"apiName": "lifecyclestage", "label": "Stage"},
            {"apiName": "city", "label": "City"},
        ],
        "hiddenColumns": [
            {"apiName": "domain", "label": "Domain"},
            {"apiName": "phone", "label": "Phone"},
            {"apiName": "country", "label": "Country"},
            {"apiName": "description", "label": "Description"},
        ],
        "filterFields": {
            "name": {"operator": "CONTAINS_TOKEN", "property": "name"},
            "type": {"operator": "EQ", "property": "type"},
            "lifecyclestage": {"operator": "EQ", "property": "lifecyclestage"},
            "city": {"operator": "CONTAINS_TOKEN", "property": "city"},
            "country": {"operator": "CONTAINS_TOKEN", "property": "country"},
        },
        "formFields": [
            {"name": "name", "label": "Company Name", "required": True},
            {"name": "domain", "label": "Domain"},
            {"name": "type", "label": "Type", "picklist": ["PROSPECT", "PARTNER", "RESELLER", "VENDOR", "OTHER"]},
            {"name": "lifecyclestage", "label": "Lifecycle Stage", "picklist": ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer", "evangelist", "other"]},
            {"name": "city", "label": "City"},
            {"name": "phone", "label": "Phone"},
            {"name": "country", "label": "Country"},
            {"name": "description", "label": "Description", "multiline": True},
        ],
    },
}


def _get_schema(entity: str) -> dict:
    return _ENTITY_SCHEMAS[entity]


# ── Cache ─────────────────────────────────────────────────────────────────────

_caches: dict[str, TTLCache] = {}


def _get_cache(entity: str) -> TTLCache:
    if entity not in _caches:
        _caches[entity] = TTLCache(maxsize=10, ttl=90)
    return _caches[entity]


def _cache_get(key: str, entity: str) -> tuple[list | None, str | None]:
    cache = _get_cache(entity)
    entry = cache.get(key)
    if entry is not None:
        return entry["items"], entry["cached_at"]
    return None, None


def _cache_set(key: str, entity: str, items: list) -> str:
    cache = _get_cache(entity)
    cached_at = _now_iso()
    cache[key] = {"items": items, "cached_at": cached_at}
    return cached_at


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _error_result(msg: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[TextContent(type="text", text=msg)],
        structuredContent={"type": "error", "message": msg},
    )


def _list_summary(entity_label: str, items: list, cache_hit: bool = False) -> str:
    count = len(items)
    suffix = " (cached)" if cache_hit else ""
    return f"{count} {entity_label}{suffix}."


def _get_list_props(entity: str) -> list[str]:
    """Get property names needed for list view."""
    cfg = _get_schema(entity)
    return [c["apiName"] for c in cfg["columns"]]


def _get_all_props(entity: str) -> list[str]:
    """Get all property names (list + hidden)."""
    cfg = _get_schema(entity)
    return [c["apiName"] for c in cfg["columns"] + cfg["hiddenColumns"]]


def _build_filter_groups(entity: str, params: dict[str, str]) -> list[dict] | None:
    """Build HubSpot Search API filterGroups from provided params."""
    cfg = _get_schema(entity)
    filter_defs = cfg.get("filterFields", {})
    filters = []
    for param_name, value in params.items():
        if not value:
            continue
        fdef = filter_defs.get(param_name)
        if not fdef:
            continue
        filters.append({
            "propertyName": fdef["property"],
            "operator": fdef["operator"],
            "value": value,
        })
    if not filters:
        return None
    return [{"filters": filters}]


def _filter_signature(params: dict[str, str]) -> str:
    """Create a cache key from non-empty filter params."""
    parts = sorted(f"{k}={v}" for k, v in params.items() if v)
    return "|".join(parts)


# ── Companies tools ───────────────────────────────────────────────────────────

async def hs__get_companies(
    company_id: str = "",
    name: str = "",
    type: str = "",
    lifecyclestage: str = "",
    city: str = "",
    country: str = "",
    action: str = "",
    refresh: bool = False,
) -> types.CallToolResult:
    """Get companies. Branches: id+edit→form, id→list-of-one, filters→filtered, bare→top 5."""
    log.info("hs__get_companies", company_id=company_id, action=action,
             name=name, type=type, lifecyclestage=lifecyclestage,
             city=city, country=country, refresh=refresh)

    cfg = _get_schema("Company")

    # Branch 1 — id + action="edit"/"change" → prefilled edit form
    if company_id and action in ("edit", "change"):
        try:
            client = get_client()
            record = await client.get_object("companies", company_id, _get_all_props("Company"))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Company {company_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error looking up company: {exc}")

        prefill = {field["name"]: record.get(field["name"], "") or "" for field in cfg["formFields"]}
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Opening edit form for company: {record.get('name', company_id)}.")],
            structuredContent={
                "type": "form", "entity": "company", "mode": "edit",
                "recordId": record.get("id", company_id), "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 2 — id alone → list-of-one
    if company_id:
        try:
            client = get_client()
            record = await client.get_object("companies", company_id, _get_list_props("Company"))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Company {company_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching company: {exc}")

        items = [record]
        return types.CallToolResult(
            content=[TextContent(type="text", text=_list_summary("company(ies)", items))],
            structuredContent={
                "type": "companies", "total": len(items), "items": items,
                "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()},
            },
        )

    # Branch 3 — filter-based or bare list
    filter_params = {
        "name": name, "type": type,
        "lifecyclestage": lifecyclestage, "city": city, "country": country,
    }
    filter_groups = _build_filter_groups("Company", filter_params)
    has_filters = filter_groups is not None

    # Cache lookup
    filter_sig = _filter_signature(filter_params)
    cache_key = f"companies:{filter_sig}" if filter_sig else "companies"
    if not refresh:
        cached_items, cached_at = _cache_get(cache_key, "Company")
        if cached_items is not None:
            return types.CallToolResult(
                content=[TextContent(type="text", text=_list_summary("company(ies)", cached_items, cache_hit=True))],
                structuredContent={
                    "type": "companies", "total": len(cached_items), "items": cached_items,
                    "_schema": cfg, "_cache": {"hit": True, "cached_at": cached_at},
                },
            )

    try:
        client = get_client()
        props = _get_list_props("Company")
        items = await client.search_objects("companies", props, filter_groups=filter_groups, limit=10)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch companies: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching companies: {exc}")

    cached_at = _cache_set(cache_key, "Company", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=_list_summary("company(ies)", items))],
        structuredContent={
            "type": "companies", "total": len(items), "items": items,
            "_schema": cfg, "_cache": {"hit": False, "cached_at": cached_at},
        },
    )


async def hs__create_company(
    name: str,
    domain: str = "",
    type: str = "",
    lifecyclestage: str = "",
    city: str = "",
    phone: str = "",
    country: str = "",
    description: str = "",
) -> types.CallToolResult:
    """Create a new Company in HubSpot CRM. Requires name. Returns updated list."""
    log.info("hs__create_company", name=name, domain=domain, type=type,
             lifecyclestage=lifecyclestage, city=city)

    props: dict[str, Any] = {"name": name}
    if domain:
        props["domain"] = domain
    if type:
        props["type"] = type
    if lifecyclestage:
        props["lifecyclestage"] = lifecyclestage
    if city:
        props["city"] = city
    if phone:
        props["phone"] = phone
    if country:
        props["country"] = country
    if description:
        props["description"] = description

    try:
        client = get_client()
        new_id = await client.create_object("companies", props)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to create company: {exc}")
    except Exception as exc:
        return _error_result(f"Unexpected error creating company: {exc}")

    # Refresh list
    try:
        items = await client.search_objects("companies", _get_list_props("Company"), limit=10)
    except Exception:
        items = []

    cfg = _get_schema("Company")
    _cache_set("companies", "Company", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Company '{name}' created (Id: {new_id}).")],
        structuredContent={
            "type": "companies", "total": len(items), "items": items,
            "_schema": cfg, "_createdId": new_id,
            "_cache": {"hit": False, "cached_at": _now_iso()},
        },
    )


async def hs__update_company(
    company_id: str,
    name: str = "",
    domain: str = "",
    type: str = "",
    lifecyclestage: str = "",
    city: str = "",
    phone: str = "",
    country: str = "",
    description: str = "",
) -> types.CallToolResult:
    """Update an existing Company by id. Only provided fields are updated."""
    log.info("hs__update_company", company_id=company_id, name=name, domain=domain)

    props: dict[str, Any] = {}
    if name:
        props["name"] = name
    if domain:
        props["domain"] = domain
    if type:
        props["type"] = type
    if lifecyclestage:
        props["lifecyclestage"] = lifecyclestage
    if city:
        props["city"] = city
    if phone:
        props["phone"] = phone
    if country:
        props["country"] = country
    if description:
        props["description"] = description

    if not props:
        return _error_result("No fields provided to update.")

    try:
        client = get_client()
        await client.update_object("companies", company_id, props)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to update company: {exc}")
    except Exception as exc:
        return _error_result(f"Unexpected error updating company: {exc}")

    # Refresh list
    try:
        items = await client.search_objects("companies", _get_list_props("Company"), limit=10)
    except Exception:
        items = []

    cfg = _get_schema("Company")
    _cache_set("companies", "Company", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Company {company_id} updated.")],
        structuredContent={
            "type": "companies", "total": len(items), "items": items,
            "_schema": cfg, "_updatedId": company_id,
            "_cache": {"hit": False, "cached_at": _now_iso()},
        },
    )


async def hs__get_company_contacts(
    company_id: str,
    refresh: bool = False,
) -> types.CallToolResult:
    """Get contacts associated to a company via Associations + Batch Read."""
    log.info("hs__get_company_contacts", company_id=company_id, refresh=refresh)
    if not company_id:
        return _error_result("company_id is required.")

    try:
        client = get_client()
        contact_ids = await client.get_associated_ids("companies", company_id, "contacts")
        records = await client.batch_read(
            "contacts",
            contact_ids,
            ["firstname", "lastname", "email", "phone", "lifecyclestage"],
        )
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch company contacts: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching company contacts: {exc}")

    items = [
        {
            "id": record.get("id", ""),
            "firstname": record.get("firstname", "") or "",
            "lastname": record.get("lastname", "") or "",
            "email": record.get("email", "") or "",
            "phone": record.get("phone", "") or "",
            "lifecyclestage": record.get("lifecyclestage", "") or "",
        }
        for record in records
    ]
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Showing {len(items)} contact(s).")],
        structuredContent={
            "type": "company_contacts",
            "company_id": company_id,
            "items": items,
            "total": len(items),
        },
    )


async def hs__get_company_deals(
    company_id: str,
    refresh: bool = False,
) -> types.CallToolResult:
    """Get deals associated to a company via Associations + Batch Read."""
    log.info("hs__get_company_deals", company_id=company_id, refresh=refresh)
    if not company_id:
        return _error_result("company_id is required.")

    try:
        client = get_client()
        deal_ids = await client.get_associated_ids("companies", company_id, "deals")
        records = await client.batch_read(
            "deals",
            deal_ids,
            ["dealname", "amount", "dealstage", "closedate", "pipeline"],
        )
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch company deals: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching company deals: {exc}")

    items = [
        {
            "id": record.get("id", ""),
            "dealname": record.get("dealname", "") or "",
            "amount": record.get("amount", "") or "",
            "dealstage": record.get("dealstage", "") or "",
            "closedate": record.get("closedate", "") or "",
            "pipeline": record.get("pipeline", "") or "",
        }
        for record in records
    ]
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Showing {len(items)} deal(s).")],
        structuredContent={
            "type": "company_deals",
            "company_id": company_id,
            "items": items,
            "total": len(items),
        },
    )


async def hs__get_company_tickets(
    company_id: str,
    refresh: bool = False,
) -> types.CallToolResult:
    """Get tickets associated to a company via Associations + Batch Read."""
    log.info("hs__get_company_tickets", company_id=company_id, refresh=refresh)
    if not company_id:
        return _error_result("company_id is required.")

    try:
        client = get_client()
        ticket_ids = await client.get_associated_ids("companies", company_id, "tickets")
        records = await client.batch_read(
            "tickets",
            ticket_ids,
            ["subject", "hs_pipeline_stage", "hs_ticket_priority", "hs_ticket_category"],
        )
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch company tickets: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching company tickets: {exc}")

    items = [
        {
            "id": record.get("id", ""),
            "subject": record.get("subject", "") or "",
            "status": record.get("hs_pipeline_stage", "") or "",
            "priority": record.get("hs_ticket_priority", "") or "",
            "category": record.get("hs_ticket_category", "") or "",
        }
        for record in records
    ]
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Showing {len(items)} ticket(s).")],
        structuredContent={
            "type": "company_tickets",
            "company_id": company_id,
            "items": items,
            "total": len(items),
        },
    )


# ── Tool specs (registered by server) ────────────────────────────────────────

TOOL_SPECS: list[dict] = [
    {
        "name": "hs__get_companies",
        "description": (
            "Get companies from HubSpot CRM (10 most recent). "
            "Pass company_id to view one record; add action='edit' to open the edit form. "
            "Filters: name (text search), "
            "type (PROSPECT, PARTNER, RESELLER, VENDOR, OTHER), "
            "lifecyclestage (subscriber, lead, marketingqualifiedlead, salesqualifiedlead, "
            "opportunity, customer, evangelist, other), city, country."
        ),
        "handler": hs__get_companies,
    },
    {
        "name": "hs__create_company",
        "description": (
            "Create a new Company in HubSpot CRM. Requires: name. "
            "Optional: domain, type (PROSPECT/PARTNER/RESELLER/VENDOR/OTHER), "
            "lifecyclestage (subscriber/lead/marketingqualifiedlead/salesqualifiedlead/"
            "opportunity/customer/evangelist/other), city, phone, country, description."
        ),
        "handler": hs__create_company,
    },
    {
        "name": "hs__update_company",
        "description": (
            "Update an existing Company in HubSpot CRM by its record Id. "
            "Only fields provided will be updated. "
            "Fields: name, domain, type, lifecyclestage, city, phone, country, description."
        ),
        "handler": hs__update_company,
    },
    {
        "name": "hs__get_company_contacts",
        "description": (
            "Get contacts associated with a Company in HubSpot CRM. "
            "Required: company_id. Returns first name, last name, email, phone, lifecycle stage."
        ),
        "handler": hs__get_company_contacts,
        "_meta": {"ui": {"resourceUri": WIDGET_URI}},
    },
    {
        "name": "hs__get_company_deals",
        "description": (
            "Get deals associated with a Company in HubSpot CRM. "
            "Required: company_id. Returns deal name, amount, stage, close date, pipeline."
        ),
        "handler": hs__get_company_deals,
        "_meta": {"ui": {"resourceUri": WIDGET_URI}},
    },
    {
        "name": "hs__get_company_tickets",
        "description": (
            "Get tickets associated with a Company in HubSpot CRM. "
            "Required: company_id. Returns subject, status, priority, category."
        ),
        "handler": hs__get_company_tickets,
        "_meta": {"ui": {"resourceUri": WIDGET_URI}},
    },
]


# ── Prompt specs ──────────────────────────────────────────────────────────────

PROMPT_SPECS: list[dict] = []
