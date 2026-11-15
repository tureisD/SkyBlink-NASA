export interface ComparisonRecovery {
  title: string;
  explanation: string;
  smallerFieldMayHelp: boolean;
}

/** Exact protocol reasons only. Unknown reasons never imply absent archive coverage. */
export function comparisonRecovery(
  reason: string | null | undefined,
  discoveryStatus?: "complete" | "partial" | "unknown" | null,
  discoveryMode?: "live" | "known" | null,
): ComparisonRecovery {
  if (!reason && discoveryMode === "known") {
    return {
      title: "Known exposure list",
      explanation:
        "One epoch was returned from a previously verified exposure list. No new archive search was performed, and newer observations may exist. Fresh downloads from this list did not establish a temporal comparison.",
      smallerFieldMayHelp: false,
    };
  }
  if (!reason && discoveryStatus === "partial") {
    return {
      title: "Archive search incomplete",
      explanation:
        "Some archive collections were unavailable during this search. One real epoch was returned, but the coverage and latest-epoch inventory are incomplete. This is not a finding that the archive contains only one epoch. Retry the comparison to make a new archive request; a compatible pair is not guaranteed.",
      smallerFieldMayHelp: false,
    };
  }
  switch (reason) {
    case "PARTIAL_DOWNLOAD_NO_MATCHED_PAIR":
      return {
        title: "Some downloads did not complete",
        explanation:
          "Some downloads did not complete, and the completed observations did not establish a compatible pair. Other epochs may exist. Retry the archive comparison; this is not a finding that the archive contains only one epoch.",
        smallerFieldMayHelp: false,
      };
    case "COMPARISON_SEARCH_BUDGET_REACHED":
      return {
        title: "Comparison search reached its time limit",
        explanation:
          "The bounded search returned one real epoch before it could establish a compatible pair. Retry to make a new archive request. More available observations are not ruled out.",
        smallerFieldMayHelp: false,
      };
    case "NO_MATCHED_PAIR_IN_BOUNDED_SAMPLE":
      return {
        title: "No compatible pair in the tested sample",
        explanation:
          "The tested sample did not establish a compatible pair across this field. Matching requires suitable wavelength coverage and usable image support. A smaller field may help, but neither that nor another request guarantees a comparison. The bounded sample is not the entire archive.",
        smallerFieldMayHelp: true,
      };
    default:
      return {
        title: "One epoch is available in this result",
        explanation:
          "You can inspect this observation, but temporal comparison needs two compatible epochs. This result does not establish that the archive contains only one epoch. The specific limitation is unrecorded or not recognized by this client.",
        smallerFieldMayHelp: false,
      };
  }
}
