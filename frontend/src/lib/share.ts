import type { UrlState } from "../hooks/useUrlState";
import type { SkyResponse } from "./types";

/** A shared query does not pin upstream bytes. Identity differences stay explicit. */
export function analysisIdentityNotice(expected: string | null, actual: string | null | undefined): string | null {
  if (!expected) return null;
  if (!actual) return "This shared view names a recorded analysis, but the loaded product has no analysis fingerprint. Its identity cannot be verified.";
  if (expected !== actual) return "The loaded analysis differs from the shared fingerprint. This archive query retrieved a different result; the original analysis has not been reproduced. Inspect its recorded inputs or explicitly accept this result.";
  return null;
}

/** Validate against actual available assets; never silently choose another pair. */
export function selectionWarnings(state: Pick<UrlState, "bands" | "epoch" | "epochA" | "epochB" | "pair" | "diff">, manifest: SkyResponse): string[] {
  const warnings: string[] = [];
  const selected = [...new Set([state.epoch === "all" ? null : state.epoch, state.epochA, state.epochB].filter((id): id is string => Boolean(id)))];
  for (const id of selected) {
    const epoch = manifest.epochs.find(value => value.epoch_id === id);
    if (!epoch) warnings.push(`Shared observation ${id} is unavailable in this result.`);
    else if (!epoch.frames[state.bands]) warnings.push(`Band ${state.bands} is unavailable in shared observation ${id}.`);
  }
  if (state.pair && !manifest.differences[state.pair]?.[state.bands]) {
    warnings.push(`The shared difference ${state.pair} in band ${state.bands} is unavailable. No substitute comparison reproduces it.`);
  }
  if (state.epochA && state.epochB && state.epochA === state.epochB) warnings.push("Observation A and B are the same; this is not a temporal comparison.");
  if (state.pair && state.epochA && state.epochB && state.pair !== `${state.epochB}_minus_${state.epochA}`) {
    warnings.push("The shared difference direction does not match the selected B minus A observations.");
  }
  if (!manifest.epochs.some(epoch => Boolean(epoch.frames[state.bands]))) warnings.push(`Shared band ${state.bands} has no image in this result.`);
  return warnings;
}
