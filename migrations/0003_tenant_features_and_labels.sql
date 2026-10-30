-- Features and module-name overrides. src/10_platform.sql creates these on a
-- fresh database. This file creates them when that file was applied earlier.
-- The app role can read them and cannot insert.

CREATE TABLE IF NOT EXISTS platform.tenant_features (
    tenant_id   uuid NOT NULL REFERENCES platform.tenants (tenant_id),
    feature_key text NOT NULL,
    enabled     boolean NOT NULL,
    PRIMARY KEY (tenant_id, feature_key),
    CONSTRAINT tenant_features_key_format CHECK (feature_key ~ '^[a-z][a-z0-9_]{0,63}$')
);

CREATE TABLE IF NOT EXISTS platform.tenant_labels (
    tenant_id   uuid NOT NULL REFERENCES platform.tenants (tenant_id),
    label_key   text NOT NULL,
    locale      text NOT NULL,
    value       text NOT NULL,
    PRIMARY KEY (tenant_id, label_key, locale),
    CONSTRAINT tenant_labels_key_not_blank CHECK (label_key <> ''),
    CONSTRAINT tenant_labels_locale_check CHECK (
        locale IN ('en', 'hi', 'te', 'ta', 'kn', 'ml', 'mr', 'gu', 'bn', 'or')
    )
);

GRANT SELECT ON platform.tenant_features TO saraswati_app;
GRANT SELECT ON platform.tenant_labels TO saraswati_app;
