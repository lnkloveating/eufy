export type CollapsibleGroupState = "idle" | "running" | "done" | "failed";

export interface CollapsibleGroupDescriptor {
  key: string;
  state: CollapsibleGroupState;
}

/**
 * Global default for grouped collapsibles:
 * - running: expanded
 * - failed: expanded
 * - done: collapsed
 * - idle: collapsed
 */
export function getDefaultExpandedGroups(
  groups: CollapsibleGroupDescriptor[],
): Record<string, boolean> {
  return Object.fromEntries(
    groups.map((group) => [
      group.key,
      group.state === "running" || group.state === "failed",
    ]),
  );
}
