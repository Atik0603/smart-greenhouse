// Phase 11 stub. Phase 12 replaces this body with the dashboard WebSocket,
// which subscribes to the backend's EventBus (e.g. AlertCreated) and calls onEvent.

export type RealtimeEvent = { type: string; payload: unknown };

export function subscribeRealtime(_onEvent: (event: RealtimeEvent) => void): () => void {
  // No live connection yet: nothing will ever call _onEvent.
  return () => {};
}