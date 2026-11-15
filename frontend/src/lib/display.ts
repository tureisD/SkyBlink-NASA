/** Display-only settings (never change flux; LAW 8). */

export type StretchId = "linear" | "log" | "asinh" | "zscale";

export const STRETCHES: ReadonlyArray<{
  id: StretchId;
  label: string;
  description: string;
}> = [
  { id: "linear", label: "Linear", description: "Direct 8-bit display values." },
  { id: "log", label: "Log", description: "Logarithmic boost of faint structure." },
  { id: "asinh", label: "Asinh", description: "Asinh compression that preserves both faint and bright values." },
  {
    id: "zscale",
    label: "Zscale",
    description: "Robust percentile clip computed once per band (p0.5–p99.5) so epochs stay comparable.",
  },
];

export const DEFAULT_COLORMAP = "gray" as const;
export const DEFAULT_STRETCH: StretchId = "linear";
export const DEFAULT_CONTRAST = 1;
export const DEFAULT_BIAS = 0;
