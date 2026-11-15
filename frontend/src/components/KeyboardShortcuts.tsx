/** These bindings match App's viewer handler and the canvas camera controls. */
export function KeyboardShortcuts() {
  return (
    <section className="keyboard-reference" aria-label="Keyboard shortcuts">
      <p>
        Focus or click the image to use viewer shortcuts. Native controls, text
        entry and open dialogs keep their own keys. Holding a shortcut does not
        repeat transport actions.
      </p>
      <dl>
        <div>
          <dt>
            <kbd>Space</kbd>
          </dt>
          <dd>
            Play or pause. Playback requires two epochs, a normal image view and
            reduced motion off.
          </dd>
        </div>
        <div>
          <dt>
            <kbd>Left</kbd> / <kbd>Right</kbd>
          </dt>
          <dd>
            Previous / next observation; pauses playback. Steps are unavailable
            in difference view.
          </dd>
        </div>
        <div>
          <dt>
            <kbd>Shift</kbd> + arrows
          </dt>
          <dd>Pan while the image is focused.</dd>
        </div>
        <div>
          <dt>
            <kbd>R</kbd>
          </dt>
          <dd>Reset image zoom and pan.</dd>
        </div>
        <div>
          <dt>
            <kbd>D</kbd>
          </dt>
          <dd>Toggle a recorded difference when available.</dd>
        </div>
        <div>
          <dt>
            <kbd>A</kbd> / <kbd>T</kbd>
          </dt>
          <dd>Combined bands / thermal composite when available.</dd>
        </div>
        <div>
          <dt>
            <kbd>1</kbd>–<kbd>6</kbd>
          </dt>
          <dd>Select an available detector band.</dd>
        </div>
        <div>
          <dt>
            <kbd>/</kbd>
          </dt>
          <dd>Open Search outside text entry or a dialog.</dd>
        </div>
        <div>
          <dt>
            <kbd>?</kbd>
          </dt>
          <dd>Open this keyboard reference outside text entry or a dialog.</dd>
        </div>
        <div>
          <dt>
            <kbd>Escape</kbd>
          </dt>
          <dd>
            Close an open dialog or focused notification and return to its
            opener.
          </dd>
        </div>
      </dl>
      <p>
        Playback starts paused and stays capped at 8 FPS. Manual steps and
        side-by-side comparison remain available with reduced motion.
      </p>
    </section>
  );
}
