import { Modal } from "./Modal";
import { KeyboardShortcuts } from "./KeyboardShortcuts";
export interface HelpDialogProps {
  onClose: () => void;
  keyboardOnly?: boolean;
}
export function HelpDialog({ onClose, keyboardOnly = false }: HelpDialogProps) {
  return (
    <Modal
      onClose={onClose}
      labelledBy="help-title"
      className="modal-panel--help"
    >
      <header className="drawer-head">
        <div>
          <p className="drawer-kicker">Using the observing workspace</p>
          <h2 id="help-title">
            {keyboardOnly
              ? "Keyboard shortcuts"
              : "Read the sky, then check the evidence"}
          </h2>
        </div>
        <button className="btn" onClick={onClose}>
          Close Help
        </button>
      </header>
      <div className="help-body">
        {keyboardOnly ? (
          <KeyboardShortcuts />
        ) : (
          <>
            <section>
              <h3>1. Choose a field</h3>
              <p>
                The left sidebar holds the target name, Observe / Compare /
                Spectrum / Evidence navigation, data source and field position.
                Use Search at the top to choose catalog targets, coordinates or
                recent queries. The central viewer holds observations and
                comparison controls; the Inspector separates evidence from
                advanced display tools. Hamburger controls collapse each panel.
                Show fields and Show inspector beside the viewer reopen them. On
                narrow screens panels stack.
              </p>
              <p>
                Search accepts decimal ICRS degrees or sexagesimal coordinates.
                Recent successful queries stay only in this browser; Clear
                history removes them. Reopening an archive field starts a new
                request, never a replay of stored observations. Arbitrary
                coordinates keep the position you enter; their epoch is
                unspecified. Named archive targets use corrected positions
                propagated to epoch 2025.8. Saved mode is an explicit choice of
                historical real observations with the old recorded positions. An
                archive failure never substitutes saved data.
              </p>
              <p>
                If catalog discovery is unavailable, Fetch known exposures
                online is an explicit recovery option. It uses a previously
                verified exposure list and downloads the images afresh; it does
                not search for new coverage. Known exposures remains selected
                across catalog changes and shared links until you choose Online
                archive — fresh search. Coordinate searches always use fresh
                discovery. Recovery can still fail when image downloads are
                unavailable or no pair passes the comparison checks.
              </p>
              <p>
                Archive searches can take about two minutes. Search and Cancel
                remain available. Cancelling stops browser waiting; shared
                server processing may continue.
              </p>
              <p>
                Focus image reclaims the side-panel space while keeping the same
                field, camera and observation selection. Exit focus restores
                your panel choices. Panel visibility and focus layout are local
                to this session; shared links still record the scientific view
                settings.
              </p>
            </section>
            <p>
              If only the spectrum request fails, Fetch known spectrum online is
              a separate, explicit recovery choice. It leaves the image
              unchanged and uses fresh downloads from a limited verified
              exposure list. Shared links, recent fields, audio and spectrum
              exports retain that choice. Changing source, target or coordinates
              restores the spectrum to the image discovery mode. Successfully
              fetched samples can still have zero eligible measurements; inspect
              their recorded reasons.
            </p>
            <section>
              <h3>2. Observe and compare dates</h3>
              <p>
                The view starts paused. Observe shows a dated image. Compare
                lets you choose A and B, inspect each manually, or display them
                side by side. The paired views share the camera, colormap and
                stretch. On narrow screens the pair is stacked. Dates are actual
                observation bounds when recorded; historical dates are labeled
                means. Epoch identifiers are grouping labels, not dates.
              </p>
              <p>
                Available bands combined uses the available contributing
                detectors, not necessarily all six. Thermal is the available
                B5/B6 composite, not a temperature measurement. Black uncovered
                margins are unavailable data. A single returned epoch cannot
                support a temporal comparison; a bounded search does not prove
                that no other archive observations exist.
              </p>
              <p>
                The status beside Comparison details stays visible when a
                comparison is unavailable or the archive search is incomplete.
                Open Comparison details to read the cause and retry options in
                the Inspector, outside the image. Dismiss notification or Escape
                closes those details; the status and reopen button remain
                available.
              </p>
              <p>
                Difference displays B minus A only where a corresponding
                recorded asset exists. Cool-warm uses blue for negative, neutral
                for zero and red for positive residuals. Historical saved
                differences remain unvalidated. Neither visual compatibility nor
                flickering proves motion or variability: wavelength sampling,
                image resolution, background, artifacts and blending can change
                appearances.
              </p>
              <p>
                Black patches can mark masked pixels or missing coverage; low
                display values can also appear dark. Resampling and unsmoothed
                zoom make pixel blocks more visible. A missing display-intensity
                sample is unavailable, not zero flux. Output flag metadata may
                be incomplete at masked pixels, so a zero flag value does not
                establish that a dark pixel is clean.
              </p>
            </section>
            <section>
              <h3>3. Inspect measurements and evidence</h3>
              <p>
                Spectrum counts recorded samples, finite fluxes and eligible
                measurements separately. Null flux is unavailable, not zero.
                Finite excluded sums remain exploratory. Negative flux and
                approximate error bars remain visible. Select a sample by click,
                keyboard or the table to inspect its reasons; molecular guides
                are reference positions, not detections.
              </p>
              <p>
                Current archive eligibility requires a full clean chosen
                aperture, a non-hard-bad center, supported field background and
                at least ten clean local-annulus pixels. This is necessary
                screening, not source-isolation or variability certification.
                Historical saved eligibility follows its recorded processing.
              </p>
              <p>
                Evidence separates real origin, comparison status, measurement
                availability and validation scope. Replaying arithmetic does not
                establish scientific validity. Report exports name their
                selected observations; native spectrum extraction is separate
                from the displayed image. Missing lineage stays unknown.
              </p>
            </section>
            <section>
              <h3>Display, navigation and accessibility</h3>
              <p>
                Advanced display contains colormap, stretch, contrast, overlays
                and field size. Changing display settings does not change native
                flux measurements. The cursor plane may be normalized display
                intensity and can use different contributing bands from the
                image; its label identifies the recorded plane and
                normalization.
              </p>
              <p>
                Use Zoom in, Zoom out and Reset view. Mouse drag pans; Control
                plus wheel zooms. Touch scrolls normally. With the image
                focused, Shift plus arrow keys pans. Search offers coordinate
                entry without using the image; the Spectrum table is the
                alternative to plot hover.
              </p>
              <KeyboardShortcuts />
              <p>
                Blinking may be uncomfortable or photosensitive. Manual steps
                and side-by-side avoid automatic flashing. Reduced motion
                disables playback. The eight-frame-per-second ceiling is not a
                flash-safety certification; start paused and stop immediately if
                needed.
              </p>
            </section>
            <section>
              <h3>Sharing and technical depth</h3>
              <p>
                Copy view link records the query, source, selections, display,
                camera and advanced settings. Shared views always open paused.
                An expected analysis identity can reveal a different archive
                result; the URL does not force the server to replay old bytes.
                Evidence report and source records provide deeper inspection.
                Advanced trial-motion and parallax controls are assumptions for
                exploration, never measurements or detections. Gaia pins are
                catalog annotations, not SPHEREx detections; reference images
                differ in date, passband and resolution.
              </p>
            </section>
          </>
        )}
      </div>
    </Modal>
  );
}
