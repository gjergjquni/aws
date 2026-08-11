import { useCallback, useEffect, useState } from "react";
import { investigationsApi } from "@/services/investigationsApi";
import type { Investigation, InvestigationFilters } from "@/types";

export function useInvestigations(filters?: InvestigationFilters) {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = filters
        ? await investigationsApi.filter(filters)
        : await investigationsApi.getAll();
      setInvestigations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load investigations");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  return { investigations, loading, error, reload: load };
}

export function useInvestigation(id: string | undefined) {
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!id) {
      setInvestigation(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await investigationsApi.getById(id);
      setInvestigation(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load investigation");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { investigation, loading, error, reload };
}
