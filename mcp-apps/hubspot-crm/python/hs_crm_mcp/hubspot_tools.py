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
    "Contact": {
        "columns": [
            {"apiName": "firstname", "label": "First Name"},
            {"apiName": "lastname", "label": "Last Name"},
            {"apiName": "email", "label": "Email"},
            {"apiName": "phone", "label": "Phone"},
            {"apiName": "company", "label": "Company"},
        ],
        "hiddenColumns": [
            {"apiName": "lifecyclestage", "label": "Lifecycle Stage"},
            {"apiName": "jobtitle", "label": "Job Title"},
            {"apiName": "city", "label": "City"},
        ],
        "filterFields": {
            "email": {"operator": "EQ", "property": "email"},
            "lifecyclestage": {"operator": "EQ", "property": "lifecyclestage"},
            "firstname": {"operator": "CONTAINS_TOKEN", "property": "firstname"},
            "lastname": {"operator": "CONTAINS_TOKEN", "property": "lastname"},
        },
        "formFields": [
            {"name": "firstname", "label": "First Name", "required": True},
            {"name": "lastname", "label": "Last Name", "required": True},
            {"name": "email", "label": "Email", "required": True},
            {"name": "phone", "label": "Phone"},
            {"name": "jobtitle", "label": "Job Title"},
            {"name": "lifecyclestage", "label": "Lifecycle Stage", "picklist": ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer", "evangelist", "other"]},
            {"name": "city", "label": "City"},
            {"name": "company_name", "label": "Company (type full name) \ud83d\udd17", "fk": True},
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


# ── FK resolution helpers ─────────────────────────────────────────────────────

async def _resolve_company(client: Any, name: str) -> tuple[str | None, list[str]]:
    """Find a Company by name. Returns (id, suggestions).
    - id non-empty on exact match, suggestions = []
    - id None on miss, suggestions = up to 5 fuzzy candidates
    """
    filter_groups = [{"filters": [{"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": name}]}]
    results = await client.search_objects("companies", ["name"], filter_groups=filter_groups, limit=6)
    # Check for exact match
    for r in results:
        if (r.get("name") or "").lower() == name.lower():
            return r["id"], []
    if results:
        return None, [r.get("name", "") for r in results if r.get("name")][:5]
    # No fuzzy hits — fall back to most recent
    recent = await client.search_objects("companies", ["name"], limit=5)
    return None, [r.get("name", "") for r in recent if r.get("name")]


def _company_not_found_alert(name: str, suggestions: list[str]) -> types.CallToolResult:
    """Return Company-not-found as an ALERT (non-isError) so Copilot's planner
    doesn't retry the tool call."""
    msg = f"Company '{name}' not found."
    if suggestions:
        msg += f" Did you mean: {', '.join(suggestions)}?"
    return types.CallToolResult(
        content=[TextContent(type="text", text=msg)],
        structuredContent={
            "type": "alert",
            "level": "warning",
            "isError": True,
            "title": f"Company '{name}' not found",
            "message": msg,
            "suggestions": suggestions,
            "field": "company_name",
        },
    )


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

    # Branch 1a — action="create" → blank create form (prefill from filters)
    if action == "create":
        prefill = {field["name"]: "" for field in cfg["formFields"]}
        # Allow prefill from query params
        if name:
            prefill["name"] = name
        if type:
            prefill["type"] = type
        if lifecyclestage:
            prefill["lifecyclestage"] = lifecyclestage
        if city:
            prefill["city"] = city
        if country:
            prefill["country"] = country
        return types.CallToolResult(
            content=[TextContent(type="text", text="Opening create form for a new company.")],
            structuredContent={
                "type": "form", "entity": "company", "mode": "create",
                "recordId": "", "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 1b — id + action="edit"/"change" → prefilled edit form
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


# ── Contacts tools ────────────────────────────────────────────────────────────

async def hs__get_contacts(
    contact_id: str = "",
    firstname: str = "",
    lastname: str = "",
    email: str = "",
    company_name: str = "",
    lifecyclestage: str = "",
    action: str = "",
    refresh: bool = False,
) -> types.CallToolResult:
    """Get contacts. Branches: action=create→form, id+edit→form, id→single, company_name→FK filter, filters→list."""
    log.info("hs__get_contacts", contact_id=contact_id, action=action,
             firstname=firstname, lastname=lastname, email=email,
             company_name=company_name, lifecyclestage=lifecyclestage, refresh=refresh)

    cfg = _get_schema("Contact")

    # Branch 1 — action="create" → blank form
    if action == "create":
        prefill = {field["name"]: "" for field in cfg["formFields"]}
        if firstname:
            prefill["firstname"] = firstname
        if lastname:
            prefill["lastname"] = lastname
        if email:
            prefill["email"] = email
        if company_name:
            prefill["company_name"] = company_name
        return types.CallToolResult(
            content=[TextContent(type="text", text="Opening create form for a new contact.")],
            structuredContent={
                "type": "form", "entity": "contact", "mode": "create",
                "recordId": "", "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 2 — id + action="edit" → prefilled edit form
    if contact_id and action in ("edit", "change"):
        try:
            client = get_client()
            record = await client.get_object("contacts", contact_id, _get_all_props("Contact"))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Contact {contact_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error looking up contact: {exc}")

        prefill = {field["name"]: record.get(field["name"], "") or "" for field in cfg["formFields"] if field["name"] != "company_name"}
        # Resolve primary company name for FK field
        try:
            co_ids = await client.get_associated_ids("contacts", contact_id, "companies")
            if co_ids:
                cos = await client.batch_read("companies", co_ids[:1], ["name"])
                prefill["company_name"] = cos[0].get("name", "") if cos else ""
            else:
                prefill["company_name"] = ""
        except Exception:
            prefill["company_name"] = ""

        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Opening edit form for contact: {record.get('firstname', '')} {record.get('lastname', '')}.")],
            structuredContent={
                "type": "form", "entity": "contact", "mode": "edit",
                "recordId": record.get("id", contact_id), "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 3 — id alone → single record
    if contact_id:
        try:
            client = get_client()
            record = await client.get_object("contacts", contact_id, _get_list_props("Contact"))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Contact {contact_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching contact: {exc}")

        items = [record]
        return types.CallToolResult(
            content=[TextContent(type="text", text=_list_summary("contact(s)", items))],
            structuredContent={
                "type": "contacts", "total": len(items), "items": items,
                "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()},
            },
        )

    # Branch 4 — FK filter: company_name → search companies → get associated contacts
    if company_name:
        try:
            client = get_client()
            # Find companies matching name
            co_filter = [{"filters": [{"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": company_name}]}]
            companies = await client.search_objects("companies", ["name"], filter_groups=co_filter, limit=5)
            if not companies:
                return types.CallToolResult(
                    content=[TextContent(type="text", text=f"No company found matching '{company_name}'.")],
                    structuredContent={"type": "contacts", "total": 0, "items": [], "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()}},
                )
            # Gather all associated contact IDs
            all_contact_ids: list[str] = []
            for co in companies:
                co_id = co.get("id", "")
                if co_id:
                    ids = await client.get_associated_ids("companies", co_id, "contacts")
                    all_contact_ids.extend(ids)
            # Deduplicate
            all_contact_ids = list(dict.fromkeys(all_contact_ids))[:20]
            if not all_contact_ids:
                return types.CallToolResult(
                    content=[TextContent(type="text", text=f"No contacts found for '{company_name}'.")],
                    structuredContent={"type": "contacts", "total": 0, "items": [], "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()}},
                )
            props = _get_list_props("Contact")
            items = await client.batch_read("contacts", all_contact_ids, props)
            # Add company name to each contact
            for item in items:
                item["company"] = companies[0].get("name", "")
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Failed to fetch contacts for '{company_name}': {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching contacts: {exc}")

        cached_at = _cache_set(f"contacts:company={company_name}", "Contact", items)
        return types.CallToolResult(
            content=[TextContent(type="text", text=_list_summary("contact(s)", items))],
            structuredContent={
                "type": "contacts", "total": len(items), "items": items,
                "_schema": cfg, "_cache": {"hit": False, "cached_at": cached_at},
            },
        )

    # Branch 5 — property-based filters or bare list
    filter_params = {
        "firstname": firstname, "lastname": lastname,
        "email": email, "lifecyclestage": lifecyclestage,
    }
    filter_groups = _build_filter_groups("Contact", filter_params)

    filter_sig = _filter_signature(filter_params)
    cache_key = f"contacts:{filter_sig}" if filter_sig else "contacts"
    if not refresh:
        cached_items, cached_at = _cache_get(cache_key, "Contact")
        if cached_items is not None:
            return types.CallToolResult(
                content=[TextContent(type="text", text=_list_summary("contact(s)", cached_items, cache_hit=True))],
                structuredContent={
                    "type": "contacts", "total": len(cached_items), "items": cached_items,
                    "_schema": cfg, "_cache": {"hit": True, "cached_at": cached_at},
                },
            )

    try:
        client = get_client()
        props = _get_list_props("Contact")
        items = await client.search_objects("contacts", props, filter_groups=filter_groups, limit=10)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch contacts: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching contacts: {exc}")

    # Resolve company names via associations (best-effort)
    try:
        for item in items:
            co_ids = await client.get_associated_ids("contacts", item["id"], "companies")
            if co_ids:
                cos = await client.batch_read("companies", co_ids[:1], ["name"])
                item["company"] = cos[0].get("name", "") if cos else ""
            else:
                item["company"] = ""
    except Exception:
        pass  # company resolution is best-effort

    cached_at = _cache_set(cache_key, "Contact", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=_list_summary("contact(s)", items))],
        structuredContent={
            "type": "contacts", "total": len(items), "items": items,
            "_schema": cfg, "_cache": {"hit": False, "cached_at": cached_at},
        },
    )


async def hs__create_contact(
    firstname: str,
    lastname: str,
    email: str,
    phone: str = "",
    jobtitle: str = "",
    lifecyclestage: str = "",
    city: str = "",
    company_name: str = "",
) -> types.CallToolResult:
    """Create a new Contact in HubSpot CRM. Optionally associate to a company by name.
    Returns alert with suggestions if company_name doesn't match."""
    log.info("hs__create_contact", firstname=firstname, lastname=lastname,
             email=email, company_name=company_name)

    props: dict[str, Any] = {"firstname": firstname, "lastname": lastname, "email": email}
    if phone:
        props["phone"] = phone
    if jobtitle:
        props["jobtitle"] = jobtitle
    if lifecyclestage:
        props["lifecyclestage"] = lifecyclestage
    if city:
        props["city"] = city

    try:
        client = get_client()

        # Resolve FK BEFORE creating — alert pattern
        resolved_company_id: str | None = None
        if company_name:
            resolved_company_id, suggestions = await _resolve_company(client, company_name)
            if not resolved_company_id:
                return _company_not_found_alert(company_name, suggestions)

        new_id = await client.create_object("contacts", props)

        # Associate to resolved company
        if resolved_company_id:
            await client.create_association("contacts", new_id, "companies", resolved_company_id)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to create contact: {exc}")
    except Exception as exc:
        return _error_result(f"Error creating contact: {exc}")

    # Return refreshed contacts list
    _get_cache("Contact").clear()
    return await hs__get_contacts(refresh=True)


async def hs__update_contact(
    contact_id: str,
    firstname: str = "",
    lastname: str = "",
    email: str = "",
    phone: str = "",
    jobtitle: str = "",
    lifecyclestage: str = "",
    city: str = "",
) -> types.CallToolResult:
    """Update an existing Contact in HubSpot CRM by its record Id."""
    log.info("hs__update_contact", contact_id=contact_id, firstname=firstname,
             lastname=lastname, email=email)

    if not contact_id:
        return _error_result("contact_id is required.")

    updates: dict[str, Any] = {}
    if firstname:
        updates["firstname"] = firstname
    if lastname:
        updates["lastname"] = lastname
    if email:
        updates["email"] = email
    if phone:
        updates["phone"] = phone
    if jobtitle:
        updates["jobtitle"] = jobtitle
    if lifecyclestage:
        updates["lifecyclestage"] = lifecyclestage
    if city:
        updates["city"] = city

    if not updates:
        return _error_result("No fields to update.")

    try:
        client = get_client()
        await client.update_object("contacts", contact_id, updates)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to update contact: {exc}")
    except Exception as exc:
        return _error_result(f"Error updating contact: {exc}")

    _get_cache("Contact").clear()
    return await hs__get_contacts(refresh=True)


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
    {
        "name": "hs__get_contacts",
        "description": (
            "Get contacts from HubSpot CRM (10 most recent). "
            "Pass contact_id to view one record; add action='edit' to open the edit form; "
            "action='create' to open a blank create form. "
            "Filters: firstname, lastname, email, company_name (FK — searches all associations), "
            "lifecyclestage (subscriber/lead/marketingqualifiedlead/salesqualifiedlead/"
            "opportunity/customer/evangelist/other)."
        ),
        "handler": hs__get_contacts,
    },
    {
        "name": "hs__create_contact",
        "description": (
            "Create a new Contact in HubSpot CRM. Requires: firstname, lastname, email. "
            "Optional: phone, jobtitle, lifecyclestage, city, company_name (associates to matching company)."
        ),
        "handler": hs__create_contact,
    },
    {
        "name": "hs__update_contact",
        "description": (
            "Update an existing Contact in HubSpot CRM by its record Id. "
            "Only fields provided will be updated. "
            "Fields: firstname, lastname, email, phone, jobtitle, lifecyclestage, city."
        ),
        "handler": hs__update_contact,
    },
]


# ── Prompt specs ──────────────────────────────────────────────────────────────

PROMPT_SPECS: list[dict] = []
