/**
 * Persist the most recently visited run and product so a page refresh can
 * resume. The backend remains the source of truth — these are only pointers,
 * never cached business data, and we deliberately do NOT fabricate a history
 * list (the backend exposes no list endpoint).
 */

const RUN_KEY = "eufy-futurelab.recent-run";
const PRODUCT_KEY = "eufy-futurelab.recent-product";

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

export function rememberRun(runId: string): void {
  safeSet(RUN_KEY, runId);
}

export function getRecentRun(): string | null {
  return safeGet(RUN_KEY);
}

export function rememberProduct(productId: string): void {
  safeSet(PRODUCT_KEY, productId);
}

export function getRecentProduct(): string | null {
  return safeGet(PRODUCT_KEY);
}
