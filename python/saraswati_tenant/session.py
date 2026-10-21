"""Open the database session for the school already bound to this request."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg_pool import ConnectionPool

from saraswati_tenant.context import current_school
from saraswati_tenant.types import School

_pools: dict[str, ConnectionPool] = {}


def apply_rls(db, tenant_id: str | None = None) -> None:
    """Set the transaction-local school id on a psycopg connection or a SQLAlchemy session.

    Call this inside the request transaction. set_config(..., true) does not
    survive commit and does not leak to the next borrower of a pooled connection.
    """
    school_id = tenant_id or current_school().tenant_id
    if hasattr(db, "get_bind"):
        from sqlalchemy import text

        db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": school_id},
        )
        return
    db.execute("SELECT set_config('app.tenant_id', %s, true)", (school_id,))


def bind_rls(session_factory) -> None:
    """Re-apply the school on every transaction this session factory opens.

    Call this once, next to the sessionmaker. set_config(..., true) lasts only
    for the current transaction, so a later commit or rollback clears the
    school. The next query on that pooled connection would otherwise see no
    school. One registration covers that next transaction whether the app
    commits once or many times.

    When no school is bound (startup, migrations, scripts) the listener
    returns. apply_rls() inside get_db() is still the check that fails a
    request whose middleware did not bind a school.
    """
    from sqlalchemy import event
    from sqlalchemy.orm import sessionmaker

    target = (
        session_factory.class_
        if isinstance(session_factory, sessionmaker)
        else session_factory
    )
    if getattr(target, "_saraswati_rls_bound", False):
        return
    event.listen(session_factory, "after_begin", _bind_school)
    target._saraswati_rls_bound = True


def _bind_school(session, transaction, connection) -> None:
    try:
        school = current_school()
    except RuntimeError:
        return
    from sqlalchemy import text

    connection.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": school.tenant_id},
    )


@contextmanager
def open_school_session() -> Iterator:
    """Yield a psycopg connection for the current school.

    isolation 'rls' uses the shared database.
    isolation 'database' uses that school's secret.
    Both set app.tenant_id, because every school database runs the same RLS migration.
    """
    school = current_school()
    if school.isolation == "database":
        pool = _pool_for(school.tenant_id, _database_url(school), max_size=2)
    else:
        pool = _pool_for("shared", _shared_database_url(), max_size=_shared_pool_size())
    with pool.connection() as connection:
        with connection.transaction():
            apply_rls(connection, school.tenant_id)
            yield connection


def _shared_database_url() -> str:
    dsn = os.environ.get("SARASWATI_DATABASE_URL")
    if not dsn:
        raise RuntimeError("SARASWATI_DATABASE_URL is not set.")
    return dsn


def _shared_pool_size() -> int:
    raw = os.environ.get("SARASWATI_POOL_MAX_SIZE", "10")
    return max(1, int(raw))


def _database_url(school: School) -> str:
    if not school.database_secret:
        raise RuntimeError(f"School {school.slug} has no database secret.")
    secrets = os.environ.get("SARASWATI_DATABASE_SECRETS", "")
    # Local and tests map secret name to a URL in this env var:
    # name=postgresql://...;other=postgresql://...
    for item in secrets.split(";"):
        if not item.strip() or "=" not in item:
            continue
        name, url = item.split("=", 1)
        if name.strip() == school.database_secret:
            return url.strip()
    raise RuntimeError(
        f"No URL configured for database secret {school.database_secret}."
    )


def _pool_for(key: str, dsn: str, max_size: int) -> ConnectionPool:
    pool = _pools.get(key)
    if pool is None:
        pool = ConnectionPool(
            dsn,
            min_size=0,
            max_size=max_size,
            open=True,
            kwargs={"autocommit": False},
        )
        _pools[key] = pool
    return pool


def close_pools() -> None:
    for pool in _pools.values():
        pool.close()
    _pools.clear()
