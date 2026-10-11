import { useEffect, useState } from "react";
import { api, type CacheMeta } from "./api";

export function useCaches() {
  const [caches, setCaches] = useState<CacheMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.caches().then((r) => setCaches(r.caches)).catch((e: Error) => setError(e.message));
  }, []);
  return { caches, error };
}
