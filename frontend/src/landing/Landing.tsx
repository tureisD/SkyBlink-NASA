import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, PointerEvent as ReactPointerEvent } from "react";
import { usePrefersReducedMotion } from "../hooks/usePrefersReducedMotion";
import { parseDec, parseRa } from "../lib/coordinates";
import { DEFAULT_TARGET, TARGET_SEEDS } from "../lib/targets";
import { MONO_FAMILY, loadLandingFonts } from "./fonts";
import { createRingScene } from "./ringScene";
import type { SceneInput } from "./ringScene";
import "./landing.css";

/**
 * Landing page shown before the viewer on a fresh visit.
 *
 * Presentation only: it never fetches data. Its single output is the
 * destination the visitor chose, which the caller writes into the URL in the
 * viewer's existing share-link format before mounting the unchanged viewer.
 */

export type LandingDestination =
  | { kind: "default" }
  | { kind: "target"; id: string }
  | { kind: "coordinates"; ra: number; dec: number };

interface LandingProps {
  leaving: boolean;
  onEnter: (destination: LandingDestination) => void;
}

const HOLD_SECONDS = 1.2;
const RELEASE_SECONDS = 0.5;

const COLORS = {
  panel: "#46334F",
  ink: "#F1EFF7",
  highlight: "#F2C230",
  accent: "#F2921D",
};

const TARGET_CARDS: readonly {
  id: string;
  kind: string;
  blurb: string;
  featured?: boolean;
}[] = [
  { id: "barnards_star", kind: "Mover", blurb: "The fastest-moving star in our sky." },
  { id: "eps_indi_b", kind: "Mover", blurb: "A pair of brown dwarfs orbiting a star." },
  {
    id: "wise_0855",
    kind: "Mover",
    blurb: "A fast-moving brown dwarf, one of the coldest known.",
    featured: true,
  },
  { id: "rw_aurigae", kind: "Variable", blurb: "A variable star: watch brightness, not position." },
  { id: "r_draconis", kind: "Variable", blurb: "A pulsating giant that brightens and fades." },
];

const TICKER =
  "REAL NASA SPHEREX DATA  ·  DATA RELEASE 1 + QUICK RELEASE 3  ·  SPACE APPS 2026  ·  ";

function Mark() {
  return (
    <svg className="lp-mark" viewBox="0 0 30 30" role="img" aria-label="SkyBlink">
      <circle cx="15" cy="15" r="13" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle
        cx="15"
        cy="15"
        r="7.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="3 3"
      />
      <circle cx="19" cy="12" r="2.5" fill="#F24F13" />
    </svg>
  );
}

export default function Landing({ leaving, onEnter }: LandingProps) {
  const reducedMotion = usePrefersReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const onEnterRef = useRef(onEnter);
  onEnterRef.current = onEnter;
  const motion = useRef({
    pointerX: 0,
    pointerY: 0,
    dive: 0,
    scroll: 0,
    holding: false,
    committed: false,
    done: false,
    destination: { kind: "default" } as LandingDestination,
  });
  const [diving, setDiving] = useState(false);
  const [ra, setRa] = useState("");
  const [dec, setDec] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Scene lifecycle: build once the embedded fonts are ready.
  useEffect(() => {
    const canvas = canvasRef.current;
    const root = rootRef.current;
    if (!canvas || !root) return undefined;
    let cancelled = false;
    let destroy: (() => void) | null = null;
    let lastDive = -1;

    const frame = (dt: number): SceneInput => {
      const state = motion.current;
      if (!state.done) {
        if (state.committed || state.holding) {
          state.dive = Math.min(1, state.dive + dt / HOLD_SECONDS);
        } else if (state.dive > 0) {
          state.dive = Math.max(0, state.dive - dt / RELEASE_SECONDS);
        }
        if (state.dive >= 1) {
          state.done = true;
          onEnterRef.current(state.destination);
        }
      }
      if (state.dive !== lastDive) {
        lastDive = state.dive;
        root.style.setProperty("--lp-dive", state.dive.toFixed(4));
      }
      const rect = panelRef.current?.getBoundingClientRect();
      return {
        pointerX: state.pointerX,
        pointerY: state.pointerY,
        dive: state.dive,
        scroll: state.scroll,
        rect: rect ? { x: rect.left, y: rect.top, w: rect.width, h: rect.height } : null,
      };
    };

    void loadLandingFonts().then(() => {
      if (cancelled) return;
      destroy = createRingScene(canvas, frame, {
        reducedMotion,
        monoFont: `"${MONO_FAMILY}", ui-monospace, Menlo, Consolas, monospace`,
        ...COLORS,
      }).destroy;
    });
    return () => {
      cancelled = true;
      destroy?.();
    };
  }, [reducedMotion]);

  // Sections rise into place the first time they scroll into view.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    const sections = Array.from(root.querySelectorAll<HTMLElement>(".lp-reveal"));
    if (reducedMotion || typeof IntersectionObserver === "undefined") {
      sections.forEach((section) => section.classList.add("is-in"));
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            observer.unobserve(entry.target);
          }
        }
      },
      { root, threshold: 0.15 },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [reducedMotion]);

  const commit = useCallback(
    (destination: LandingDestination) => {
      const state = motion.current;
      if (state.done || state.committed) return;
      state.destination = destination;
      if (reducedMotion) {
        state.done = true;
        onEnterRef.current(destination);
        return;
      }
      state.committed = true;
      setDiving(true);
    },
    [reducedMotion],
  );

  const scrollToSection = (id: string) => {
    rootRef.current
      ?.querySelector(`#${id}`)
      ?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  };

  const submitCoordinates = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedRa = parseRa(ra);
    const parsedDec = parseDec(dec);
    if (!parsedRa.ok || !parsedDec.ok) {
      setFormError(parsedRa.error ?? parsedDec.error);
      return;
    }
    setFormError(null);
    commit({ kind: "coordinates", ra: parsedRa.degrees, dec: parsedDec.degrees });
  };

  const tiltCard = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (reducedMotion || event.pointerType === "touch") return;
    const card = event.currentTarget;
    const bounds = card.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - 0.5;
    const y = (event.clientY - bounds.top) / bounds.height - 0.5;
    card.style.setProperty("--lp-tilt-x", `${(-y * 14).toFixed(2)}deg`);
    card.style.setProperty("--lp-tilt-y", `${(x * 14).toFixed(2)}deg`);
  };

  const resetCard = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.currentTarget.style.setProperty("--lp-tilt-x", "0deg");
    event.currentTarget.style.setProperty("--lp-tilt-y", "0deg");
  };

  const className = ["lp", diving ? "lp--diving" : "", leaving ? "lp--leaving" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={className}
      ref={rootRef}
      onScroll={(event) => {
        motion.current.scroll = event.currentTarget.scrollTop / window.innerHeight;
      }}
      onPointerMove={(event) => {
        motion.current.pointerX = (event.clientX / window.innerWidth) * 2 - 1;
        motion.current.pointerY = (event.clientY / window.innerHeight) * 2 - 1;
      }}
    >
      <canvas className="lp-scene" ref={canvasRef} aria-hidden="true" />

      <nav className="lp-nav" aria-label="Landing page">
        <div className="lp-nav-row">
          <Mark />
          <button type="button" className="lp-nav-link" onClick={() => scrollToSection("lp-how")}>
            How it works
          </button>
          <button
            type="button"
            className="lp-nav-link"
            onClick={() => scrollToSection("lp-targets")}
          >
            Targets
          </button>
          <button type="button" className="lp-nav-link" onClick={() => scrollToSection("lp-data")}>
            The data
          </button>
          <button
            type="button"
            className="lp-nav-cta"
            onClick={() => commit({ kind: "default" })}
          >
            Open viewer
          </button>
        </div>
        <div className="lp-ticker" aria-hidden="true">
          <div className="lp-ticker-track">
            {TICKER}
            {TICKER}
            {TICKER}
            {TICKER}
          </div>
        </div>
      </nav>

      <header className="lp-hero">
        <div className="lp-hero-copy">
          <p className="lp-kicker">NASA Space Apps 2026. Planet X and SPHEREx.</p>
          <h1 className="lp-title">
            See the sky
            <br />
            <em>change.</em>
          </h1>
          <p className="lp-lede">
            SkyBlink flips between NASA SPHEREx survey passes of the same patch of sky. Pick a
            target or paste coordinates, press play, and check every pixel warning before you
            trust what moved.
          </p>
          <p className="lp-indexed-recovery">
            Indexed archive recovery: <a href="?target=wise_0855&amp;source=archive&amp;discovery=indexed">open WISE 0855 online</a>.
            Fresh downloads from a limited exposure index; other coverage is unknown.
          </p>
          <form className="lp-form" onSubmit={submitCoordinates} noValidate>
            <p className="lp-form-title">Start with a patch of sky.</p>
            <p className="lp-form-note">
              Right ascension and declination, in degrees or sexagesimal. The view lives in the
              URL, so you can share it.
            </p>
            <div className="lp-form-row">
              <label className="lp-field">
                <span>RA</span>
                <input
                  type="text"
                  inputMode="text"
                  autoComplete="off"
                  placeholder="133.795"
                  value={ra}
                  onChange={(event) => setRa(event.target.value)}
                />
              </label>
              <label className="lp-field">
                <span>Dec</span>
                <input
                  type="text"
                  inputMode="text"
                  autoComplete="off"
                  placeholder="-7.245"
                  value={dec}
                  onChange={(event) => setDec(event.target.value)}
                />
              </label>
              <button type="submit" className="lp-submit">
                Blink it
              </button>
            </div>
            <p className="lp-form-error" role="alert">
              {formError}
            </p>
          </form>
        </div>

        <div className="lp-hero-scene" ref={panelRef}>
          <button
            type="button"
            className="lp-hold"
            onPointerDown={(event) => {
              if (event.button !== 0 || reducedMotion) return;
              motion.current.holding = true;
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerUp={() => {
              motion.current.holding = false;
            }}
            onPointerCancel={() => {
              motion.current.holding = false;
            }}
            onContextMenu={(event) => event.preventDefault()}
            onClick={(event) => {
              // Keyboard activation (and reduced motion) cannot hold: run the dive.
              if (event.detail === 0 || reducedMotion) commit({ kind: "default" });
            }}
          >
            {reducedMotion ? "Open the viewer" : "Hold to dive in"}
          </button>
          <p className="lp-scene-caption">
            {DEFAULT_TARGET.name} · RA {DEFAULT_TARGET.ra.toFixed(3)} · Dec{" "}
            {DEFAULT_TARGET.dec.toFixed(3).replace("-", "−")}
          </p>
        </div>
      </header>

      <section id="lp-how" className="lp-section lp-reveal">
        <p className="lp-label">How it works</p>
        <div className="lp-steps">
          <div className="lp-step">
            <span className="lp-step-number">01</span>
            <h2>Choose a field</h2>
            <p>Pick one of the five challenge targets, or paste any coordinates on the sky.</p>
          </div>
          <div className="lp-step">
            <span className="lp-step-number">02</span>
            <h2>Press play</h2>
            <p>
              The viewer flips between survey passes. Still stars stay put. Anything that moves
              or changes brightness stands out.
            </p>
          </div>
          <div className="lp-step">
            <span className="lp-step-number">03</span>
            <h2>Check before you trust</h2>
            <p>
              The Artifact Shield explains pixel warnings, and the spectrum marks every unusable
              value with its reason.
            </p>
          </div>
        </div>
      </section>

      <section id="lp-targets" className="lp-band">
        <div className="lp-section lp-reveal">
          <div className="lp-band-head">
            <h2 className="lp-heading">
              Five targets,
              <br />
              <em>ready to blink.</em>
            </h2>
            <p className="lp-label">The challenge test set</p>
          </div>
          <div className="lp-cards">
            {TARGET_CARDS.map((card) => (
              <button
                type="button"
                key={card.id}
                className={card.featured ? "lp-card lp-card--featured" : "lp-card"}
                onClick={() => commit({ kind: "target", id: card.id })}
                onPointerMove={tiltCard}
                onPointerLeave={resetCard}
              >
                <span className="lp-card-kind">{card.kind}</span>
                <span className="lp-card-body">
                  <span className="lp-card-name">
                    {TARGET_SEEDS[card.id]?.name ?? card.id}
                  </span>
                  <span className="lp-card-blurb">{card.blurb}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section id="lp-data" className="lp-section lp-data lp-reveal">
        <div className="lp-data-copy">
          <p className="lp-label">The data</p>
          <h2 className="lp-heading">
            A visual match is <em>not a discovery.</em>
          </h2>
          <p className="lp-lede">
            Everything on screen is real NASA data. SkyBlink tells you when a comparison works,
            when a measurement is unusable, and why. An unavailable value never means zero
            light.
          </p>
        </div>
        <dl className="lp-facts">
          <div>
            <dt>Source</dt>
            <dd>NASA/IPAC IRSA</dd>
          </div>
          <div>
            <dt>Releases</dt>
            <dd>DR1 + QR3</dd>
          </div>
          <div>
            <dt>Infrared bands</dt>
            <dd>102</dd>
          </div>
          <div>
            <dt>Detector arrays</dt>
            <dd>6</dd>
          </div>
          <div>
            <dt>License</dt>
            <dd>MIT</dd>
          </div>
        </dl>
      </section>

      <footer className="lp-footer">
        <div className="lp-footer-row">
          <span>SkyBlink · Planet X and SPHEREx</span>
          <span>Images: NASA/IPAC IRSA SPHEREx</span>
        </div>
      </footer>
    </div>
  );
}
