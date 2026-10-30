export const THEME_NAMES = ["indigo-classic", "bright-blue", "plain-card", "saffron"] as const;

export type ThemeName = (typeof THEME_NAMES)[number];

export function themeName(value: unknown): ThemeName {
  return typeof value === "string" && (THEME_NAMES as readonly string[]).includes(value)
    ? (value as ThemeName)
    : "indigo-classic";
}

export type SchoolLanguages = {
  default: string;
  enabled: string[];
  names: Record<string, string>;
};

export type SchoolConfig = {
  tenantId: string;
  slug: string;
  schoolName: string;
  shortName: string;
  place: string;
  logoUrl: string;
  faviconUrl: string;
  theme: string;
  layout: string;
  smsSenderName: string;
  supportEmail: string;
  features: Record<string, boolean>;
  languages: SchoolLanguages;
  labels: Record<string, Record<string, string>>;
};

export const SCHOOL_CSS_VARIABLES = {
  primary: "--school-primary",
  accent: "--school-accent",
  background: "--school-background",
} as const;
