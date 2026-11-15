/**
 * RA/Dec parsing for the coordinate-search dialog.
 *
 * Accepted forms (the field decides the unit of a bare sexagesimal triplet):
 *
 *   decimal degrees        133.79513        -7.24515
 *   sexagesimal units      08h55m10.831s    -7d14m42.53s    -7°14′42.53″
 *   colon separated        08:55:10.831     -07:14:42.53
 *   space separated        08 55 10.831     -7 14 42.53
 *   two-part h m / d m     08 55.18         -7 14.7
 *
 * RA sexagesimal input is hours (24h = 360°); Dec sexagesimal input is degrees.
 * Decimal input is always degrees. Nothing here talks to the network: the
 * parsed values are validated and then handed to the catalog resolver.
 */

export interface CoordinateParse {
  ok: boolean;
  /** Decimal degrees when `ok`; 0 otherwise. */
  degrees: number;
  error: string | null;
}

const DECIMAL_PATTERN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;

function fail(error: string): CoordinateParse {
  return { ok: false, degrees: 0, error };
}

interface Tokenised {
  sign: 1 | -1;
  parts: number[];
}

/**
 * Collapse every supported unit spelling into plain numeric tokens. Unit
 * letters are separators, so `08h55m10.831s` and `08 55 10.831` converge.
 */
function tokenise(raw: string): Tokenised | null {
  let text = raw
    .trim()
    .replace(/[−–—]/g, "-")
    .replace(/[°hHdD]/g, " ")
    .replace(/[mM′']/g, " ")
    .replace(/[sS″"]/g, " ")
    .replace(/:/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return null;

  const rawParts = text.split(" ");
  if (rawParts.length < 1 || rawParts.length > 3) return null;

  let sign: 1 | -1 = 1;
  const first = rawParts[0];
  if (first.startsWith("-")) {
    sign = -1;
    rawParts[0] = first.slice(1);
  } else if (first.startsWith("+")) {
    rawParts[0] = first.slice(1);
  }

  // A decimal must have exactly one token; a sexagesimal 2 or 3.
  for (const part of rawParts) {
    if (!DECIMAL_PATTERN.test(part)) return null;
  }

  return { sign, parts: rawParts.map(Number) };
}

function parseSexagesimal(
  raw: string,
  kind: "ra" | "dec",
  rangeError: string,
): CoordinateParse {
  // Unit letters are unambiguous: Dec never uses hours, and an explicit
  // degree marker in the RA field means the triplet is degrees, not hours.
  if (kind === "dec" && /[hH]/.test(raw)) {
    return fail("Dec sexagesimal is in degrees (d / °), not hours.");
  }
  const explicitDegrees = kind === "ra" && /[dD°]/.test(raw);
  const tokenised = tokenise(raw);
  if (!tokenised) {
    const example =
      kind === "ra" ? "08h55m10.831s" : "−7d14m42.53s";
    return fail(
      `Could not parse ${kind === "ra" ? "RA" : "Dec"} “${raw.trim()}”. ` +
        `Use decimal degrees or sexagesimal (e.g. ${example} or ${kind === "ra" ? "08:55:10.831" : "−07:14:42.53"}).`,
    );
  }

  const { sign, parts } = tokenised;
  if (parts.length > 1) {
    const minutes = parts[1];
    if (!(minutes >= 0 && minutes < 60)) {
      return fail(
        `${kind === "ra" ? "RA" : "Dec"} minutes must be between 0 and 59.999.`,
      );
    }
  }
  if (parts.length > 2) {
    const seconds = parts[2];
    if (!(seconds >= 0 && seconds < 60)) {
      return fail(
        `${kind === "ra" ? "RA" : "Dec"} seconds must be between 0 and 59.999.`,
      );
    }
  }

  // parts[0] + parts[1]/60 + parts[2]/3600; missing parts contribute 0.
  const base = parts.reduce((sum, part, index) => sum + part / 60 ** index, 0);

  if (kind === "ra") {
    if (sign < 0) return fail("RA must be between 0 and 360° (0–24h).");
    let degrees = base * (explicitDegrees ? 1 : 15);
    if (!(degrees >= 0 && degrees <= 360)) return fail(rangeError);
    if (degrees === 360) degrees = 0;
    return { ok: true, degrees, error: null };
  }

  const degrees = sign * base;
  if (!(degrees >= -90 && degrees <= 90)) return fail(rangeError);
  return { ok: true, degrees, error: null };
}

/** Parse the RA field: decimal degrees or hours-based sexagesimal. */
export function parseRa(raw: string): CoordinateParse {
  if (!raw.trim()) {
    return fail("Enter an RA, e.g. 08h55m10.831s or 133.79513°.");
  }
  const trimmed = raw.trim();
  if (!trimmed.includes(" ") && !trimmed.includes(":") && DECIMAL_PATTERN.test(trimmed)) {
    const degrees = Number(trimmed);
    if (!(degrees >= 0 && degrees <= 360)) {
      return fail("RA must be between 0 and 360°.");
    }
    return { ok: true, degrees: degrees === 360 ? 0 : degrees, error: null };
  }
  return parseSexagesimal(trimmed, "ra", "RA must be between 0 and 360°.");
}

/** Parse the Dec field: decimal degrees or degree-based sexagesimal. */
export function parseDec(raw: string): CoordinateParse {
  if (!raw.trim()) {
    return fail("Enter a Dec, e.g. −7d14m42.53s or −7.24515°.");
  }
  const trimmed = raw.trim();
  if (!trimmed.includes(" ") && !trimmed.includes(":") && DECIMAL_PATTERN.test(trimmed)) {
    const degrees = Number(trimmed);
    if (!(degrees >= -90 && degrees <= 90)) {
      return fail("Dec must be between −90 and +90°.");
    }
    return { ok: true, degrees, error: null };
  }
  return parseSexagesimal(trimmed, "dec", "Dec must be between −90 and +90°.");
}
