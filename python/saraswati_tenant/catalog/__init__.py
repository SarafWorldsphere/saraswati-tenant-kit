"""Default features, languages, and module labels. Schools override these in platform."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from saraswati_tenant.memory_cache import school_cache

_CATALOG = json.loads(files("saraswati_tenant.catalog").joinpath("catalog.json").read_text())

LANGUAGE_CODES: tuple[str, ...] = tuple(item["code"] for item in _CATALOG["languages"])
LANGUAGE_NAMES: dict[str, str] = {item["code"]: item["name"] for item in _CATALOG["languages"]}
FEATURE_DEFAULTS: dict[str, bool] = {
    key: bool(spec["defaultEnabled"]) for key, spec in _CATALOG["features"].items()
}
LABEL_DEFAULTS: dict[str, dict[str, str]] = {
    key: {locale: text for locale, text in translations.items() if isinstance(text, str)}
    for key, translations in _CATALOG["labels"].items()
}


def resolve_features(rows: dict[str, Any] | None) -> dict[str, bool]:
    """Catalog default, replaced by a tenant_features row. Unknown keys are dropped."""
    overrides = rows if isinstance(rows, dict) else {}
    resolved: dict[str, bool] = {}
    for key, default in FEATURE_DEFAULTS.items():
        value = overrides.get(key, default)
        resolved[key] = value if isinstance(value, bool) else default
    return resolved


def resolve_languages(config: dict[str, Any] | None) -> dict[str, Any]:
    """Every school is multilingual. A missing list means the whole catalog."""
    body = config if isinstance(config, dict) else {}
    requested = body.get("defaultLanguage")
    default = requested if isinstance(requested, str) and requested in LANGUAGE_NAMES else "en"

    raw = body.get("enabledLanguages")
    if not isinstance(raw, list):
        enabled = list(LANGUAGE_CODES)
    else:
        enabled = []
        for code in raw:
            if isinstance(code, str) and code in LANGUAGE_NAMES and code not in enabled:
                enabled.append(code)
    if default not in enabled:
        enabled.insert(0, default)

    return {
        "default": default,
        "enabled": enabled,
        "names": {code: LANGUAGE_NAMES[code] for code in enabled},
    }


def resolve_labels(
    enabled: list[str],
    rows: dict[str, Any] | None,
) -> dict[str, dict[str, str]]:
    """One map of module labels per enabled language. Other languages are ignored."""
    overrides = rows if isinstance(rows, dict) else {}
    resolved: dict[str, dict[str, str]] = {}
    for locale in enabled:
        if locale not in LANGUAGE_NAMES:
            continue
        locale_rows = overrides.get(locale)
        locale_rows = locale_rows if isinstance(locale_rows, dict) else {}
        labels: dict[str, str] = {}
        for key, translations in LABEL_DEFAULTS.items():
            replacement = locale_rows.get(key)
            if isinstance(replacement, str):
                labels[key] = replacement
            else:
                labels[key] = translations.get(locale) or translations["en"]
        resolved[locale] = labels
    return resolved


def resolve_catalog(
    config: dict[str, Any] | None,
    feature_rows: dict[str, Any] | None,
    label_rows: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolved features, languages, and labels. Same process cache as the domain lookup."""
    body = config if isinstance(config, dict) else {}
    key = "catalog:" + json.dumps(
        {
            "defaultLanguage": body.get("defaultLanguage"),
            "enabledLanguages": body.get("enabledLanguages"),
            "features": feature_rows or {},
            "labels": label_rows or {},
        },
        sort_keys=True,
        default=str,
    )
    cached = school_cache.get(key)
    if isinstance(cached, dict):
        return _copy_resolved(cached)
    languages = resolve_languages(config)
    resolved = {
        "features": resolve_features(feature_rows),
        "languages": languages,
        "labels": resolve_labels(languages["enabled"], label_rows),
    }
    school_cache.put(key, resolved)
    return _copy_resolved(resolved)


def _copy_resolved(resolved: dict[str, Any]) -> dict[str, Any]:
    languages = resolved["languages"]
    return {
        "features": dict(resolved["features"]),
        "languages": {
            "default": languages["default"],
            "enabled": list(languages["enabled"]),
            "names": dict(languages["names"]),
        },
        "labels": {locale: dict(labels) for locale, labels in resolved["labels"].items()},
    }
