import { Pool } from "pg";
import { createMemoryCache } from "./memoryCache";
import { resolveFeatures, resolveLabels, resolveLanguages } from "./schoolCatalog";
import type { SchoolLanguages } from "./types";

export type ResolvedTenant = { tenantId: string; status: string };

export type PublicSchoolConfig = Record<string, unknown> & {
  tenantId: string;
  slug: string;
  features: Record<string, boolean>;
  languages: SchoolLanguages;
  labels: Record<string, Record<string, string>>;
};

/** Each server process keeps a domain for this long, then reads the database again. */
export const TENANT_CACHE_MS = 60 * 60 * 1000;

let pool: Pool | undefined;
const domainCache = createMemoryCache<ResolvedTenant | null>(TENANT_CACHE_MS);
const configCache = createMemoryCache<PublicSchoolConfig | null>(TENANT_CACHE_MS);

function getPool(): Pool {
  if (!pool) {
    const connectionString = process.env.SARASWATI_DATABASE_URL;
    if (!connectionString) throw new Error("SARASWATI_DATABASE_URL is not set.");
    pool = new Pool({ connectionString });
  }
  return pool;
}

function domainOf(host: string): string | null {
  const domain = host.trim().toLowerCase().replace(/\.$/, "").split(":")[0];
  if (!domain || domain.includes("/")) return null;
  return domain;
}

async function lookupDomain(domain: string): Promise<ResolvedTenant | null> {
  const result = await getPool().query(
    `SELECT t.tenant_id::text AS "tenantId", t.status
     FROM platform.tenant_domains AS d
     JOIN platform.tenants AS t ON t.tenant_id = d.tenant_id
     WHERE d.domain = $1`,
    [domain],
  );
  return result.rows[0] ?? null;
}

export async function resolveTenant(host: string): Promise<ResolvedTenant | null> {
  const domain = domainOf(host);
  if (!domain) return null;
  const cached = domainCache.get(domain);
  if (cached !== undefined) return cached;
  const tenant = await lookupDomain(domain);
  return domainCache.put(domain, tenant);
}

export async function publicSchoolConfig(tenantId: string): Promise<PublicSchoolConfig | null> {
  const cached = configCache.get(tenantId);
  if (cached !== undefined) return cached;
  const result = await getPool().query(
    `SELECT
        t.tenant_id::text AS "tenantId",
        t.slug,
        t.config,
        COALESCE((
            SELECT jsonb_object_agg(f.feature_key, f.enabled)
            FROM platform.tenant_features AS f
            WHERE f.tenant_id = t.tenant_id
        ), '{}'::jsonb) AS features,
        COALESCE((
            SELECT jsonb_object_agg(grouped.locale, grouped.labels)
            FROM (
                SELECT l.locale, jsonb_object_agg(l.label_key, l.value) AS labels
                FROM platform.tenant_labels AS l
                WHERE l.tenant_id = t.tenant_id
                GROUP BY l.locale
            ) AS grouped
        ), '{}'::jsonb) AS labels
     FROM platform.tenants AS t
     WHERE t.tenant_id = $1::uuid`,
    [tenantId],
  );
  const row = result.rows[0];
  if (!row) return configCache.put(tenantId, null);
  const config = { ...(row.config ?? {}) } as Record<string, unknown>;
  delete config.database_secret;
  delete config.databaseSecret;
  const languages = resolveLanguages(config);
  return configCache.put(tenantId, {
    ...config,
    tenantId: row.tenantId,
    slug: row.slug,
    features: resolveFeatures(row.features),
    languages,
    labels: resolveLabels(languages.enabled, row.labels),
  });
}
