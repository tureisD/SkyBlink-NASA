import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import App from "./App";
import type { LandingDestination } from "./landing/Landing";

/**
 * Entry gate: a fresh visit sees the landing page first; the viewer itself is
 * the unchanged <App />.
 *
 * The landing page is skipped whenever the URL already carries viewer state
 * (so every existing share link opens exactly as before) and after the visitor
 * has entered once in this tab. `#intro` forces it to show again.
 */

const Landing = lazy(() => import("./landing/Landing"));

const ENTERED_KEY = "skyblink:entered";
const INTRO_HASH = "#intro";
const FADE_MS = 550;

function hasEntered(): boolean {
  try {
    return window.sessionStorage.getItem(ENTERED_KEY) === "1";
  } catch {
    return false;
  }
}

function rememberEntered(): void {
  try {
    window.sessionStorage.setItem(ENTERED_KEY, "1");
  } catch {
    // Storage can be unavailable (private mode); the landing page then shows
    // again on reload, which is harmless.
  }
}

function shouldShowLanding(): boolean {
  if (typeof window === "undefined") return false;
  if (window.location.hash === INTRO_HASH) return true;
  if (window.location.search.length > 1) return false;
  return !hasEntered();
}

/** Write the chosen destination in the viewer's existing share-link format. */
function applyDestination(destination: LandingDestination): void {
  let search = "";
  if (destination.kind === "target") {
    search = `?target=${encodeURIComponent(destination.id)}`;
  } else if (destination.kind === "coordinates") {
    search = `?ra=${destination.ra.toFixed(5)}&dec=${destination.dec.toFixed(5)}`;
  }
  window.history.replaceState(null, "", `${window.location.pathname}${search}`);
}

type Phase = "landing" | "leaving" | "viewer";

export default function Root() {
  const [phase, setPhase] = useState<Phase>(() =>
    shouldShowLanding() ? "landing" : "viewer",
  );

  const enter = useCallback((destination: LandingDestination) => {
    applyDestination(destination);
    rememberEntered();
    setPhase("leaving");
  }, []);

  useEffect(() => {
    if (phase !== "leaving") return undefined;
    const timer = window.setTimeout(() => setPhase("viewer"), FADE_MS);
    return () => window.clearTimeout(timer);
  }, [phase]);

  return (
    <>
      {phase !== "landing" && <App />}
      {phase !== "viewer" && (
        <Suspense fallback={null}>
          <Landing leaving={phase === "leaving"} onEnter={enter} />
        </Suspense>
      )}
    </>
  );
}
