/**
 * Live activity feed for a forecast run.
 *
 * Strategy (per spec):
 *  1. Replay existing events via the plain `/events` endpoint first.
 *  2. Connect the named-event SSE stream from the last known sequence.
 *  3. De-duplicate + order everything by `sequence`.
 *  4. If SSE drops while the run is still active, fall back to polling
 *     `/events` every 2 seconds until the stream recovers.
 *  5. Close the stream on terminal events and on unmount.
 *
 * The run's *status* is polled separately by `useRun` (React Query), so this
 * hook only owns the fine-grained timeline — never the source of truth.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { AgentEvent } from "../../types/api";
import { getRunEvents } from "../../lib/api/forecastApi";
import {
  latestSequence,
  mergeEvents,
  subscribeRunEvents,
  TERMINAL_EVENT_TYPES,
  type RunEventSubscription,
} from "../../lib/api/sse";

export type ConnectionState = "connecting" | "live" | "reconnecting" | "closed";

export interface UseRunEventsResult {
  events: AgentEvent[];
  connection: ConnectionState;
}

export function useRunEvents(
  runId: string | undefined,
  runFinished: boolean,
): UseRunEventsResult {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const eventsRef = useRef<AgentEvent[]>([]);

  const pushEvents = useCallback((incoming: AgentEvent[]) => {
    setEvents((prev) => {
      const merged = mergeEvents(prev, incoming);
      eventsRef.current = merged;
      return merged;
    });
  }, []);

  useEffect(() => {
    if (!runId) return;

    let disposed = false;
    let sub: RunEventSubscription | null = null;
    let fallbackTimer: number | null = null;

    setEvents([]);
    eventsRef.current = [];
    setConnection("connecting");

    const stopFallback = () => {
      if (fallbackTimer !== null) {
        window.clearInterval(fallbackTimer);
        fallbackTimer = null;
      }
    };

    const startFallback = () => {
      if (fallbackTimer !== null || disposed) return;
      setConnection("reconnecting");
      fallbackTimer = window.setInterval(async () => {
        try {
          const more = await getRunEvents(runId, latestSequence(eventsRef.current));
          if (!disposed && more.length) pushEvents(more);
        } catch {
          /* transient — the run status query surfaces real failures */
        }
      }, 2000);
    };

    void (async () => {
      // 1. Replay historical events so a refresh shows the full timeline.
      try {
        const existing = await getRunEvents(runId, 0);
        if (disposed) return;
        pushEvents(existing);
      } catch {
        /* ignore — useRun drives the primary error UI */
      }
      if (disposed) return;

      // A finished run has a complete, static timeline — no live stream needed.
      if (runFinished) {
        setConnection("closed");
        return;
      }

      // 2. Open the SSE stream from the last known sequence.
      sub = subscribeRunEvents(runId, {
        afterSequence: latestSequence(eventsRef.current),
        onOpen: () => {
          if (disposed) return;
          stopFallback();
          setConnection("live");
        },
        onEvent: (event) => {
          if (disposed) return;
          pushEvents([event]);
          if (TERMINAL_EVENT_TYPES.has(event.event_type)) {
            sub?.close();
            sub = null;
            stopFallback();
            setConnection("closed");
          }
        },
        onError: () => {
          if (disposed) return;
          // EventSource auto-reconnects; polling is the safety net meanwhile.
          startFallback();
        },
      });
    })();

    return () => {
      disposed = true;
      stopFallback();
      sub?.close();
    };
  }, [runId, runFinished, pushEvents]);

  return { events, connection };
}
