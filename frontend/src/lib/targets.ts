/**
 * Separate archive and saved catalog positions (AGENTS.md §3.3).
 *
 * Each seed stores both the catalog reference position and the 2025.8
 * position propagated by the backend. `ra`/`dec` are the API query centre
 * (LAW 5); the reference pair is used only by the coordinate resolver and the
 * proper-motion reticle. The manifest remains authoritative: the frontend
 * never invents a target that is not in this table.
 */

export interface TargetSeed {
  id: string;
  name: string;
  /** Compact label for dense controls. */
  shortName: string;
  /** ICRS position propagated to epoch 2025.8 (API query centre). */
  ra: number;
  dec: number;
  /** Catalog reference position from ROADMAP Appendix A. */
  raRef: number;
  decRef: number;
  /** Reference epoch label exactly as published (2010.0 / J2000). */
  refEpoch: string;
}

export const SAVED_TARGET_SEEDS: Record<string, TargetSeed> = {
  wise_0855: {
    id: "wise_0855",
    name: "WISE 0855",
    shortName: "WISE 0855",
    ra: 133.75921,
    dec: -7.24216,
    raRef: 133.79513,
    decRef: -7.24515,
    refEpoch: "2010.0",
  },
  barnards_star: {
    id: "barnards_star",
    name: "Barnard's Star",
    shortName: "Barnard",
    ra: 269.4463,
    dec: 4.7676,
    raRef: 269.4521,
    decRef: 4.6934,
    refEpoch: "J2000",
  },
  eps_indi_b: {
    id: "eps_indi_b",
    name: "Epsilon Indi Ba/Bb",
    shortName: "ε Indi B",
    ra: 331.0962,
    dec: -56.8005,
    raRef: 331.04415,
    decRef: -56.78284,
    refEpoch: "J2000",
  },
  rw_aurigae: {
    id: "rw_aurigae",
    name: "RW Aurigae",
    shortName: "RW Aur",
    ra: 76.9561,
    dec: 30.4011,
    raRef: 76.95607,
    decRef: 30.40133,
    refEpoch: "J2000",
  },
  r_draconis: {
    id: "r_draconis",
    name: "R Draconis",
    shortName: "R Dra",
    ra: 248.1674,
    dec: 66.7548,
    raRef: 248.1676,
    decRef: 66.755,
    refEpoch: "J2000",
  },
};

/** Reviewed corrected solutions; historical saved coordinates remain separate. */
export const TARGET_SEEDS: Record<string, TargetSeed> = {
  wise_0855: { ...SAVED_TARGET_SEEDS.wise_0855, ra: 133.76021647484097, dec: -7.242224282436729, raRef: 133.780984, decRef: -7.243932, refEpoch: "2016.6704644808742" },
  r_draconis: { ...SAVED_TARGET_SEEDS.r_draconis, ra: 248.16723597981732, dec: 66.7550234840942, raRef: 248.1673783672889, decRef: 66.75500674547219, refEpoch: "J2016.0" },
  rw_aurigae: { ...SAVED_TARGET_SEEDS.rw_aurigae, ra: 76.95608953000796, dec: 30.401130005742516, raRef: 76.95608119552952, decRef: 30.401204589097233, refEpoch: "J2016.0" },
  barnards_star: { ...SAVED_TARGET_SEEDS.barnards_star, ra: 269.44631291911435, dec: 4.767629180929986, raRef: 269.44850252543836, decRef: 4.739420051112412, refEpoch: "J2016.0" },
  eps_indi_b: { ...SAVED_TARGET_SEEDS.eps_indi_b, ra: 331.0962496336297, dec: -56.80052585840758, raRef: 331.07645259656397, decRef: -56.79381206688221, refEpoch: "J2016.0" },
};

export function targetSeeds(source: "archive" | "saved"): Record<string, TargetSeed> {
  return source === "saved" ? SAVED_TARGET_SEEDS : TARGET_SEEDS;
}

export const KNOWN_TARGET_IDS: ReadonlySet<string> = new Set(
  Object.keys(TARGET_SEEDS),
);

export const DEFAULT_TARGET: TargetSeed = TARGET_SEEDS.wise_0855;

export function targetSeed(id: string | null | undefined, source: "archive" | "saved" = "archive"): TargetSeed | null {
  if (!id) return null;
  return targetSeeds(source)[id] ?? null;
}

function wrapDeltaDegrees(delta: number): number {
  return ((delta + 540) % 360) - 180;
}

/** Angular separation in arcseconds (haversine; sufficient at this scale). */
export function separationArcsec(
  a: { ra: number; dec: number },
  b: { ra: number; dec: number },
): number {
  const deg2rad = Math.PI / 180;
  const dRa = wrapDeltaDegrees(a.ra - b.ra) * deg2rad;
  const dDec = (a.dec - b.dec) * deg2rad;
  const decA = a.dec * deg2rad;
  const decB = b.dec * deg2rad;
  const h =
    Math.sin(dDec / 2) ** 2 +
    Math.cos(decA) * Math.cos(decB) * Math.sin(dRa / 2) ** 2;
  return (2 * Math.asin(Math.min(1, Math.sqrt(h))) / deg2rad) * 3600;
}

export const ARBITRARY_COORDINATES_NOTICE =
  "Arbitrary coordinates: searching for comparable real epochs. The five benchmark targets also provide saved observations.";
