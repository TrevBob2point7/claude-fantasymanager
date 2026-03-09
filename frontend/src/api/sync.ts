import { get } from "./client";
import type { SyncLogEntry } from "./types";
import { getCurrentNflSeason } from "./season";

export interface SyncEvent {
  type: "progress" | "done" | "error";
  message?: string;
  synced?: string[];
  errors?: string[];
}

export async function triggerSync(
  accountId: string,
  onProgress?: (event: SyncEvent) => void,
  seasons?: number[],
): Promise<void> {
  const currentSeason = getCurrentNflSeason();
  const toSync = seasons ?? [currentSeason];

  for (const season of toSync) {
    const token = localStorage.getItem("token");
    const resp = await fetch(`/api/sync/${accountId}?season=${season}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!resp.ok) {
      throw new Error(`Sync failed: ${resp.status}`);
    }

    const reader = resp.body?.getReader();
    if (!reader) throw new Error("Sync response stream not available");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const event = JSON.parse(line.slice(6)) as SyncEvent;
            onProgress?.(event);
          } catch {
            // ignore malformed events
          }
        }
      }
    }
  }
}

export async function triggerLeagueSync(
  leagueId: string,
  onProgress?: (event: SyncEvent) => void,
): Promise<void> {
  const token = localStorage.getItem("token");
  const resp = await fetch(`/api/sync/league/${leagueId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!resp.ok) {
    throw new Error(`Sync failed: ${resp.status}`);
  }

  const reader = resp.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event = JSON.parse(line.slice(6)) as SyncEvent;
          onProgress?.(event);
        } catch {
          // ignore malformed events
        }
      }
    }
  }
}

export function getSyncLog(limit?: number): Promise<SyncLogEntry[]> {
  const query = limit != null ? `?limit=${limit}` : "";
  return get<SyncLogEntry[]>(`/sync/log${query}`);
}
