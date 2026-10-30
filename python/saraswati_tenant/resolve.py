"""The only place a hostname becomes a school."""

from __future__ import annotations

import os
from collections.abc import Callable
import psycopg
from psycopg.rows import dict_row

from saraswati_tenant.errors import SchoolNotFound, SchoolSuspended
from saraswati_tenant.memory_cache import school_cache
from saraswati_tenant.types import School

Lookup = Callable[[str], School | None]

_lookup: Lookup | None = None

_LOOKUP_SQL = """
SELECT
    t.tenant_id::text AS tenant_id,
    t.slug,
    t.status,
    t.isolation,
    t.config,
    t.database_secret,
    COALESCE((
        SELECT jsonb_object_agg(f.feature_key, f.enabled)
        FROM platform.tenant_features AS f
        WHERE f.tenant_id = t.tenant_id
    ), '{}'::jsonb) AS feature_rows,
    COALESCE((
        SELECT jsonb_object_agg(grouped.locale, grouped.labels)
        FROM (
            SELECT l.locale, jsonb_object_agg(l.label_key, l.value) AS labels
            FROM platform.tenant_labels AS l
            WHERE l.tenant_id = t.tenant_id
            GROUP BY l.locale
        ) AS grouped
    ), '{}'::jsonb) AS label_rows
FROM platform.tenant_domains AS d
JOIN platform.tenants AS t ON t.tenant_id = d.tenant_id
WHERE d.domain = %s
"""


def set_school_lookup(lookup: Lookup | None) -> None:
    """Tests and local fakes pass a function. Production leaves this unset."""
    global _lookup
    _lookup = lookup
    school_cache.clear()


def normalize_host(host: str) -> str:
    value = (host or "").strip().lower()
    if not value or "://" in value or "/" in value or " " in value:
        raise SchoolNotFound(host)
    if value.startswith("[") and "]" in value:
        value = value[1 : value.index("]")]
    elif value.count(":") == 1:
        value = value.split(":", 1)[0]
    value = value.rstrip(".")
    if value.startswith("www.") and value.count(".") >= 2:
        value = value[4:]
    if not value or "." not in value and value != "localhost":
        raise SchoolNotFound(host)
    return value


def resolve_school(host: str) -> School:
    normalized = normalize_host(host)
    cached = school_cache.get(normalized)
    if isinstance(cached, School):
        school = cached
    else:
        school = _find(normalized)
        if school is None and normalized != host.strip().lower():
            school = _find(host.strip().lower().split(":")[0].rstrip("."))
        if school is None:
            raise SchoolNotFound(normalized)
        school_cache.put(normalized, school)
    if school.status != "active":
        raise SchoolSuspended(normalized)
    if school.isolation not in ("rls", "database"):
        raise SchoolNotFound(normalized)
    return school


def _find(domain: str) -> School | None:
    if _lookup is not None:
        return _lookup(domain)
    return _lookup_database(domain)


def _lookup_database(domain: str) -> School | None:
    dsn = os.environ.get("SARASWATI_CONTROL_DATABASE_URL") or os.environ.get(
        "SARASWATI_DATABASE_URL"
    )
    if not dsn:
        raise RuntimeError(
            "Set SARASWATI_CONTROL_DATABASE_URL or SARASWATI_DATABASE_URL before resolving a school."
        )
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        row = connection.execute(_LOOKUP_SQL, (domain,)).fetchone()
    if row is None:
        return None
    config = row["config"] if isinstance(row["config"], dict) else {}
    return School(
        tenant_id=row["tenant_id"],
        slug=row["slug"],
        status=row["status"],
        isolation=row["isolation"],
        config=config,
        database_secret=row["database_secret"],
        feature_rows=_object(row["feature_rows"]),
        label_rows=_object(row["label_rows"]),
    )


def _object(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def clear_school_cache() -> None:
    school_cache.clear()
