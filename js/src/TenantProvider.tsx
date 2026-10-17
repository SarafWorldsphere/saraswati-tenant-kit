"use client";

import { createContext, useContext, useLayoutEffect, type ReactNode } from "react";
import { themeName, type SchoolConfig } from "./types";

const SchoolContext = createContext<SchoolConfig | null>(null);

export function TenantProvider({
  config,
  children,
}: {
  config: SchoolConfig;
  children: ReactNode;
}) {
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = themeName(config.theme);
  }, [config.theme]);

  return <SchoolContext.Provider value={config}>{children}</SchoolContext.Provider>;
}

export function useSchool(): SchoolConfig {
  const config = useContext(SchoolContext);
  if (config === null) {
    throw new Error("useSchool must be called inside TenantProvider.");
  }
  return config;
}
