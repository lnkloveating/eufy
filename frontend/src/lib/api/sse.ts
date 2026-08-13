/**
 * Server-Sent Events helpers for the run activity stream.
 *
 * The backend emits *named* SSE events (`event: agent_started`, etc.), so the
 * browser's default `onmessage` handler never fires — we must register a
 * listener per event type. This module owns:
 *   - the list of known event names,
 *   - pure de-duplication / ordering of events by `sequence`,
 *   - a small `subscribeRunEvents` wrapper around `EventSource`.
 *
 * No `Authorization` header is set — the backend requires no auth today.
 */

import type { AgentEvent } from "../../types/api";
import { buildUrl } from "./client";

/** Every named event the backend can emit for a forecast run. */
export const KNOWN_EVENT_TYPES = [
  "run_queued",
  "evidence_selected",
  "artifact_ready",
  "agent_started",
  "agent_completed",
  "consensus_completed",
  "opportunities_created",
  "competitive_analysis_completed",
  "candidates_created",
  "candidate_validation_failed",
  "reviews_completed",
  "run_completed",
  "run_failed",
  "product_definition_started",
  "product_definition_completed",
] as const;

export type KnownEventType = (typeof KNOWN_EVENT_TYPES)[number];

/** Terminal events after which the stream will close on the server side. */
export const TERMINAL_EVENT_TYPES: ReadonlySet<string> = new Set([
  "run_completed",
  "run_failed",
]);

/**
 * Merge incoming events into an existing list, removing duplicates by
 * `sequence` and returning a new array sorted ascending by `sequence`.
 * Later occurrences of the same sequence win (fresher payload).
 */
export function mergeEvents(
  existing: readonly AgentEvent[],
  incoming: readonly AgentEvent[],
): AgentEvent[] {
  const bySequence = new Map<number, AgentEvent>();
  for (const event of existing) {
    bySequence.set(event.sequence, event);
  }
  for (const event of incoming) {
    bySequence.set(event.sequence, event);
  }
  return [...bySequence.values()].sort((a, b) => a.sequence - b.sequence);
}

/** The highest sequence number seen so far (0 if the list is empty). */
export function latestSequence(events: readonly AgentEvent[]): number {
  return events.reduce((max, event) => Math.max(max, event.sequence), 0);
}

/** Safely parse an SSE `data:` payload into an AgentEvent. */
export function parseAgentEvent(raw: string): AgentEvent | null {
  try {
    const parsed = JSON.parse(raw) as Partial<AgentEvent>;
    if (
      parsed &&
      typeof parsed.sequence === "number" &&
      typeof parsed.event_type === "string" &&
      typeof parsed.run_id === "string"
    ) {
      return {
        id: parsed.id ?? null,
        run_id: parsed.run_id,
        sequence: parsed.sequence,
        event_type: parsed.event_type,
        agent: parsed.agent ?? null,
        message: typeof parsed.message === "string" ? parsed.message : "",
        payload: (parsed.payload as Record<string, unknown>) ?? {},
        created_at:
          typeof parsed.created_at === "string"
            ? parsed.created_at
            : new Date().toISOString(),
      };
    }
    return null;
  } catch {
    return null;
  }
}

export interface RunEventSubscription {
  close: () => void;
}

export interface SubscribeOptions {
  afterSequence?: number;
  onEvent: (event: AgentEvent) => void;
  onOpen?: () => void;
  onError?: () => void;
}

/**
 * Open an EventSource for a run and register handlers for every known event
 * type. Returns a handle with a `close()` method; callers must call it on
 * unmount. The EventSource natively reconnects on transient errors.
 */
export function subscribeRunEvents(
  runId: string,
  options: SubscribeOptions,
): RunEventSubscription {
  const after = options.afterSequence ?? 0;
  const url = buildUrl(
    `/forecast-runs/${encodeURIComponent(runId)}/events/stream?after_sequence=${after}`,
  );
  const source = new EventSource(url);

  const handle = (raw: string) => {
    const event = parseAgentEvent(raw);
    if (event) {
      options.onEvent(event);
    }
  };

  for (const type of KNOWN_EVENT_TYPES) {
    source.addEventListener(type, (evt) => handle((evt as MessageEvent).data));
  }
  // Fallback for any unnamed / future events the backend might add.
  source.onmessage = (evt) => handle(evt.data);

  source.onopen = () => options.onOpen?.();
  source.onerror = () => options.onError?.();

  return {
    close: () => source.close(),
  };
}
