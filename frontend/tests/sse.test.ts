import { describe, expect, it } from "vitest";
import type { AgentEvent } from "../src/types/api";
import {
  latestSequence,
  mergeEvents,
  parseAgentEvent,
} from "../src/lib/api/sse";

function event(sequence: number, message = `event ${sequence}`): AgentEvent {
  return {
    id: sequence,
    run_id: "forecast-1",
    sequence,
    event_type: "agent_started",
    agent: "futures-user_trends",
    message,
    payload: {},
    created_at: "2026-08-13T00:00:00Z",
  };
}

describe("mergeEvents", () => {
  it("de-duplicates by sequence and sorts ascending", () => {
    const existing = [event(1), event(2), event(3)];
    const incoming = [event(2, "updated"), event(4)];
    const merged = mergeEvents(existing, incoming);

    expect(merged.map((item) => item.sequence)).toEqual([1, 2, 3, 4]);
    // later occurrence wins
    expect(merged.find((item) => item.sequence === 2)?.message).toBe("updated");
  });

  it("orders out-of-order incoming events", () => {
    const merged = mergeEvents([], [event(5), event(1), event(3)]);
    expect(merged.map((item) => item.sequence)).toEqual([1, 3, 5]);
  });

  it("ignores duplicates delivered by both replay and SSE", () => {
    const replayed = [event(1), event(2)];
    const streamed = [event(1), event(2), event(3)];
    const merged = mergeEvents(replayed, streamed);
    expect(merged).toHaveLength(3);
  });
});

describe("latestSequence", () => {
  it("returns the highest sequence, or 0 when empty", () => {
    expect(latestSequence([])).toBe(0);
    expect(latestSequence([event(2), event(7), event(4)])).toBe(7);
  });
});

describe("parseAgentEvent", () => {
  it("parses a valid SSE data payload", () => {
    const raw = JSON.stringify(event(9, "hello"));
    const parsed = parseAgentEvent(raw);
    expect(parsed?.sequence).toBe(9);
    expect(parsed?.message).toBe("hello");
  });

  it("returns null for malformed JSON", () => {
    expect(parseAgentEvent("{not json")).toBeNull();
  });

  it("returns null when required fields are missing", () => {
    expect(parseAgentEvent(JSON.stringify({ message: "no sequence" }))).toBeNull();
  });
});
