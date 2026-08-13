/**
 * Presentation helpers for ranked candidates.
 *
 * Critical rule: the frontend must NEVER re-derive or override the backend
 * `rank`. It may only sort a *copy* for display. `orderForDisplay` returns a
 * new array ordered by the backend rank without mutating the input or touching
 * any `rank` value.
 */

import type { RankedCandidate } from "../types/api";

/** Return a display-ordered copy (ascending backend rank). Input untouched. */
export function orderForDisplay(candidates: readonly RankedCandidate[]): RankedCandidate[] {
  return [...candidates].sort((a, b) => a.rank - b.rank);
}

/** The single top-ranked candidate (rank === 1), if present. */
export function topCandidate(
  candidates: readonly RankedCandidate[],
): RankedCandidate | undefined {
  return candidates.find((item) => item.rank === 1);
}

/** Lookup by candidate id. */
export function findCandidate(
  candidates: readonly RankedCandidate[],
  candidateId: string,
): RankedCandidate | undefined {
  return candidates.find((item) => item.candidate.id === candidateId);
}

/**
 * Every candidate — including the lowest-ranked — is selectable. This helper
 * exists so the rule is explicit and unit-tested: selection is never gated on
 * rank.
 */
export function isCandidateSelectable(candidate: RankedCandidate): boolean {
  return Boolean(candidate.candidate.id);
}
