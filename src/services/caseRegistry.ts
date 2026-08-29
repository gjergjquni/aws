import { STORAGE_KEYS } from "@/lib/constants";
import type { StoredCase } from "@/types";

// Local registry of cases submitted from this browser. It only records
// real client-observed events (upload/submit timestamps) and the latest
// real backend status — nothing is simulated.

function readAll(): StoredCase[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.liveCases);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as StoredCase[]) : [];
  } catch {
    return [];
  }
}

function writeAll(cases: StoredCase[]): void {
  try {
    localStorage.setItem(STORAGE_KEYS.liveCases, JSON.stringify(cases));
  } catch {
    // Storage full/unavailable — the registry is a convenience cache only.
  }
}

export const caseRegistry = {
  list(): StoredCase[] {
    return readAll().sort((a, b) =>
      (b.submittedAt ?? "").localeCompare(a.submittedAt ?? ""),
    );
  },

  get(caseId: string | undefined): StoredCase | null {
    if (!caseId) return null;
    return readAll().find((c) => c.caseId === caseId) ?? null;
  },

  save(record: StoredCase): void {
    const rest = readAll().filter((c) => c.caseId !== record.caseId);
    writeAll([record, ...rest]);
  },

  update(caseId: string, patch: Partial<StoredCase>): void {
    const all = readAll();
    const index = all.findIndex((c) => c.caseId === caseId);
    if (index === -1) return;
    all[index] = { ...all[index], ...patch };
    writeAll(all);
  },
};
