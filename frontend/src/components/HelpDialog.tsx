import { useState } from "react";
import type { ReactNode } from "react";
import { Modal } from "./Modal";
import { KeyboardShortcuts } from "./KeyboardShortcuts";
import "../styles/help-guide.css";

export interface HelpDialogProps {
  onClose: () => void;
  keyboardOnly?: boolean;
}

/** Educational screenshots only: never passed to observation/data loaders. */
function GuideFigure({ name, alt, children }: {
  name: "workspace" | "compare" | "spectrum";
  alt: string;
  children: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const id = `help-image-${name}`;
  return (
    <figure className="guide-figure">
      <div className="guide-image-toolbar">
        <span>Numbered screenshot guide</span>
        <button className="btn" type="button" aria-expanded={expanded}
          aria-controls={id} onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Fit image to panel" : `Enlarge ${name} image`}
        </button>
      </div>
      <div id={id} className={`guide-image-scroll${expanded ? " is-expanded" : ""}`}
        role="region" aria-label={`${name} screenshot${expanded ? "; scroll to inspect at full size" : ""}`}
        tabIndex={expanded ? 0 : undefined}
        onKeyDown={(event) => {
          if (!expanded || event.target !== event.currentTarget || event.altKey ||
              event.ctrlKey || event.metaKey || event.shiftKey) return;
          const step = 64;
          const offsets: Record<string, [number, number]> = {
            ArrowLeft: [-step, 0], ArrowRight: [step, 0],
            ArrowUp: [0, -step], ArrowDown: [0, step],
          };
          const offset = offsets[event.key];
          if (!offset) return;
          // Native keyboard scroll may animate despite reduced-motion. Keep
          // this educational-image interaction immediate and local to its region.
          event.preventDefault();
          event.stopPropagation();
          event.currentTarget.scrollLeft += offset[0];
          event.currentTarget.scrollTop += offset[1];
        }}>
        <img src={`/help/guide-${name}.png`} alt={alt} loading="lazy" decoding="async" />
      </div>
      {expanded && <p className="guide-image-hint">Swipe to explore the full-size image. With the image region focused, use the arrow keys to scroll. The numbered explanations are below.</p>}
      <figcaption><ol className="guide-callouts">{children}</ol></figcaption>
    </figure>
  );
}

export function HelpDialog({ onClose, keyboardOnly = false }: HelpDialogProps) {
  return (
    <Modal onClose={onClose} labelledBy="help-title" className="modal-panel--help">
      <header className="drawer-head guide-header">
        <div>
          <p className="drawer-kicker">SkyBlink field guide</p>
          <h2 id="help-title">{keyboardOnly ? "Keyboard shortcuts" : "Your first look at the infrared sky"}</h2>
        </div>
        <button className="btn" onClick={onClose}>Close Help</button>
      </header>
      <div className="help-body visual-guide">
        {keyboardOnly ? <KeyboardShortcuts /> : (
          <>
            <div className="guide-intro">
              <p>SkyBlink shows real NASA SPHEREx images of the same patch of sky at different times. Start with two dates, then check what the data can support.</p>
              <ol className="guide-start">
                <li><strong>Choose a target</strong><span>Search → WISE 0855</span></li>
                <li><strong>Compare two dates</strong><span>Compare → Show A / Show B</span></li>
                <li><strong>Check the result</strong><span>Spectrum and Evidence</span></li>
              </ol>
              <p className="guide-recording-note">These screenshots show real results recorded earlier, not a new archive request. Your dates, bands and sample counts may differ. Reduced motion was enabled for these captures, so Play is disabled. Source labels and warnings are part of the result.</p>
            </div>

            <section className="guide-step" aria-labelledby="help-step-one">
              <p className="guide-step-label">01 / Get oriented</p>
              <h3 id="help-step-one">Choose a field and a data source</h3>
              <p>Open <strong>Search sky or choose a target</strong>, then choose a catalog target such as WISE 0855. A “field” is the patch of sky around that position. The image starts paused.</p>
              <GuideFigure name="workspace" alt="Recorded WISE 0855 workspace. Markers locate Search, task navigation, Data source and Inspector; each is explained below.">
                <li><strong>Search.</strong> Choose a named target or enter sky coordinates.</li>
                <li><strong>Tasks.</strong> Observe shows the image; Compare chooses dates; Spectrum opens brightness samples; Evidence explains their origin and limits.</li>
                <li><strong>Data source.</strong> Check which route supplied the observations. The three choices below do different things.</li>
                <li><strong>Inspector.</strong> Read comparison and measurement status here. A real image is not automatically a reliable measurement.</li>
              </GuideFigure>
              <dl className="guide-source-list">
                <div><dt>Online archive — fresh search</dt><dd>Searches current coverage and downloads images. This is the default. If discovery fails, the app reports an error.</dd></div>
                <div><dt>Known exposures — fresh downloads</dt><dd>For catalog targets only. Downloads real files from a previously verified list; it does not search for newer coverage. Choose it explicitly when archive search is unavailable.</dd></div>
                <div><dt>Saved catalog data</dt><dd>Opens historical real observations already stored with the app. Their comparisons remain unvalidated. This is an explicit choice, never an automatic fallback.</dd></div>
              </dl>
              <p className="guide-tip">Panels stack on a small screen. If a panel is hidden, use <strong>Show fields</strong> or <strong>Show inspector</strong> beside the viewer.</p>
            </section>

            <section className="guide-step" aria-labelledby="help-step-two">
              <p className="guide-step-label">02 / Compare</p>
              <h3 id="help-step-two">Look at the same field on two dates</h3>
              <p>Open <strong>Compare</strong>. Choose observations A and B, select an available detector band, then press <strong>Show A</strong> and <strong>Show B</strong>. Use <strong>Side by side</strong> to keep both visible without blinking.</p>
              <GuideFigure name="compare" alt="Recorded WISE 0855 comparison. Markers locate A/B controls, the D6 band selection, observation dates and CAUTION warning, and comparison availability.">
                <li><strong>A and B.</strong> Choose two observations in the left panel; the buttons choose how to view them.</li>
                <li><strong>Image band.</strong> D6 is detector 6. Only available bands can be selected. A band is a wavelength range, not another date.</li>
                <li><strong>Dates and warnings.</strong> Read the dates and CAUTION label above the image. This recorded D6 pair is 5 May 2025 and 11 May 2026; a new request may return a different pair.</li>
                <li><strong>Comparison status.</strong> Open Comparison details for limitations or retry options. A matched pair permits visual comparison; it does not prove a moving or variable object.</li>
              </GuideFigure>
              <div className="guide-caution">
                <strong>Dark does not mean “nothing is there.”</strong>
                <p>Black patches can be masked pixels, missing coverage, or low displayed intensity. Pixel blocks become obvious when zoomed in. Do not identify a dark patch or a flickering spot as an object without separate evidence.</p>
              </div>
              <p>One returned observation cannot support a time comparison. Image sharpness, wavelength sampling, background, artifacts and blended sources can all change appearances.</p>
            </section>

            <section className="guide-step" aria-labelledby="help-step-three">
              <p className="guide-step-label">03 / Understand the measurements</p>
              <h3 id="help-step-three">Fetched samples are not all usable measurements</h3>
              <p>Open <strong>Spectrum</strong>: brightness at different infrared wavelengths (colors). Start with the sample count, then inspect the table and the reasons for any excluded sample.</p>
              <GuideFigure name="spectrum" alt="Recorded R Draconis spectrum with three fetched samples and zero eligible measurements. Markers identify the count, unavailable-measurement explanation, table, and expanded exclusion reasons.">
                <li><strong>Fetched / eligible.</strong> “Fetched 3 samples; 0 recorded eligible” means data arrived, but none passed the recorded measurement checks.</li>
                <li><strong>Unavailable values.</strong> No flux plot is drawn here because all brightness values are unavailable. This is a completed response, not a broken chart.</li>
                <li><strong>Table.</strong> The dashes mark unavailable flux; Used is “no.” Unavailable is not zero brightness, proof of absence, or a calibrated upper limit.</li>
                <li><strong>Reasons.</strong> Open Measurement rules and per-observation reasons. The aperture is the small measurement area around the chosen position. These samples have no clean pixels there, and their center is hard-bad (flagged unusable). Both D3 samples also lack a supported background estimate.</li>
              </GuideFigure>
              <p>Keep <strong>All epochs</strong> and <strong>All recorded samples</strong> when investigating missing measurements. Use a row’s <strong>Inspect</strong> button for its details. Finite but excluded values are exploratory; even an eligible measurement does not certify a discovery or brightness change.</p>
              <div className="guide-tip"><strong>Display and measurement are separate.</strong> Colormap, stretch and contrast change how the picture looks. They do not change the native brightness measurements. “Thermal” combines available bands 5 and 6; it is not a temperature reading.</div>
            </section>

            <section className="guide-more" aria-labelledby="help-more">
              <h3 id="help-more">When you need more</h3>
              <details>
                <summary>A request failed, or a comparison is missing</summary>
                <p>Fresh archive discovery is currently unreliable. For a named target, explicitly choose Known exposures — fresh downloads or use Fetch known exposures online when offered. Downloads can still fail, and a downloaded pair must still pass comparison checks. Arbitrary coordinates require working fresh discovery.</p>
                <p>If only Spectrum fails, Fetch known spectrum online retries that part using the verified list. It leaves the image mode unchanged; source labels show the separate choice. A retrieval failure differs from a successful response with zero eligible samples.</p>
                <p>Archive requests can take about two minutes. Cancel stops browser waiting; shared server work may continue. A single returned epoch or incomplete search does not prove that no other observations exist.</p>
              </details>
              <details>
                <summary>Move around the image and use the keyboard</summary>
                <p>Use Zoom in, Zoom out and Reset view. Drag with a mouse to pan; Control plus wheel zooms. Touch scrolls normally. Focus image expands the existing viewer; Exit focus restores the panels.</p>
                <KeyboardShortcuts />
                <p>Blinking can be uncomfortable or photosensitive. Manual steps and side-by-side avoid automatic flashing. Reduced motion disables playback. The 8 FPS cap is not a flash-safety certification.</p>
              </details>
              <details>
                <summary>Read differences, flags and measurement limits</summary>
                <p>Difference shows B minus A only when the recorded difference exists. With the cool-warm palette, blue is negative, neutral is zero and red is positive. Historical saved differences remain unvalidated.</p>
                <p>Current native measurements require a clean aperture and center, supported background, and enough clean surrounding pixels. Saved products use their recorded rules. Negative fluxes and approximate errors remain visible; molecular guide lines are reference positions, not detections.</p>
                <p>Cursor intensity may use normalized display data and different contributing bands; read its label. A zero flag value at a dark pixel does not establish that it is clean. Gaia pins are catalog annotations, not SPHEREx detections. Trial motion and parallax controls are assumptions for exploration.</p>
              </details>
              <details>
                <summary>Search coordinates, share a view and inspect its source</summary>
                <p>Search accepts decimal ICRS degrees or sexagesimal coordinates. Arbitrary positions stay as entered; named archive targets use corrected positions propagated to epoch 2025.8. Saved products retain their historical positions.</p>
                <p>Copy view link saves source, query and view settings and opens paused. It may request a new result; it does not replay pinned image bytes. Recent queries stay in this browser and can be cleared.</p>
                <p>Evidence separates data origin, comparison status, measurement availability and validation scope. Reports and source records explain inputs and processing. Replaying arithmetic does not validate an astrophysical interpretation.</p>
              </details>
            </section>
          </>
        )}
      </div>
    </Modal>
  );
}
