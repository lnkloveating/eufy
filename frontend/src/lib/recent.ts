/**
 * Persist only the most recently visited run so a page refresh can resume.
 * Product-definition navigation is resolved from the run-scoped backend state.
 */

const RUN_KEY = "eufy-futurelab.recent-run";
const LEGACY_PRODUCT_KEY = "eufy-futurelab.recent-product";

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode / quota) — non-fatal */
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* storage unavailable — non-fatal */
  }
}

export function rememberRun(runId: string): void {
  safeSet(RUN_KEY, runId);
  // Product navigation is now resolved from the run-scoped backend state.
  // Remove the old global pointer so it can never leak across new research runs.
  safeRemove(LEGACY_PRODUCT_KEY);
}

export function getRecentRun(): string | null {
  return safeGet(RUN_KEY);
}

export function forgetRecentRun(): void {
  safeRemove(RUN_KEY);
  safeRemove(LEGACY_PRODUCT_KEY);
}
