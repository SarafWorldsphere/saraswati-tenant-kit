const LOGO_KEY = "images/logo.jpeg";

export function schoolLogo(tenantId: string): string {
  const key = `${tenantId}/${LOGO_KEY}`;
  const origin = process.env.NEXT_PUBLIC_ASSETS_ORIGIN?.replace(/\/$/, "");
  if (origin) return `${origin}/${key}`;
  return `/assets/${key}`;
}
