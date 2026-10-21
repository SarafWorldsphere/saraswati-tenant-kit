from saraswati_tenant import (
    School,
    SchoolNotFound,
    SchoolSuspended,
    s3_path_validator,
    build_key,
    current_school,
    normalize_host,
    resolve_school,
    school_context,
    set_school_lookup,
)
from saraswati_tenant.s3keys import TenantKeyError
from saraswati_tenant.session import apply_rls, bind_rls, _bind_school


def _school(**overrides) -> School:
    body = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "slug": "sss",
        "status": "active",
        "isolation": "rls",
        "config": {"schoolName": "Shiva Satya Sai School", "database_secret": "nope"},
        "database_secret": None,
    }
    body.update(overrides)
    return School(**body)


def test_normalize_host_strips_port_and_www():
    assert normalize_host("WWW.SSS.SWAIS.IN:443") == "sss.swais.in"
    assert normalize_host("localhost") == "localhost"


def test_normalize_host_rejects_urls():
    try:
        normalize_host("https://sss.swais.in")
    except SchoolNotFound:
        return
    raise AssertionError("expected SchoolNotFound")


def test_resolve_uses_the_injected_lookup_only():
    set_school_lookup(lambda domain: _school() if domain == "sss.swais.in" else None)
    try:
        school = resolve_school("sss.swais.in")
        assert school.slug == "sss"
        assert "database_secret" not in school.public_config()
        assert school.public_config()["tenantId"] == school.tenant_id
    finally:
        set_school_lookup(None)


def test_unknown_and_suspended_hosts():
    def lookup(domain: str):
        if domain == "paused.swais.in":
            return _school(status="suspended", slug="paused")
        return None

    set_school_lookup(lookup)
    try:
        try:
            resolve_school("missing.swais.in")
        except SchoolNotFound:
            pass
        else:
            raise AssertionError("expected SchoolNotFound")
        try:
            resolve_school("paused.swais.in")
        except SchoolSuspended:
            pass
        else:
            raise AssertionError("expected SchoolSuspended")
    finally:
        set_school_lookup(None)


def test_build_key_prefixes_the_current_school():
    with school_context(_school()):
        assert build_key("brand", "logo") == (
            "11111111-1111-1111-1111-111111111111/brand/logo"
        )
        assert current_school().slug == "sss"


def test_build_key_rejects_parent_segments():
    try:
        build_key("brand", "../other", tenant_id="11111111-1111-1111-1111-111111111111")
    except TenantKeyError:
        return
    raise AssertionError("expected TenantKeyError")


def test_unprefixed_key_is_rejected():
    tenant = "11111111-1111-1111-1111-111111111111"
    s3_path_validator(f"{tenant}/study-material/class-7/file.pdf", tenant)
    s3_path_validator(f"{tenant}/student-photos/1784796691389-tki6ot.jpeg", tenant)
    for key in (
        "study-material/class-7/file.pdf",
        "assignments/class-18/assignment-117/file.jpeg",
        "student-photos/1784796691389-tki6ot.jpeg",
        "father-1784747197741-images-(1).jpeg",
    ):
        try:
            s3_path_validator(key, tenant)
        except TenantKeyError:
            continue
        raise AssertionError(f"unprefixed key must be rejected: {key}")


class _FakeDb:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_apply_rls_uses_the_bound_school():
    db = _FakeDb()
    with school_context(_school()):
        apply_rls(db)
    sql, params = db.calls[0]
    assert "set_config" in sql
    assert params == ("11111111-1111-1111-1111-111111111111",)


class _FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((str(sql), params))


def test_bind_rls_sets_the_school_for_a_transaction():
    connection = _FakeConnection()
    with school_context(_school()):
        _bind_school(None, None, connection)
    sql, params = connection.calls[0]
    assert "set_config" in sql
    assert params == {"tenant_id": "11111111-1111-1111-1111-111111111111"}


def test_bind_rls_is_quiet_without_a_school():
    connection = _FakeConnection()
    _bind_school(None, None, connection)
    assert connection.calls == []


def test_bind_rls_registers_once():
    from sqlalchemy.orm import sessionmaker

    first = sessionmaker()
    second = sessionmaker()
    bind_rls(first)
    bind_rls(second)
    assert first.class_._saraswati_rls_bound is True
