"""HubSpot CRM tool handlers — Companies, Contacts, Deals, Orders, Products."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from cachetools import TTLCache
from mcp import types
from mcp.types import TextContent

from .hubspot_client import HubSpotAPIError, HubSpotAuthError, get_client

log = structlog.get_logger("hs")


# ── Entity Schemas ────────────────────────────────────────────────────────────

_ENTITY_SCHEMAS: dict[str, dict] = {
    "Company": {
        "columns": [
            {"apiName": "name", "label": "Name"},
            {"apiName": "domain", "label": "Domain"},
            {"apiName": "type", "label": "Type"},
            {"apiName": "lifecyclestage", "label": "Stage"},
            {"apiName": "city", "label": "City"},
            {"apiName": "country", "label": "Country"},
        ],
        "hiddenColumns": [
            {"apiName": "phone", "label": "Phone"},
            {"apiName": "industry", "label": "Industry"},
            {"apiName": "description", "label": "Description"},
        ],
        "filterFields": {
            "name": {"operator": "CONTAINS_TOKEN", "property": "name"},
            "domain": {"operator": "CONTAINS_TOKEN", "property": "domain"},
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
            {"name": "industry", "label": "Industry", "picklist": [
                "ACCOUNTING", "AUTOMOTIVE", "BANKING", "BIOTECHNOLOGY", "COMPUTER_SOFTWARE",
                "CONSTRUCTION", "CONSUMER_GOODS", "EDUCATION_MANAGEMENT", "ENTERTAINMENT",
                "FINANCIAL_SERVICES", "FOOD_BEVERAGES", "GOVERNMENT_ADMINISTRATION",
                "HEALTH_WELLNESS_AND_FITNESS", "HOSPITAL_HEALTH_CARE", "HOSPITALITY",
                "INFORMATION_TECHNOLOGY_AND_SERVICES", "INSURANCE", "INTERNET",
                "MANAGEMENT_CONSULTING", "MANUFACTURING", "MARKETING_AND_ADVERTISING",
                "MINING_METALS", "OIL_ENERGY", "PHARMACEUTICALS", "REAL_ESTATE",
                "RETAIL", "TELECOMMUNICATIONS", "TRANSPORTATION_TRUCKING_RAILROAD", "UTILITIES",
            ]},
            {"name": "description", "label": "Description", "multiline": True},
        ],
    },
    "Contact": {
        "columns": [
            {"apiName": "firstname", "label": "First Name"},
            {"apiName": "lastname", "label": "Last Name"},
            {"apiName": "email", "label": "Email"},
            {"apiName": "phone", "label": "Phone"},
            {"apiName": "jobtitle", "label": "Job Title"},
            {"apiName": "city", "label": "City"},
            {"apiName": "lifecyclestage", "label": "Lifecycle Stage"},
            {"apiName": "company", "label": "Company"},
        ],
        "hiddenColumns": [],
        "filterFields": {
            "email": {"operator": "EQ", "property": "email"},
            "lifecyclestage": {"operator": "EQ", "property": "lifecyclestage"},
            "firstname": {"operator": "CONTAINS_TOKEN", "property": "firstname"},
            "lastname": {"operator": "CONTAINS_TOKEN", "property": "lastname"},
            "jobtitle": {"operator": "CONTAINS_TOKEN", "property": "jobtitle"},
            "city": {"operator": "CONTAINS_TOKEN", "property": "city"},
        },
        "formFields": [
            {"name": "firstname", "label": "First Name", "required": True},
            {"name": "lastname", "label": "Last Name", "required": True},
            {"name": "email", "label": "Email", "required": True},
            {"name": "phone", "label": "Phone"},
            {"name": "jobtitle", "label": "Job Title"},
            {"name": "lifecyclestage", "label": "Lifecycle Stage", "picklist": ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer", "evangelist", "other"]},
            {"name": "city", "label": "City"},
            {"name": "company_name", "label": "Company (type full name)", "fk": True},
        ],
    },
    "Deal": {
        "columns": [
               {"apiName": "dealname", "label": "Deal Name"},
               {"apiName": "amount", "label": "Amount"},
               {"apiName": "dealstage", "label": "Stage"},
               {"apiName": "pipeline", "label": "Pipeline"},
               {"apiName": "closedate", "label": "Close Date"},
               {"apiName": "company", "label": "Company"},
        ],
        "hiddenColumns": [
               {"apiName": "dealtype", "label": "Deal Type"},
               {"apiName": "description", "label": "Description"},
        ],
        "filterFields": {
               "dealname": {"operator": "CONTAINS_TOKEN", "property": "dealname"},
               "dealstage": {"operator": "EQ", "property": "dealstage"},
               "pipeline": {"operator": "EQ", "property": "pipeline"},
               "dealtype": {"operator": "EQ", "property": "dealtype"},
        },
        "formFields": [
               {"name": "dealname", "label": "Deal Name", "required": True},
               {"name": "amount", "label": "Amount"},
               {"name": "pipeline", "label": "Pipeline", "required": True, "picklist": ["default"]},
               {"name": "dealstage", "label": "Stage", "required": True, "picklist": [
                   "3442945774", "3442945775", "3442945776", "3442945777", "closedwon", "closedlost",
               ]},
               {"name": "closedate", "label": "Close Date"},
               {"name": "dealtype", "label": "Deal Type", "picklist": ["newbusiness", "existingbusiness"]},
               {"name": "description", "label": "Description", "multiline": True},
               {"name": "company_name", "label": "Company (type full name)", "fk": True},
               {"name": "contact_name", "label": "Contact (type full name)", "fk": True},
        ],
        "stageLabels": {
               "3442945774": "Lead Captured",
               "3442945775": "Qualified",
               "3442945776": "Proposal Sent",
               "3442945777": "Negotiation",
               "closedwon": "Closed Won",
               "closedlost": "Closed Lost",
        },
    },
    "Product": {
        "columns": [
            {"apiName": "name", "label": "Name"},
            {"apiName": "hs_sku", "label": "SKU"},
            {"apiName": "price", "label": "Unit Price"},
            {"apiName": "hs_status", "label": "Status"},
            {"apiName": "hs_product_type", "label": "Type"},
            {"apiName": "recurringbillingfrequency", "label": "Billing Freq"},
        ],
        "hiddenColumns": [
            {"apiName": "description", "label": "Description"},
            {"apiName": "hs_recurring_billing_period", "label": "Term"},
        ],
        "filterFields": {
            "name": {"operator": "CONTAINS_TOKEN", "property": "name"},
            "hs_product_type": {"operator": "EQ", "property": "hs_product_type"},
            "hs_status": {"operator": "EQ", "property": "hs_status"},
        },
        "formFields": [
            {"name": "name", "label": "Product Name", "required": True},
            {"name": "hs_sku", "label": "SKU"},
            {"name": "price", "label": "Unit Price"},
            {"name": "hs_status", "label": "Status", "picklist": ["active", "inactive"]},
            {"name": "hs_product_type", "label": "Product Type", "picklist": ["inventory", "non_inventory", "service"]},
            {"name": "recurringbillingfrequency", "label": "Billing Frequency", "picklist": [
                "weekly", "biweekly", "monthly", "quarterly", "per_six_months",
                "annually", "per_two_years", "per_three_years", "per_four_years", "per_five_years",
            ]},
            {"name": "hs_recurring_billing_period", "label": "Term"},
            {"name": "description", "label": "Description", "multiline": True},
        ],
    },
    "Order": {
        "columns": [
               {"apiName": "hs_order_name", "label": "Order Name"},
               {"apiName": "hs_total_price", "label": "Total"},
               {"apiName": "hs_currency_code", "label": "Currency"},
               {"apiName": "hs_fulfillment_status", "label": "Fulfillment"},
               {"apiName": "hs_payment_status", "label": "Payment"},
               {"apiName": "hs_closed_date", "label": "Closed Date"},
               {"apiName": "contact", "label": "Contact"},
               {"apiName": "company", "label": "Company"},
               {"apiName": "deal", "label": "Deal"},
        ],
        "hiddenColumns": [
               {"apiName": "hs_source_store", "label": "Source Store"},
        ],
        "filterFields": {
               "hs_order_name": {"operator": "CONTAINS_TOKEN", "property": "hs_order_name"},
               "hs_fulfillment_status": {"operator": "EQ", "property": "hs_fulfillment_status"},
               "hs_payment_status": {"operator": "EQ", "property": "hs_payment_status"},
               "hs_currency_code": {"operator": "EQ", "property": "hs_currency_code"},
        },
        "formFields": [
               {"name": "hs_order_name", "label": "Order Name", "required": True},
               {"name": "hs_total_price", "label": "Total Price"},
               {"name": "hs_currency_code", "label": "Currency", "picklist": ["USD", "EUR", "GBP", "CAD", "AUD", "INR"]},
               {"name": "hs_fulfillment_status", "label": "Fulfillment Status"},
               {"name": "hs_payment_status", "label": "Payment Status"},
               {"name": "hs_closed_date", "label": "Closed Date"},
               {"name": "hs_source_store", "label": "Source Store"},
               {"name": "company_name", "label": "Company (type full name)", "fk": True},
               {"name": "contact_name", "label": "Contact (type full name)", "fk": True},
               {"name": "deal_name", "label": "Deal (type full name)", "fk": True},
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


async def _resolve_contact(client: Any, name: str) -> tuple[str | None, list[str]]:
    """Find a Contact by name (first+last). Returns (id, suggestions)."""
    parts = name.strip().split(None, 1)
    first = parts[0] if parts else name
    filter_groups = [{"filters": [{"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": first}]}]
    results = await client.search_objects("contacts", ["firstname", "lastname", "email"], filter_groups=filter_groups, limit=6)
    # Check for exact match on full name
    for r in results:
        full = f"{r.get('firstname', '')} {r.get('lastname', '')}".strip()
        if full.lower() == name.strip().lower():
            return r["id"], []
    if results:
        return None, [f"{r.get('firstname', '')} {r.get('lastname', '')}".strip() for r in results if r.get("firstname")][:5]
    recent = await client.search_objects("contacts", ["firstname", "lastname"], limit=5)
    return None, [f"{r.get('firstname', '')} {r.get('lastname', '')}".strip() for r in recent if r.get("firstname")]


def _contact_not_found_alert(name: str, suggestions: list[str]) -> types.CallToolResult:
    """Return Contact-not-found as an ALERT."""
    msg = f"Contact '{name}' not found."
    if suggestions:
        msg += f" Did you mean: {', '.join(suggestions)}?"
    return types.CallToolResult(
        content=[TextContent(type="text", text=msg)],
        structuredContent={
            "type": "alert",
            "level": "warning",
            "isError": True,
            "title": f"Contact '{name}' not found",
            "message": msg,
            "suggestions": suggestions,
            "field": "contact_name",
        },
    )


async def _resolve_deal(client: Any, name: str) -> tuple[str | None, list[str]]:
    """Find a Deal by name. Returns (id, suggestions)."""
    filter_groups = [{"filters": [{"propertyName": "dealname", "operator": "CONTAINS_TOKEN", "value": name}]}]
    results = await client.search_objects("deals", ["dealname"], filter_groups=filter_groups, limit=6)
    for r in results:
        if (r.get("dealname") or "").lower() == name.lower():
            return r["id"], []
    if results:
        return None, [r.get("dealname", "") for r in results if r.get("dealname")][:5]
    recent = await client.search_objects("deals", ["dealname"], limit=5)
    return None, [r.get("dealname", "") for r in recent if r.get("dealname")]


def _deal_not_found_alert(name: str, suggestions: list[str]) -> types.CallToolResult:
    """Return Deal-not-found as an ALERT."""
    msg = f"Deal '{name}' not found."
    if suggestions:
        msg += f" Did you mean: {', '.join(suggestions)}?"
    return types.CallToolResult(
        content=[TextContent(type="text", text=msg)],
        structuredContent={
            "type": "alert",
            "level": "warning",
            "isError": True,
            "title": f"Deal '{name}' not found",
            "message": msg,
            "suggestions": suggestions,
            "field": "deal_name",
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
    domain: str = "",
    type: str = "",
    lifecyclestage: str = "",
    city: str = "",
    country: str = "",
    action: str = "",
    refresh: bool = False,
) -> types.CallToolResult:
    """Get companies. Branches: id+edit→form, id→list-of-one, filters→filtered, bare→top 5."""
    log.info("hs__get_companies", company_id=company_id, action=action,
             name=name, domain=domain, type=type, lifecyclestage=lifecyclestage,
             city=city, country=country, refresh=refresh)

    cfg = _get_schema("Company")

    # Branch 1a — action="create" → blank create form (prefill from filters)
    if action == "create":
        prefill = {field["name"]: "" for field in cfg["formFields"]}
        # Allow prefill from query params
        if name:
            prefill["name"] = name
        if domain:
            prefill["domain"] = domain
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
        "name": name, "domain": domain, "type": type,
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


# ── Generic associations tool ─────────────────────────────────────────────────

_ASSOC_CONFIG: dict[str, dict] = {
    "contacts": {
        "props": ["firstname", "lastname", "email", "phone", "lifecyclestage"],
        "map": lambda r: {
            "id": r.get("id", ""),
            "firstname": r.get("firstname", "") or "",
            "lastname": r.get("lastname", "") or "",
            "email": r.get("email", "") or "",
            "phone": r.get("phone", "") or "",
            "lifecyclestage": r.get("lifecyclestage", "") or "",
        },
        "label": "contact",
    },
    "deals": {
        "props": ["dealname", "amount", "dealstage", "closedate", "pipeline"],
        "map": lambda r: {
            "id": r.get("id", ""),
            "dealname": r.get("dealname", "") or "",
            "amount": r.get("amount", "") or "",
            "dealstage": r.get("dealstage", "") or "",
            "closedate": r.get("closedate", "") or "",
            "pipeline": r.get("pipeline", "") or "",
        },
        "label": "deal",
    },
    "tickets": {
        "props": ["subject", "hs_pipeline_stage", "hs_ticket_priority", "hs_ticket_category"],
        "map": lambda r: {
            "id": r.get("id", ""),
            "subject": r.get("subject", "") or "",
            "status": r.get("hs_pipeline_stage", "") or "",
            "priority": r.get("hs_ticket_priority", "") or "",
            "category": r.get("hs_ticket_category", "") or "",
        },
        "label": "ticket",
    },
    "companies": {
        "props": ["name", "domain", "city", "industry", "lifecyclestage"],
        "map": lambda r: {
            "id": r.get("id", ""),
            "name": r.get("name", "") or "",
            "domain": r.get("domain", "") or "",
            "city": r.get("city", "") or "",
            "industry": r.get("industry", "") or "",
            "lifecyclestage": r.get("lifecyclestage", "") or "",
        },
        "label": "company",
    },
    "line_items": {
        "props": ["name", "quantity", "price", "amount", "hs_sku"],
        "map": lambda r: {
            "id": r.get("id", ""),
            "name": r.get("name", "") or "",
            "quantity": r.get("quantity", "") or "",
            "price": r.get("price", "") or "",
            "amount": r.get("amount", "") or "",
            "sku": r.get("hs_sku", "") or "",
        },
        "label": "line item",
    },
}

_VALID_SOURCES = {"companies", "contacts", "deals", "orders"}
_VALID_TARGETS = {"companies", "contacts", "deals", "tickets", "line_items"}


async def hs__get_associations(
    entity_type: str,
    entity_id: str,
    association_type: str,
    refresh: bool = False,
) -> types.CallToolResult:
    """Get records associated to an entity via HubSpot Associations API.

    entity_type: source object (companies, contacts).
    entity_id:   HubSpot record id.
    association_type: target object (contacts, deals, tickets, companies).
    """
    log.info("hs__get_associations", entity_type=entity_type, entity_id=entity_id,
             association_type=association_type, refresh=refresh)

    if not entity_id:
        return _error_result("entity_id is required.")
    if entity_type not in _VALID_SOURCES:
        return _error_result(f"entity_type must be one of {sorted(_VALID_SOURCES)}.")
    if association_type not in _VALID_TARGETS or association_type == entity_type:
        return _error_result(f"association_type must be one of {sorted(_VALID_TARGETS - {entity_type})}.")

    cfg = _ASSOC_CONFIG[association_type]

    try:
        client = get_client()
        assoc_ids = await client.get_associated_ids(entity_type, entity_id, association_type)
        records = await client.batch_read(association_type, assoc_ids, cfg["props"])
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch {association_type}: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching {association_type}: {exc}")

    items = [cfg["map"](r) for r in records]
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Showing {len(items)} {cfg['label']}(s).")],
        structuredContent={
            "type": f"{entity_type}_{association_type}",
            "entity_id": entity_id,
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
    jobtitle: str = "",
    city: str = "",
    action: str = "",
    refresh: bool = False,
) -> types.CallToolResult:
    """Get contacts. Branches: action=create→form, id+edit→form, id→single, company_name→FK filter, filters→list."""
    log.info("hs__get_contacts", contact_id=contact_id, action=action,
             firstname=firstname, lastname=lastname, email=email,
             company_name=company_name, lifecyclestage=lifecyclestage,
             jobtitle=jobtitle, city=city, refresh=refresh)

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
        "jobtitle": jobtitle, "city": city,
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


# ── Deals tools ───────────────────────────────────────────────────────────────

def _deal_stage_label(stage_id: str) -> str:
    """Convert pipeline stage ID to human-readable label."""
    labels = _get_schema("Deal").get("stageLabels", {})
    return labels.get(stage_id, stage_id)


async def hs__get_deals(
    deal_id: str = "",
    dealname: str = "",
    dealstage: str = "",
    pipeline: str = "",
    dealtype: str = "",
    company_name: str = "",
    action: str = "",
    refresh: bool = False,
) -> types.CallToolResult:
    """Get deals from HubSpot CRM."""
    log.info("hs__get_deals", deal_id=deal_id, action=action, dealname=dealname,
             dealstage=dealstage, pipeline=pipeline, company_name=company_name, refresh=refresh)

    schema = _get_schema("Deal")

    # ── Branch: blank create form ────────────────────────────────────────────
    if action == "create":
        return types.CallToolResult(
            content=[TextContent(type="text", text="Opening deal create form.")],
            structuredContent={
                "type": "form",
                "entity": "deal",
                "mode": "create",
                "_schema": schema,
            },
        )

    # ── Branch: single record / edit form ────────────────────────────────────
    if deal_id:
        try:
            client = get_client()
            record = await client.get_object("deals", deal_id, _get_all_props("Deal"))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Failed to fetch deal: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching deal: {exc}")

        if not record:
            return _error_result(f"Deal {deal_id} not found.")

        # Resolve associated company name
        try:
            co_ids = await client.get_associated_ids("deals", deal_id, "companies")
            if co_ids:
                cos = await client.batch_read("companies", co_ids[:1], ["name"])
                record["company"] = cos[0].get("name", "") if cos else ""
            else:
                record["company"] = ""
        except Exception:
            record["company"] = ""

        # Convert stage ID to label for display
        record["dealstage_label"] = _deal_stage_label(record.get("dealstage", ""))

        if action == "edit":
            return types.CallToolResult(
                content=[TextContent(type="text", text=f"Opening edit form for deal '{record.get('dealname', '')}'.")],
                structuredContent={
                    "type": "form",
                    "entity": "deal",
                    "mode": "edit",
                    "recordId": deal_id,
                    "prefill": record,
                    "_schema": schema,
                },
            )

        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Deal: {record.get('dealname', '')}.")],
            structuredContent={
                "type": "deals",
                "items": [record],
                "total": 1,
                "_schema": schema,
            },
        )

    # ── Branch: FK filter by company_name ────────────────────────────────────
    if company_name:
        try:
            client = get_client()
            co_id, suggestions = await _resolve_company(client, company_name)
            if not co_id:
                return _company_not_found_alert(company_name, suggestions)
            deal_ids = await client.get_associated_ids("companies", co_id, "deals")
            if not deal_ids:
                return types.CallToolResult(
                    content=[TextContent(type="text", text=f"No deals found for company '{company_name}'.")],
                    structuredContent={"type": "deals", "items": [], "total": 0, "_schema": schema},
                )
            props = _get_list_props("Deal")
            items = await client.batch_read("deals", deal_ids, [p for p in props if p != "company"])
            # Attach company name and stage labels
            for item in items:
                item["company"] = company_name
                item["dealstage_label"] = _deal_stage_label(item.get("dealstage", ""))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching deals by company: {exc}")

        cached_at = _cache_set(f"deals_co_{company_name}", "Deal", items)
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Showing {len(items)} deal(s) for '{company_name}'.")],
            structuredContent={
                "type": "deals",
                "items": items,
                "total": len(items),
                "_schema": schema,
                "_cache": {"hit": False, "cached_at": cached_at},
            },
        )

    # ── Branch: list / filter ────────────────────────────────────────────────
    filter_params = {k: v for k, v in {"dealname": dealname, "dealstage": dealstage, "pipeline": pipeline, "dealtype": dealtype}.items() if v}
    filter_sig = _filter_signature(filter_params)
    cache_key = f"deals_{filter_sig}" if filter_sig else "deals_all"

    if not refresh:
        cached_items, cached_at = _cache_get(cache_key, "Deal")
        if cached_items is not None:
            return types.CallToolResult(
                content=[TextContent(type="text", text=_list_summary("deal(s)", cached_items, cache_hit=True))],
                structuredContent={
                    "type": "deals",
                    "items": cached_items,
                    "total": len(cached_items),
                    "_schema": schema,
                    "_cache": {"hit": True, "cached_at": cached_at},
                },
            )

    try:
        client = get_client()
        filter_groups = _build_filter_groups("Deal", filter_params) if filter_params else None
        props = _get_list_props("Deal")
        results = await client.search_objects("deals", [p for p in props if p != "company"], filter_groups=filter_groups, limit=10)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to search deals: {exc}")
    except Exception as exc:
        return _error_result(f"Error searching deals: {exc}")

    # Resolve company names for each deal
    items = []
    for r in results:
        item = {p: r.get(p, "") or "" for p in props if p != "company"}
        item["id"] = r.get("id", "")
        item["dealstage_label"] = _deal_stage_label(item.get("dealstage", ""))
        try:
            co_ids = await client.get_associated_ids("deals", item["id"], "companies")
            if co_ids:
                cos = await client.batch_read("companies", co_ids[:1], ["name"])
                item["company"] = cos[0].get("name", "") if cos else ""
            else:
                item["company"] = ""
        except Exception:
            item["company"] = ""
        items.append(item)

    cached_at = _cache_set(cache_key, "Deal", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=_list_summary("deal(s)", items))],
        structuredContent={
            "type": "deals",
            "items": items,
            "total": len(items),
            "_schema": schema,
            "_cache": {"hit": False, "cached_at": cached_at},
        },
    )


async def hs__create_deal(
    dealname: str = "",
    amount: str = "",
    pipeline: str = "default",
    dealstage: str = "",
    closedate: str = "",
    dealtype: str = "",
    description: str = "",
    company_name: str = "",
    contact_name: str = "",
) -> types.CallToolResult:
    """Create a new Deal in HubSpot CRM."""
    log.info("hs__create_deal", dealname=dealname, dealstage=dealstage, company_name=company_name)
    if not dealname:
        return _error_result("dealname is required.")
    if not dealstage:
        return _error_result("dealstage is required.")

    # Resolve company FK
    company_id: str | None = None
    if company_name:
        try:
            client = get_client()
            company_id, suggestions = await _resolve_company(client, company_name)
            if not company_id:
                return _company_not_found_alert(company_name, suggestions)
        except Exception as exc:
            return _error_result(f"Error resolving company: {exc}")

    # Resolve contact FK
    contact_id: str | None = None
    if contact_name:
        try:
            client = get_client()
            contact_id, suggestions = await _resolve_contact(client, contact_name)
            if not contact_id:
                return _contact_not_found_alert(contact_name, suggestions)
        except Exception as exc:
            return _error_result(f"Error resolving contact: {exc}")

    props = {"dealname": dealname, "pipeline": pipeline or "default", "dealstage": dealstage}
    if amount:
        props["amount"] = amount
    if closedate:
        props["closedate"] = closedate
    if dealtype:
        props["dealtype"] = dealtype
    if description:
        props["description"] = description

    try:
        client = get_client()
        new_id = await client.create_object("deals", props)
        # Create associations
        if company_id:
            await client.create_association("deals", new_id, "companies", company_id)
        if contact_id:
            await client.create_association("deals", new_id, "contacts", contact_id)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to create deal: {exc}")
    except Exception as exc:
        return _error_result(f"Error creating deal: {exc}")

    _get_cache("Deal").clear()
    return await hs__get_deals(refresh=True)


async def hs__update_deal(
    deal_id: str = "",
    dealname: str = "",
    amount: str = "",
    pipeline: str = "",
    dealstage: str = "",
    closedate: str = "",
    dealtype: str = "",
    description: str = "",
) -> types.CallToolResult:
    """Update an existing Deal in HubSpot CRM."""
    log.info("hs__update_deal", deal_id=deal_id)
    if not deal_id:
        return _error_result("deal_id is required.")

    props: dict[str, str] = {}
    if dealname:
        props["dealname"] = dealname
    if amount:
        props["amount"] = amount
    if pipeline:
        props["pipeline"] = pipeline
    if dealstage:
        props["dealstage"] = dealstage
    if closedate:
        props["closedate"] = closedate
    if dealtype:
        props["dealtype"] = dealtype
    if description:
        props["description"] = description

    if not props:
        return _error_result("No fields to update.")

    try:
        client = get_client()
        await client.update_object("deals", deal_id, props)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to update deal: {exc}")
    except Exception as exc:
        return _error_result(f"Error updating deal: {exc}")

    _get_cache("Deal").clear()
    return await hs__get_deals(refresh=True)


# ── Orders tools ──────────────────────────────────────────────────────────────

async def hs__get_orders(
    order_id: str = "",
    hs_order_name: str = "",
    hs_fulfillment_status: str = "",
    hs_payment_status: str = "",
    hs_currency_code: str = "",
    company_name: str = "",
    contact_name: str = "",
    deal_name: str = "",
    action: str = "",
    refresh: bool = False,
) -> types.CallToolResult:
    """Get orders from HubSpot CRM."""
    log.info("hs__get_orders", order_id=order_id, action=action,
             hs_order_name=hs_order_name, company_name=company_name, refresh=refresh)

    schema = _get_schema("Order")

    # ── Branch: blank create form ────────────────────────────────────────────
    if action == "create":
        return types.CallToolResult(
            content=[TextContent(type="text", text="Opening order create form.")],
            structuredContent={
                "type": "form",
                "entity": "order",
                "mode": "create",
                "_schema": schema,
            },
        )

    # ── Branch: single record / edit form ────────────────────────────────────
    if order_id:
        try:
            client = get_client()
            props = [c["apiName"] for c in schema["columns"] + schema["hiddenColumns"] if not c["apiName"] in ("contact", "company", "deal")]
            record = await client.get_object("orders", order_id, props)
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Failed to fetch order: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching order: {exc}")

        if not record:
            return _error_result(f"Order {order_id} not found.")

        # Resolve FK associations
        try:
            co_ids = await client.get_associated_ids("orders", order_id, "companies")
            if co_ids:
                cos = await client.batch_read("companies", co_ids[:1], ["name"])
                record["company"] = cos[0].get("name", "") if cos else ""
            else:
                record["company"] = ""
        except Exception:
            record["company"] = ""

        try:
            ct_ids = await client.get_associated_ids("orders", order_id, "contacts")
            if ct_ids:
                cts = await client.batch_read("contacts", ct_ids[:1], ["firstname", "lastname"])
                record["contact"] = f"{cts[0].get('firstname', '')} {cts[0].get('lastname', '')}".strip() if cts else ""
            else:
                record["contact"] = ""
        except Exception:
            record["contact"] = ""

        try:
            deal_ids = await client.get_associated_ids("orders", order_id, "deals")
            if deal_ids:
                deals = await client.batch_read("deals", deal_ids[:1], ["dealname"])
                record["deal"] = deals[0].get("dealname", "") if deals else ""
            else:
                record["deal"] = ""
        except Exception:
            record["deal"] = ""

        if action == "edit":
            return types.CallToolResult(
                content=[TextContent(type="text", text=f"Opening edit form for order '{record.get('hs_order_name', '')}'.")],
                structuredContent={
                    "type": "form",
                    "entity": "order",
                    "mode": "edit",
                    "recordId": order_id,
                    "prefill": record,
                    "_schema": schema,
                },
            )

        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Order: {record.get('hs_order_name', '')}.")],
            structuredContent={
                "type": "orders",
                "items": [record],
                "total": 1,
                "_schema": schema,
            },
        )

    # ── Branch: FK filter by company_name ────────────────────────────────────
    if company_name:
        try:
            client = get_client()
            co_id, suggestions = await _resolve_company(client, company_name)
            if not co_id:
                return _company_not_found_alert(company_name, suggestions)
            order_ids = await client.get_associated_ids("companies", co_id, "orders")
            if not order_ids:
                return types.CallToolResult(
                    content=[TextContent(type="text", text=f"No orders found for company '{company_name}'.")],
                    structuredContent={"type": "orders", "items": [], "total": 0, "_schema": schema},
                )
            native_props = [c["apiName"] for c in schema["columns"] if c["apiName"] not in ("contact", "company", "deal")]
            items = await client.batch_read("orders", order_ids, native_props)
            for item in items:
                item["company"] = company_name
                item["contact"] = ""
                item["deal"] = ""
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching orders by company: {exc}")

        cached_at = _cache_set(f"orders_co_{company_name}", "Order", items)
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Showing {len(items)} order(s) for '{company_name}'.")],
            structuredContent={"type": "orders", "items": items, "total": len(items), "_schema": schema, "_cache": {"hit": False, "cached_at": cached_at}},
        )

    # ── Branch: FK filter by contact_name ────────────────────────────────────
    if contact_name:
        try:
            client = get_client()
            ct_id, suggestions = await _resolve_contact(client, contact_name)
            if not ct_id:
                return _contact_not_found_alert(contact_name, suggestions)
            order_ids = await client.get_associated_ids("contacts", ct_id, "orders")
            if not order_ids:
                return types.CallToolResult(
                    content=[TextContent(type="text", text=f"No orders found for contact '{contact_name}'.")],
                    structuredContent={"type": "orders", "items": [], "total": 0, "_schema": schema},
                )
            native_props = [c["apiName"] for c in schema["columns"] if c["apiName"] not in ("contact", "company", "deal")]
            items = await client.batch_read("orders", order_ids, native_props)
            for item in items:
                item["contact"] = contact_name
                item["company"] = ""
                item["deal"] = ""
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching orders by contact: {exc}")

        cached_at = _cache_set(f"orders_ct_{contact_name}", "Order", items)
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Showing {len(items)} order(s) for '{contact_name}'.")],
            structuredContent={"type": "orders", "items": items, "total": len(items), "_schema": schema, "_cache": {"hit": False, "cached_at": cached_at}},
        )

    # ── Branch: FK filter by deal_name ───────────────────────────────────────
    if deal_name:
        try:
            client = get_client()
            d_id, suggestions = await _resolve_deal(client, deal_name)
            if not d_id:
                return _deal_not_found_alert(deal_name, suggestions)
            order_ids = await client.get_associated_ids("deals", d_id, "orders")
            if not order_ids:
                return types.CallToolResult(
                    content=[TextContent(type="text", text=f"No orders found for deal '{deal_name}'.")],
                    structuredContent={"type": "orders", "items": [], "total": 0, "_schema": schema},
                )
            native_props = [c["apiName"] for c in schema["columns"] if c["apiName"] not in ("contact", "company", "deal")]
            items = await client.batch_read("orders", order_ids, native_props)
            for item in items:
                item["deal"] = deal_name
                item["contact"] = ""
                item["company"] = ""
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching orders by deal: {exc}")

        cached_at = _cache_set(f"orders_dl_{deal_name}", "Order", items)
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Showing {len(items)} order(s) for '{deal_name}'.")],
            structuredContent={"type": "orders", "items": items, "total": len(items), "_schema": schema, "_cache": {"hit": False, "cached_at": cached_at}},
        )

    # ── Branch: list / filter ────────────────────────────────────────────────
    filter_params = {k: v for k, v in {
        "hs_order_name": hs_order_name,
        "hs_fulfillment_status": hs_fulfillment_status,
        "hs_payment_status": hs_payment_status,
        "hs_currency_code": hs_currency_code,
    }.items() if v}
    filter_sig = _filter_signature(filter_params)
    cache_key = f"orders_{filter_sig}" if filter_sig else "orders_all"

    if not refresh:
        cached_items, cached_at = _cache_get(cache_key, "Order")
        if cached_items is not None:
            return types.CallToolResult(
                content=[TextContent(type="text", text=_list_summary("order(s)", cached_items, cache_hit=True))],
                structuredContent={"type": "orders", "items": cached_items, "total": len(cached_items), "_schema": schema, "_cache": {"hit": True, "cached_at": cached_at}},
            )

    try:
        client = get_client()
        filter_groups = _build_filter_groups("Order", filter_params) if filter_params else None
        native_props = [c["apiName"] for c in schema["columns"] if c["apiName"] not in ("contact", "company", "deal")]
        results = await client.search_objects("orders", native_props, filter_groups=filter_groups, limit=10)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to search orders: {exc}")
    except Exception as exc:
        return _error_result(f"Error searching orders: {exc}")

    # Resolve FK names for each order
    items = []
    for r in results:
        item = {p: r.get(p, "") or "" for p in native_props}
        item["id"] = r.get("id", "")
        try:
            co_ids = await client.get_associated_ids("orders", item["id"], "companies")
            if co_ids:
                cos = await client.batch_read("companies", co_ids[:1], ["name"])
                item["company"] = cos[0].get("name", "") if cos else ""
            else:
                item["company"] = ""
        except Exception:
            item["company"] = ""
        try:
            ct_ids = await client.get_associated_ids("orders", item["id"], "contacts")
            if ct_ids:
                cts = await client.batch_read("contacts", ct_ids[:1], ["firstname", "lastname"])
                item["contact"] = f"{cts[0].get('firstname', '')} {cts[0].get('lastname', '')}".strip() if cts else ""
            else:
                item["contact"] = ""
        except Exception:
            item["contact"] = ""
        try:
            d_ids = await client.get_associated_ids("orders", item["id"], "deals")
            if d_ids:
                ds = await client.batch_read("deals", d_ids[:1], ["dealname"])
                item["deal"] = ds[0].get("dealname", "") if ds else ""
            else:
                item["deal"] = ""
        except Exception:
            item["deal"] = ""
        items.append(item)

    cached_at = _cache_set(cache_key, "Order", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=_list_summary("order(s)", items))],
        structuredContent={"type": "orders", "items": items, "total": len(items), "_schema": schema, "_cache": {"hit": False, "cached_at": cached_at}},
    )


async def hs__create_order(
    hs_order_name: str = "",
    hs_total_price: str = "",
    hs_currency_code: str = "",
    hs_fulfillment_status: str = "",
    hs_payment_status: str = "",
    hs_closed_date: str = "",
    hs_source_store: str = "",
    company_name: str = "",
    contact_name: str = "",
    deal_name: str = "",
) -> types.CallToolResult:
    """Create a new Order in HubSpot CRM."""
    log.info("hs__create_order", hs_order_name=hs_order_name, company_name=company_name)
    if not hs_order_name:
        return _error_result("hs_order_name is required.")

    # Resolve FKs
    company_id: str | None = None
    if company_name:
        try:
            client = get_client()
            company_id, suggestions = await _resolve_company(client, company_name)
            if not company_id:
                return _company_not_found_alert(company_name, suggestions)
        except Exception as exc:
            return _error_result(f"Error resolving company: {exc}")

    contact_id: str | None = None
    if contact_name:
        try:
            client = get_client()
            contact_id, suggestions = await _resolve_contact(client, contact_name)
            if not contact_id:
                return _contact_not_found_alert(contact_name, suggestions)
        except Exception as exc:
            return _error_result(f"Error resolving contact: {exc}")

    deal_id: str | None = None
    if deal_name:
        try:
            client = get_client()
            deal_id, suggestions = await _resolve_deal(client, deal_name)
            if not deal_id:
                return _deal_not_found_alert(deal_name, suggestions)
        except Exception as exc:
            return _error_result(f"Error resolving deal: {exc}")

    props: dict[str, str] = {"hs_order_name": hs_order_name}
    if hs_total_price:
        props["hs_total_price"] = hs_total_price
    if hs_currency_code:
        props["hs_currency_code"] = hs_currency_code
    if hs_fulfillment_status:
        props["hs_fulfillment_status"] = hs_fulfillment_status
    if hs_payment_status:
        props["hs_payment_status"] = hs_payment_status
    if hs_closed_date:
        props["hs_closed_date"] = hs_closed_date
    if hs_source_store:
        props["hs_source_store"] = hs_source_store

    try:
        client = get_client()
        new_id = await client.create_object("orders", props)
        if company_id:
            await client.create_association("orders", new_id, "companies", company_id)
        if contact_id:
            await client.create_association("orders", new_id, "contacts", contact_id)
        if deal_id:
            await client.create_association("orders", new_id, "deals", deal_id)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to create order: {exc}")
    except Exception as exc:
        return _error_result(f"Error creating order: {exc}")

    _get_cache("Order").clear()
    return await hs__get_orders(refresh=True)


async def hs__update_order(
    order_id: str = "",
    hs_order_name: str = "",
    hs_total_price: str = "",
    hs_currency_code: str = "",
    hs_fulfillment_status: str = "",
    hs_payment_status: str = "",
    hs_closed_date: str = "",
    hs_source_store: str = "",
) -> types.CallToolResult:
    """Update an existing Order in HubSpot CRM."""
    log.info("hs__update_order", order_id=order_id)
    if not order_id:
        return _error_result("order_id is required.")

    props: dict[str, str] = {}
    if hs_order_name:
        props["hs_order_name"] = hs_order_name
    if hs_total_price:
        props["hs_total_price"] = hs_total_price
    if hs_currency_code:
        props["hs_currency_code"] = hs_currency_code
    if hs_fulfillment_status:
        props["hs_fulfillment_status"] = hs_fulfillment_status
    if hs_payment_status:
        props["hs_payment_status"] = hs_payment_status
    if hs_closed_date:
        props["hs_closed_date"] = hs_closed_date
    if hs_source_store:
        props["hs_source_store"] = hs_source_store

    if not props:
        return _error_result("No fields to update.")

    try:
        client = get_client()
        await client.update_object("orders", order_id, props)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to update order: {exc}")
    except Exception as exc:
        return _error_result(f"Error updating order: {exc}")

    _get_cache("Order").clear()
    return await hs__get_orders(refresh=True)


# ── Products tools ────────────────────────────────────────────────────────────

async def hs__get_products(
    product_id: str = "",
    name: str = "",
    hs_status: str = "",
    hs_product_type: str = "",
    action: str = "",
    refresh: bool = False,
) -> types.CallToolResult:
    """Get products. Branches: id+edit→form, id→list-of-one, filters→filtered, bare→top 10."""
    log.info("hs__get_products", product_id=product_id, action=action,
             name=name, hs_status=hs_status, hs_product_type=hs_product_type, refresh=refresh)

    cfg = _get_schema("Product")

    # Branch 1a — action="create" → blank create form
    if action == "create":
        prefill = {field["name"]: "" for field in cfg["formFields"]}
        if name:
            prefill["name"] = name
        if hs_status:
            prefill["hs_status"] = hs_status
        if hs_product_type:
            prefill["hs_product_type"] = hs_product_type
        return types.CallToolResult(
            content=[TextContent(type="text", text="Opening create form for a new product.")],
            structuredContent={
                "type": "form", "entity": "product", "mode": "create",
                "recordId": "", "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 1b — id + action="edit"/"change" → prefilled edit form
    if product_id and action in ("edit", "change"):
        try:
            client = get_client()
            record = await client.get_object("products", product_id, _get_all_props("Product"))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Product {product_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error looking up product: {exc}")

        prefill = {field["name"]: record.get(field["name"], "") or "" for field in cfg["formFields"]}
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Opening edit form for product: {record.get('name', product_id)}.")],
            structuredContent={
                "type": "form", "entity": "product", "mode": "edit",
                "recordId": record.get("id", product_id), "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 2 — id alone → list-of-one
    if product_id:
        try:
            client = get_client()
            record = await client.get_object("products", product_id, _get_list_props("Product"))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"Product {product_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching product: {exc}")

        items = [record]
        return types.CallToolResult(
            content=[TextContent(type="text", text=_list_summary("product(s)", items))],
            structuredContent={
                "type": "products", "total": len(items), "items": items,
                "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()},
            },
        )

    # Branch 3 — filter-based or bare list
    filter_params = {
        "name": name, "hs_product_type": hs_product_type, "hs_status": hs_status,
    }
    filter_groups = _build_filter_groups("Product", filter_params)

    filter_sig = _filter_signature(filter_params)
    cache_key = f"products:{filter_sig}" if filter_sig else "products"
    if not refresh:
        cached_items, cached_at = _cache_get(cache_key, "Product")
        if cached_items is not None:
            return types.CallToolResult(
                content=[TextContent(type="text", text=_list_summary("product(s)", cached_items, cache_hit=True))],
                structuredContent={
                    "type": "products", "total": len(cached_items), "items": cached_items,
                    "_schema": cfg, "_cache": {"hit": True, "cached_at": cached_at},
                },
            )

    try:
        client = get_client()
        props = _get_list_props("Product")
        items = await client.search_objects("products", props, filter_groups=filter_groups, limit=10)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch products: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching products: {exc}")

    cached_at = _cache_set(cache_key, "Product", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=_list_summary("product(s)", items))],
        structuredContent={
            "type": "products", "total": len(items), "items": items,
            "_schema": cfg, "_cache": {"hit": False, "cached_at": cached_at},
        },
    )


async def hs__create_product(
    name: str,
    hs_sku: str = "",
    price: str = "",
    hs_status: str = "",
    hs_product_type: str = "",
    recurringbillingfrequency: str = "",
    hs_recurring_billing_period: str = "",
    description: str = "",
) -> types.CallToolResult:
    """Create a new Product in HubSpot CRM. Requires name. Returns updated list."""
    log.info("hs__create_product", name=name, hs_sku=hs_sku, price=price,
             hs_status=hs_status, hs_product_type=hs_product_type)

    props: dict[str, Any] = {"name": name}
    if hs_sku:
        props["hs_sku"] = hs_sku
    if price:
        props["price"] = price
    if hs_status:
        props["hs_status"] = hs_status
    if hs_product_type:
        props["hs_product_type"] = hs_product_type
    if recurringbillingfrequency:
        props["recurringbillingfrequency"] = recurringbillingfrequency
    if hs_recurring_billing_period:
        props["hs_recurring_billing_period"] = hs_recurring_billing_period
    if description:
        props["description"] = description

    try:
        client = get_client()
        new_id = await client.create_object("products", props)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to create product: {exc}")
    except Exception as exc:
        return _error_result(f"Unexpected error creating product: {exc}")

    # Refresh list
    try:
        items = await client.search_objects("products", _get_list_props("Product"), limit=10)
    except Exception:
        items = []

    cfg = _get_schema("Product")
    _cache_set("products", "Product", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Product '{name}' created (Id: {new_id}).")],
        structuredContent={
            "type": "products", "total": len(items), "items": items,
            "_schema": cfg, "_createdId": new_id,
            "_cache": {"hit": False, "cached_at": _now_iso()},
        },
    )


async def hs__update_product(
    product_id: str,
    name: str = "",
    hs_sku: str = "",
    price: str = "",
    hs_status: str = "",
    hs_product_type: str = "",
    recurringbillingfrequency: str = "",
    hs_recurring_billing_period: str = "",
    description: str = "",
) -> types.CallToolResult:
    """Update an existing Product by id. Only provided fields are updated."""
    log.info("hs__update_product", product_id=product_id, name=name)

    if not product_id:
        return _error_result("product_id is required.")

    props: dict[str, Any] = {}
    if name:
        props["name"] = name
    if hs_sku:
        props["hs_sku"] = hs_sku
    if price:
        props["price"] = price
    if hs_status:
        props["hs_status"] = hs_status
    if hs_product_type:
        props["hs_product_type"] = hs_product_type
    if recurringbillingfrequency:
        props["recurringbillingfrequency"] = recurringbillingfrequency
    if hs_recurring_billing_period:
        props["hs_recurring_billing_period"] = hs_recurring_billing_period
    if description:
        props["description"] = description

    if not props:
        return _error_result("No fields provided to update.")

    try:
        client = get_client()
        await client.update_object("products", product_id, props)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to update product: {exc}")
    except Exception as exc:
        return _error_result(f"Unexpected error updating product: {exc}")

    # Refresh list
    try:
        items = await client.search_objects("products", _get_list_props("Product"), limit=10)
    except Exception:
        items = []

    cfg = _get_schema("Product")
    _cache_set("products", "Product", items)
    return types.CallToolResult(
        content=[TextContent(type="text", text=f"Product {product_id} updated.")],
        structuredContent={
            "type": "products", "total": len(items), "items": items,
            "_schema": cfg, "_updatedId": product_id,
            "_cache": {"hit": False, "cached_at": _now_iso()},
        },
    )


# ── Activities tools ──────────────────────────────────────────────────────────

_ACTIVITY_SCHEMAS: dict[str, dict] = {
    "note": {
        "objectType": "notes",
        "columns": [
            {"apiName": "hs_note_body", "label": "Body"},
            {"apiName": "hs_timestamp", "label": "Date"},
        ],
        "hiddenColumns": [],
        "filterFields": {},
        "formFields": [
            {"name": "hs_note_body", "label": "Note Body", "multiline": True, "required": True},
        ],
    },
    "call": {
        "objectType": "calls",
        "columns": [
            {"apiName": "hs_call_body", "label": "Notes"},
            {"apiName": "hs_call_direction", "label": "Direction"},
            {"apiName": "hs_call_status", "label": "Status"},
            {"apiName": "hs_timestamp", "label": "Date"},
        ],
        "hiddenColumns": [
            {"apiName": "hs_call_duration", "label": "Duration (s)"},
        ],
        "filterFields": {
            "hs_call_direction": {"operator": "EQ", "property": "hs_call_direction"},
            "hs_call_status": {"operator": "EQ", "property": "hs_call_status"},
        },
        "formFields": [
            {"name": "hs_call_body", "label": "Call Notes", "multiline": True},
            {"name": "hs_call_direction", "label": "Direction", "required": True, "picklist": ["INBOUND", "OUTBOUND"]},
            {"name": "hs_call_status", "label": "Outcome", "picklist": ["COMPLETED", "BUSY", "NO_ANSWER", "FAILED", "CONNECTING", "CALLING_CRM_USER"]},
        ],
    },
    "task": {
        "objectType": "tasks",
        "columns": [
            {"apiName": "hs_task_subject", "label": "Subject"},
            {"apiName": "hs_task_status", "label": "Status"},
            {"apiName": "hs_task_priority", "label": "Priority"},
            {"apiName": "hs_timestamp", "label": "Due Date"},
        ],
        "hiddenColumns": [
            {"apiName": "hs_task_body", "label": "Body"},
        ],
        "filterFields": {
            "hs_task_status": {"operator": "EQ", "property": "hs_task_status"},
            "hs_task_priority": {"operator": "EQ", "property": "hs_task_priority"},
            "hs_task_subject": {"operator": "CONTAINS_TOKEN", "property": "hs_task_subject"},
        },
        "formFields": [
            {"name": "hs_task_subject", "label": "Subject", "required": True},
            {"name": "hs_task_body", "label": "Details", "multiline": True},
            {"name": "hs_task_status", "label": "Status", "picklist": ["NOT_STARTED", "IN_PROGRESS", "WAITING", "COMPLETED", "DEFERRED"]},
            {"name": "hs_task_priority", "label": "Priority", "picklist": ["HIGH", "MEDIUM", "LOW", "NONE"]},
            {"name": "hs_timestamp", "label": "Due Date (ISO datetime)"},
        ],
    },
    "meeting": {
        "objectType": "meetings",
        "columns": [
            {"apiName": "hs_meeting_title", "label": "Title"},
            {"apiName": "hs_meeting_outcome", "label": "Outcome"},
            {"apiName": "hs_meeting_start_time", "label": "Start"},
            {"apiName": "hs_meeting_end_time", "label": "End"},
        ],
        "hiddenColumns": [
            {"apiName": "hs_meeting_body", "label": "Description"},
        ],
        "filterFields": {
            "hs_meeting_outcome": {"operator": "EQ", "property": "hs_meeting_outcome"},
        },
        "formFields": [
            {"name": "hs_meeting_title", "label": "Title", "required": True},
            {"name": "hs_meeting_body", "label": "Description", "multiline": True},
            {"name": "hs_meeting_start_time", "label": "Start Time (ISO)"},
            {"name": "hs_meeting_end_time", "label": "End Time (ISO)"},
            {"name": "hs_meeting_outcome", "label": "Outcome", "picklist": ["SCHEDULED", "COMPLETED", "RESCHEDULED", "NO_SHOW", "CANCELLED"]},
        ],
    },
    "email": {
        "objectType": "emails",
        "columns": [
            {"apiName": "hs_email_subject", "label": "Subject"},
            {"apiName": "hs_email_status", "label": "Status"},
            {"apiName": "hs_email_direction", "label": "Direction"},
            {"apiName": "hs_timestamp", "label": "Date"},
        ],
        "hiddenColumns": [
            {"apiName": "hs_email_text", "label": "Body"},
        ],
        "filterFields": {
            "hs_email_status": {"operator": "EQ", "property": "hs_email_status"},
            "hs_email_direction": {"operator": "EQ", "property": "hs_email_direction"},
        },
        "formFields": [
            {"name": "hs_email_subject", "label": "Subject", "required": True},
            {"name": "hs_email_text", "label": "Body", "multiline": True},
            {"name": "hs_email_direction", "label": "Direction", "picklist": ["EMAIL", "INCOMING_EMAIL", "FORWARDED_EMAIL"]},
            {"name": "hs_email_status", "label": "Status", "picklist": ["SEND", "SENDING", "SENT", "FAILED", "BOUNCED"]},
        ],
    },
}

_ACTIVITY_ASSOC_IDS: dict[tuple[str, str], int] = {
    ("notes", "companies"): 190,    ("notes", "contacts"): 202,    ("notes", "deals"): 214,
    ("calls", "companies"): 182,    ("calls", "contacts"): 194,    ("calls", "deals"): 206,
    ("tasks", "companies"): 192,    ("tasks", "contacts"): 204,    ("tasks", "deals"): 216,
    ("meetings", "companies"): 188, ("meetings", "contacts"): 200, ("meetings", "deals"): 212,
    ("emails", "companies"): 186,   ("emails", "contacts"): 198,   ("emails", "deals"): 210,
}

_VALID_ACTIVITY_TYPES = {"note", "call", "task", "meeting", "email"}
_VALID_ENTITY_TYPES = {"company", "contact", "deal"}

_ENTITY_RESOLVER: dict[str, tuple] = {
    "company": ("companies", _resolve_company, _company_not_found_alert),
    "contact": ("contacts", _resolve_contact, _contact_not_found_alert),
    "deal": ("deals", _resolve_deal, _deal_not_found_alert),
}


def _activity_list_props(activity_type: str) -> list[str]:
    """Get property names for list view of an activity type."""
    cfg = _ACTIVITY_SCHEMAS[activity_type]
    return [c["apiName"] for c in cfg["columns"] + cfg.get("hiddenColumns", [])]


async def hs__get_activities(
    activity_type: str = "",
    activity_id: str = "",
    entity_type: str = "",
    entity_name: str = "",
    action: str = "",
    refresh: bool = False,
    # Call fields
    hs_call_direction: str = "",
    hs_call_status: str = "",
    # Task fields
    hs_task_subject: str = "",
    hs_task_status: str = "",
    hs_task_priority: str = "",
    # Meeting fields
    hs_meeting_outcome: str = "",
    # Email fields
    hs_email_status: str = "",
    hs_email_direction: str = "",
) -> types.CallToolResult:
    """Get activities (note/call/task/meeting/email). Requires activity_type.
    Branches: action=create→form, id+edit→form, id→single, entity_name→filtered, bare→top 10."""
    log.info("hs__get_activities", activity_type=activity_type, activity_id=activity_id,
             entity_type=entity_type, entity_name=entity_name, action=action, refresh=refresh)

    # Collect all filter kwargs into a dict
    kwargs: dict[str, str] = {}
    for k, v in [("hs_call_direction", hs_call_direction), ("hs_call_status", hs_call_status),
                 ("hs_task_subject", hs_task_subject), ("hs_task_status", hs_task_status),
                 ("hs_task_priority", hs_task_priority), ("hs_meeting_outcome", hs_meeting_outcome),
                 ("hs_email_status", hs_email_status), ("hs_email_direction", hs_email_direction)]:
        if v:
            kwargs[k] = v

    if not activity_type or activity_type not in _VALID_ACTIVITY_TYPES:
        return _error_result(f"activity_type is required. Must be one of: {sorted(_VALID_ACTIVITY_TYPES)}.")

    cfg = _ACTIVITY_SCHEMAS[activity_type]
    obj_type = cfg["objectType"]

    # Branch 1a — action="create" → form (entity_type + entity_name for FK)
    if action == "create":
        prefill = {field["name"]: "" for field in cfg["formFields"]}
        # Pass through any kwargs that match form field names
        for field in cfg["formFields"]:
            if field["name"] in kwargs and kwargs[field["name"]]:
                prefill[field["name"]] = kwargs[field["name"]]
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Opening create form for a new {activity_type}.")],
            structuredContent={
                "type": "activity_form", "activity_type": activity_type,
                "entity_type": entity_type or "", "entity_name": entity_name or "",
                "mode": "create", "recordId": "", "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 1b — id + action="edit" → prefilled edit form
    if activity_id and action in ("edit", "change"):
        try:
            client = get_client()
            record = await client.get_object(obj_type, activity_id, _activity_list_props(activity_type))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"{activity_type} {activity_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error looking up {activity_type}: {exc}")

        prefill = {field["name"]: record.get(field["name"], "") or "" for field in cfg["formFields"]}
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"Opening edit form for {activity_type} {activity_id}.")],
            structuredContent={
                "type": "activity_form", "activity_type": activity_type,
                "entity_type": "", "entity_name": "",
                "mode": "edit", "recordId": activity_id, "prefill": prefill,
                "_schema": cfg,
            },
        )

    # Branch 2 — id alone → single record view
    if activity_id:
        try:
            client = get_client()
            record = await client.get_object(obj_type, activity_id, _activity_list_props(activity_type))
        except HubSpotAuthError as exc:
            return _error_result(f"HubSpot authentication failed: {exc}")
        except HubSpotAPIError as exc:
            return _error_result(f"{activity_type} {activity_id} not found: {exc}")
        except Exception as exc:
            return _error_result(f"Error fetching {activity_type}: {exc}")

        items = [record]
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"1 {activity_type}(s).")],
            structuredContent={
                "type": "activities", "activity_type": activity_type,
                "total": 1, "items": items,
                "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()},
            },
        )

    # Branch 3 — entity_name filter (resolve FK → get associations → batch read)
    if entity_name and entity_type:
        if entity_type not in _VALID_ENTITY_TYPES:
            return _error_result(f"entity_type must be one of: {sorted(_VALID_ENTITY_TYPES)}.")
        plural, resolver, alert_fn = _ENTITY_RESOLVER[entity_type]
        try:
            client = get_client()
            entity_id, suggestions = await resolver(client, entity_name)
        except Exception as exc:
            return _error_result(f"Error resolving {entity_type}: {exc}")
        if not entity_id:
            return alert_fn(entity_name, suggestions)

        # Get associated activity IDs
        try:
            assoc_ids = await client.get_associated_ids(plural, entity_id, obj_type)
            if assoc_ids:
                records = await client.batch_read(obj_type, assoc_ids[:10], _activity_list_props(activity_type))
            else:
                records = []
        except Exception as exc:
            return _error_result(f"Error fetching {activity_type}s for {entity_type}: {exc}")

        items = [{"id": r.get("id", ""), **r} for r in records]
        return types.CallToolResult(
            content=[TextContent(type="text", text=f"{len(items)} {activity_type}(s) for {entity_name}.")],
            structuredContent={
                "type": "activities", "activity_type": activity_type,
                "total": len(items), "items": items,
                "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()},
            },
        )

    # Branch 4 — filter-based or bare search
    filter_params = {k: v for k, v in kwargs.items() if v and k in cfg.get("filterFields", {})}
    filter_defs = cfg.get("filterFields", {})
    filters = []
    for param_name, value in filter_params.items():
        fdef = filter_defs.get(param_name)
        if fdef:
            filters.append({"propertyName": fdef["property"], "operator": fdef["operator"], "value": value})
    filter_groups = [{"filters": filters}] if filters else None

    try:
        client = get_client()
        props = _activity_list_props(activity_type)
        items = await client.search_objects(obj_type, props, filter_groups=filter_groups, limit=10)
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to fetch {activity_type}s: {exc}")
    except Exception as exc:
        return _error_result(f"Error fetching {activity_type}s: {exc}")

    return types.CallToolResult(
        content=[TextContent(type="text", text=f"{len(items)} {activity_type}(s).")],
        structuredContent={
            "type": "activities", "activity_type": activity_type,
            "total": len(items), "items": items,
            "_schema": cfg, "_cache": {"hit": False, "cached_at": _now_iso()},
        },
    )


async def hs__create_activity(
    activity_type: str,
    entity_type: str = "",
    entity_name: str = "",
    # Note fields
    hs_note_body: str = "",
    # Call fields
    hs_call_body: str = "",
    hs_call_direction: str = "",
    hs_call_status: str = "",
    # Task fields
    hs_task_subject: str = "",
    hs_task_body: str = "",
    hs_task_status: str = "",
    hs_task_priority: str = "",
    # Meeting fields
    hs_meeting_title: str = "",
    hs_meeting_body: str = "",
    hs_meeting_start_time: str = "",
    hs_meeting_end_time: str = "",
    hs_meeting_outcome: str = "",
    # Email fields
    hs_email_subject: str = "",
    hs_email_text: str = "",
    hs_email_direction: str = "",
    hs_email_status: str = "",
) -> types.CallToolResult:
    """Create an activity (note/call/task/meeting/email) and associate it with an entity."""
    log.info("hs__create_activity", activity_type=activity_type,
             entity_type=entity_type, entity_name=entity_name)

    if not activity_type or activity_type not in _VALID_ACTIVITY_TYPES:
        return _error_result(f"activity_type is required. Must be one of: {sorted(_VALID_ACTIVITY_TYPES)}.")

    # Collect all field values into kwargs dict
    kwargs: dict[str, str] = {}
    for k, v in [("hs_note_body", hs_note_body), ("hs_call_body", hs_call_body),
                 ("hs_call_direction", hs_call_direction), ("hs_call_status", hs_call_status),
                 ("hs_task_subject", hs_task_subject), ("hs_task_body", hs_task_body),
                 ("hs_task_status", hs_task_status), ("hs_task_priority", hs_task_priority),
                 ("hs_meeting_title", hs_meeting_title), ("hs_meeting_body", hs_meeting_body),
                 ("hs_meeting_start_time", hs_meeting_start_time), ("hs_meeting_end_time", hs_meeting_end_time),
                 ("hs_meeting_outcome", hs_meeting_outcome), ("hs_email_subject", hs_email_subject),
                 ("hs_email_text", hs_email_text), ("hs_email_direction", hs_email_direction),
                 ("hs_email_status", hs_email_status)]:
        if v:
            kwargs[k] = v

    cfg = _ACTIVITY_SCHEMAS[activity_type]
    obj_type = cfg["objectType"]

    # Build properties from kwargs matching form fields
    props: dict[str, Any] = {}
    for field in cfg["formFields"]:
        val = kwargs.get(field["name"], "")
        if val:
            props[field["name"]] = val

    # Ensure required fields
    required_fields = [f["name"] for f in cfg["formFields"] if f.get("required")]
    for rf in required_fields:
        if not props.get(rf):
            return _error_result(f"'{rf}' is required for {activity_type}.")

    # Auto-set timestamp
    props["hs_timestamp"] = _now_iso()

    # Resolve FK entity for association
    associations: list[dict] = []
    if entity_name and entity_type:
        if entity_type not in _VALID_ENTITY_TYPES:
            return _error_result(f"entity_type must be one of: {sorted(_VALID_ENTITY_TYPES)}.")
        plural, resolver, alert_fn = _ENTITY_RESOLVER[entity_type]
        try:
            client = get_client()
            entity_id, suggestions = await resolver(client, entity_name)
        except Exception as exc:
            return _error_result(f"Error resolving {entity_type}: {exc}")
        if not entity_id:
            return alert_fn(entity_name, suggestions)

        assoc_type_id = _ACTIVITY_ASSOC_IDS.get((obj_type, plural))
        if assoc_type_id:
            associations.append({
                "to": {"id": entity_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": assoc_type_id}],
            })

    # Create the activity
    try:
        client = get_client()
        body: dict[str, Any] = {"properties": props}
        if associations:
            body["associations"] = associations
        # Use raw _request since create_object doesn't support associations
        resp = await client._request("POST", f"/crm/v3/objects/{obj_type}", json_body=body)
        client._raise_for_error(resp, f"create {obj_type}")
        new_id = resp.json()["id"]
    except HubSpotAuthError as exc:
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        return _error_result(f"Failed to create {activity_type}: {exc}")
    except Exception as exc:
        return _error_result(f"Unexpected error creating {activity_type}: {exc}")

    # Refresh list
    try:
        items = await client.search_objects(obj_type, _activity_list_props(activity_type), limit=10)
    except Exception:
        items = []

    return types.CallToolResult(
        content=[TextContent(type="text", text=f"{activity_type.title()} created (Id: {new_id}).")],
        structuredContent={
            "type": "activities", "activity_type": activity_type,
            "total": len(items), "items": items,
            "_schema": cfg, "_createdId": new_id,
            "_cache": {"hit": False, "cached_at": _now_iso()},
        },
    )


async def hs__update_activity(
    activity_type: str,
    activity_id: str,
    # Note fields
    hs_note_body: str = "",
    # Call fields
    hs_call_body: str = "",
    hs_call_direction: str = "",
    hs_call_status: str = "",
    # Task fields
    hs_task_subject: str = "",
    hs_task_body: str = "",
    hs_task_status: str = "",
    hs_task_priority: str = "",
    # Meeting fields
    hs_meeting_title: str = "",
    hs_meeting_body: str = "",
    hs_meeting_start_time: str = "",
    hs_meeting_end_time: str = "",
    hs_meeting_outcome: str = "",
    # Email fields
    hs_email_subject: str = "",
    hs_email_text: str = "",
    hs_email_direction: str = "",
    hs_email_status: str = "",
) -> types.CallToolResult:
    """Update an existing activity by id. Only provided fields are updated."""
    log.info("hs__update_activity", activity_type=activity_type, activity_id=activity_id)

    if not activity_type or activity_type not in _VALID_ACTIVITY_TYPES:
        return _error_result(f"activity_type is required. Must be one of: {sorted(_VALID_ACTIVITY_TYPES)}.")
    if not activity_id:
        return _error_result("activity_id is required.")

    cfg = _ACTIVITY_SCHEMAS[activity_type]
    obj_type = cfg["objectType"]

    # Collect all field values into kwargs dict
    kwargs: dict[str, str] = {}
    for k, v in [("hs_note_body", hs_note_body), ("hs_call_body", hs_call_body),
                 ("hs_call_direction", hs_call_direction), ("hs_call_status", hs_call_status),
                 ("hs_task_subject", hs_task_subject), ("hs_task_body", hs_task_body),
                 ("hs_task_status", hs_task_status), ("hs_task_priority", hs_task_priority),
                 ("hs_meeting_title", hs_meeting_title), ("hs_meeting_body", hs_meeting_body),
                 ("hs_meeting_start_time", hs_meeting_start_time), ("hs_meeting_end_time", hs_meeting_end_time),
                 ("hs_meeting_outcome", hs_meeting_outcome), ("hs_email_subject", hs_email_subject),
                 ("hs_email_text", hs_email_text), ("hs_email_direction", hs_email_direction),
                 ("hs_email_status", hs_email_status)]:
        if v:
            kwargs[k] = v

    # Build properties from kwargs matching form fields
    props: dict[str, Any] = {}
    valid_fields = {f["name"] for f in cfg["formFields"]}
    for k, v in kwargs.items():
        if k in valid_fields and v:
            props[k] = v

    if not props:
        return _error_result("No fields provided to update.")

    log.info("hs__update_activity sending props", props=props)

    try:
        client = get_client()
        await client.update_object(obj_type, activity_id, props)
    except HubSpotAuthError as exc:
        log.error("Auth error updating activity", activity_type=activity_type, activity_id=activity_id, error=str(exc))
        return _error_result(f"HubSpot authentication failed: {exc}")
    except HubSpotAPIError as exc:
        log.error("API error updating activity", activity_type=activity_type, activity_id=activity_id, error=str(exc))
        return _error_result(f"Failed to update {activity_type}: {exc}")
    except Exception as exc:
        log.error("Unexpected error updating activity", activity_type=activity_type, activity_id=activity_id, error=str(exc))
        return _error_result(f"Error updating {activity_type}: {exc}")

    # Refresh list
    try:
        items = await client.search_objects(obj_type, _activity_list_props(activity_type), limit=10)
    except Exception:
        items = []

    return types.CallToolResult(
        content=[TextContent(type="text", text=f"{activity_type.title()} {activity_id} updated.")],
        structuredContent={
            "type": "activities", "activity_type": activity_type,
            "total": len(items), "items": items,
            "_schema": cfg, "_updatedId": activity_id,
            "_cache": {"hit": False, "cached_at": _now_iso()},
        },
    )


# ── Tool specs (registered by server) ────────────────────────────────────────

TOOL_SPECS: list[dict] = [
    {
        "name": "hs__get_companies",
        "description": (
            "Get companies from HubSpot CRM (10 most recent). "
            "Pass company_id to view one record; add action='edit' to open the edit form. "
            "Filters: name (text search), domain (text search), "
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
        "name": "hs__get_associations",
        "description": (
            "Get records associated to an entity in HubSpot CRM. "
            "Required: entity_type (companies or contacts), entity_id, "
            "association_type (contacts, deals, tickets, or companies). "
            "Returns fields relevant to the target type."
        ),
        "handler": hs__get_associations,
    },
    {
        "name": "hs__get_contacts",
        "description": (
            "Get contacts from HubSpot CRM (10 most recent). "
            "Pass contact_id to view one record; add action='edit' to open the edit form; "
            "action='create' to open a blank create form. "
            "Filters: firstname, lastname, email, jobtitle, city, "
            "company_name (FK — searches all associations), "
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
    {
        "name": "hs__get_deals",
        "description": (
            "Get deals from HubSpot CRM (10 most recent). "
            "Pass deal_id to view one record; add action='edit' to open the edit form; "
            "action='create' to open a blank create form. "
            "Filters: dealname (text search), dealstage (stage ID or closedwon/closedlost), "
            "pipeline (default), dealtype (newbusiness/existingbusiness), "
            "company_name (FK — finds deals associated to that company)."
        ),
        "handler": hs__get_deals,
    },
    {
        "name": "hs__create_deal",
        "description": (
            "Create a new Deal in HubSpot CRM. Required: dealname, dealstage, pipeline. "
            "Optional: amount, closedate (ISO date), dealtype (newbusiness/existingbusiness), "
            "description, company_name (associates to matching company), "
            "contact_name (associates to matching contact)."
        ),
        "handler": hs__create_deal,
    },
    {
        "name": "hs__update_deal",
        "description": (
            "Update an existing Deal in HubSpot CRM by its record Id. "
            "Only fields provided will be updated. "
            "Fields: dealname, amount, pipeline, dealstage, closedate, dealtype, description."
        ),
        "handler": hs__update_deal,
    },
    {
        "name": "hs__get_orders",
        "description": (
            "Get orders from HubSpot CRM (10 most recent). "
            "Pass order_id to view one record; add action='edit' to open the edit form; "
            "action='create' to open a blank create form. "
            "Filters: hs_order_name (text search), hs_fulfillment_status, hs_payment_status, "
            "hs_currency_code, company_name (FK), contact_name (FK), deal_name (FK)."
        ),
        "handler": hs__get_orders,
    },
    {
        "name": "hs__create_order",
        "description": (
            "Create a new Order in HubSpot CRM. Required: hs_order_name. "
            "Optional: hs_total_price, hs_currency_code, hs_fulfillment_status, "
            "hs_payment_status, hs_closed_date (ISO date), hs_source_store, "
            "company_name (associates to company), contact_name (associates to contact), "
            "deal_name (associates to deal)."
        ),
        "handler": hs__create_order,
    },
    {
        "name": "hs__update_order",
        "description": (
            "Update an existing Order in HubSpot CRM by its record Id. "
            "Only fields provided will be updated. "
            "Fields: hs_order_name, hs_total_price, hs_currency_code, "
            "hs_fulfillment_status, hs_payment_status, hs_closed_date, hs_source_store."
        ),
        "handler": hs__update_order,
    },
    {
        "name": "hs__get_products",
        "description": (
            "Get products from HubSpot CRM (10 most recent). "
            "Pass product_id to view one record; add action='edit' to open the edit form; "
            "action='create' to open a blank create form. "
            "Filters: name (text search), hs_product_type (inventory/non_inventory/service), "
            "hs_status (active/inactive)."
        ),
        "handler": hs__get_products,
    },
    {
        "name": "hs__create_product",
        "description": (
            "Create a new Product in HubSpot CRM. Required: name. "
            "Optional: hs_sku, price, hs_status (active/inactive), "
            "hs_product_type (inventory/non_inventory/service), "
            "recurringbillingfrequency (weekly/biweekly/monthly/quarterly/per_six_months/"
            "annually/per_two_years/per_three_years/per_four_years/per_five_years), "
            "hs_recurring_billing_period (term), description."
        ),
        "handler": hs__create_product,
    },
    {
        "name": "hs__update_product",
        "description": (
            "Update an existing Product in HubSpot CRM by its record Id. "
            "Only fields provided will be updated. "
            "Fields: name, hs_sku, price, hs_status, hs_product_type, "
            "recurringbillingfrequency, hs_recurring_billing_period, description."
        ),
        "handler": hs__update_product,
    },
    {
        "name": "hs__get_activities",
        "description": (
            "Get activities from HubSpot CRM. REQUIRED: activity_type (note/call/task/meeting/email). "
            "Pass activity_id to view one; add action='edit' to open edit form; action='create' for new. "
            "Filter by entity: entity_type (company/contact/deal) + entity_name. "
            "Filter by fields: call(hs_call_direction, hs_call_status), "
            "task(hs_task_subject, hs_task_status, hs_task_priority), "
            "meeting(hs_meeting_outcome), email(hs_email_status, hs_email_direction)."
        ),
        "handler": hs__get_activities,
    },
    {
        "name": "hs__create_activity",
        "description": (
            "Create an activity in HubSpot CRM. REQUIRED: activity_type (note/call/task/meeting/email). "
            "Optional: entity_type (company/contact/deal) + entity_name to associate. "
            "Note fields: hs_note_body. Call: hs_call_body, hs_call_direction, hs_call_status. "
            "Task: hs_task_subject, hs_task_body, hs_task_status, hs_task_priority. "
            "Meeting: hs_meeting_title, hs_meeting_body, hs_meeting_start_time, hs_meeting_end_time, hs_meeting_outcome. "
            "Email: hs_email_subject, hs_email_text, hs_email_direction, hs_email_status."
        ),
        "handler": hs__create_activity,
    },
    {
        "name": "hs__update_activity",
        "description": (
            "Update an existing activity in HubSpot CRM. REQUIRED: activity_type + activity_id. "
            "Only provided fields are updated. Fields depend on activity_type."
        ),
        "handler": hs__update_activity,
    },
]


# ── Prompt specs ──────────────────────────────────────────────────────────────

PROMPT_SPECS: list[dict] = []
