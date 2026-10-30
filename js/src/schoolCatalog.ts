import catalog from "../../python/saraswati_tenant/catalog/catalog.json";
import type { SchoolLanguages } from "./types";

type LanguageEntry = { code: string; name: string };
type FeatureEntry = { defaultEnabled: boolean };

const languages = catalog.languages as LanguageEntry[];
const features = catalog.features as Record<string, FeatureEntry>;
const labelDefaults = catalog.labels as Record<string, Record<string, string>>;

const LANGUAGE_NAMES: Record<string, string> = Object.fromEntries(
  languages.map((language) => [language.code, language.name]),
);
const LANGUAGE_CODES = languages.map((language) => language.code);

export function resolveFeatures(rows: unknown): Record<string, boolean> {
  const overrides = isRecord(rows) ? rows : {};
  const resolved: Record<string, boolean> = {};
  for (const [key, spec] of Object.entries(features)) {
    const value = overrides[key];
    resolved[key] = typeof value === "boolean" ? value : spec.defaultEnabled;
  }
  return resolved;
}

export function resolveLanguages(config: unknown): SchoolLanguages {
  const body = isRecord(config) ? config : {};
  const requested = body.defaultLanguage;
  const fallback = typeof requested === "string" && requested in LANGUAGE_NAMES ? requested : "en";

  const raw = body.enabledLanguages;
  const enabled: string[] = [];
  if (!Array.isArray(raw)) {
    enabled.push(...LANGUAGE_CODES);
  } else {
    for (const code of raw) {
      if (typeof code === "string" && code in LANGUAGE_NAMES && !enabled.includes(code)) {
        enabled.push(code);
      }
    }
  }
  if (!enabled.includes(fallback)) enabled.unshift(fallback);

  const names: Record<string, string> = {};
  for (const code of enabled) names[code] = LANGUAGE_NAMES[code];
  return { default: fallback, enabled, names };
}

export function resolveLabels(
  enabled: string[],
  rows: unknown,
): Record<string, Record<string, string>> {
  const overrides = isRecord(rows) ? rows : {};
  const resolved: Record<string, Record<string, string>> = {};
  for (const locale of enabled) {
    if (!(locale in LANGUAGE_NAMES)) continue;
    const localeRows = isRecord(overrides[locale]) ? overrides[locale] : {};
    const labels: Record<string, string> = {};
    for (const [key, translations] of Object.entries(labelDefaults)) {
      const replacement = localeRows[key];
      labels[key] =
        typeof replacement === "string" ? replacement : translations[locale] ?? translations.en;
    }
    resolved[locale] = labels;
  }
  return resolved;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
