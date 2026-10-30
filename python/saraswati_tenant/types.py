from dataclasses import dataclass
from typing import Any

from saraswati_tenant.catalog import resolve_catalog


@dataclass(frozen=True)
class School:
    tenant_id: str
    slug: str
    status: str
    isolation: str
    config: dict[str, Any]
    database_secret: str | None = None
    feature_rows: dict[str, Any] | None = None
    label_rows: dict[str, Any] | None = None

    def public_config(self) -> dict[str, Any]:
        """Branding JSON for the browser. Never includes the database secret.

        features, languages, and labels are resolved here and replace any copy
        of those keys that a school put in config.
        """
        body = dict(self.config)
        body["tenantId"] = self.tenant_id
        body["slug"] = self.slug
        body.pop("database_secret", None)
        body.pop("databaseSecret", None)
        resolved = resolve_catalog(self.config, self.feature_rows, self.label_rows)
        body["features"] = resolved["features"]
        body["languages"] = resolved["languages"]
        body["labels"] = resolved["labels"]
        body.pop("pages", None)
        return body
