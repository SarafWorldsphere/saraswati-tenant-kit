export type MemoryCache<T> = {
  get(key: string): T | undefined;
  put(key: string, value: T): T;
  clear(): void;
};

/** Same process cache the domain lookup uses. A miss is `undefined`, so do not store `undefined`. */
export function createMemoryCache<T>(ttlMs: number): MemoryCache<T> {
  const entries = new Map<string, { at: number; value: T }>();
  return {
    get(key) {
      const hit = entries.get(key);
      if (!hit) return undefined;
      if (Date.now() - hit.at >= ttlMs) {
        entries.delete(key);
        return undefined;
      }
      return hit.value;
    },
    put(key, value) {
      entries.set(key, { at: Date.now(), value });
      return value;
    },
    clear() {
      entries.clear();
    },
  };
}
