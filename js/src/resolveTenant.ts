import { Pool } from "pg";

export type ResolvedTenant = { tenantId: string; status: string };

export type PublicSchoolConfig = Record<string, unknown> & {
  tenantId: string;
  slug: string;
};

/** Each server process keeps a domain for this long, then reads the database again. */
export const TENANT_CACHE_MS = 60 * 60 * 1000;

type CacheEntry = { at: number; tenant: ResolvedTenant | null };

let pool: Pool | undefined;
const cache = new Map<string, CacheEntry>();

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
  const now = Date.now();
  const cached = cache.get(domain);
  if (cached && now - cached.at < TENANT_CACHE_MS) return cached.tenant;
  const tenant = await lookupDomain(domain);
  cache.set(domain, { at: now, tenant });
  return tenant;
}

export async function publicSchoolConfig(tenantId: string): Promise<PublicSchoolConfig | null> {
  const result = await getPool().query(
    `SELECT tenant_id::text AS "tenantId", slug, config
     FROM platform.tenants
     WHERE tenant_id = $1::uuid`,
    [tenantId],
  );
  const row = result.rows[0];
  if (!row) return null;
  const config = { ...(row.config ?? {}) } as Record<string, unknown>;
  delete config.database_secret;
  delete config.databaseSecret;
  return { ...config, tenantId: row.tenantId, slug: row.slug };
}
