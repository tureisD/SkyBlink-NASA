/**
 * Landing-page ring tunnel (presentation only).
 *
 * A dependency-free Canvas 2D scene: rings of text and a star field are
 * placed at depths along the view axis and perspective-projected, so pointer
 * movement gives parallax and the "dive" moves the camera down the tunnel.
 * Nothing here touches observation data or the viewer.
 */

export interface SceneRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface SceneInput {
  /** Pointer position relative to the viewport centre, each in [-1, 1]. */
  pointerX: number;
  pointerY: number;
  /** Dive progress, 0 (idle) to 1 (arrived). */
  dive: number;
  /** Page scroll in viewport heights. */
  scroll: number;
  /** Where the scene sits on the page when idle; null when not laid out. */
  rect: SceneRect | null;
}

export interface SceneOptions {
  reducedMotion: boolean;
  monoFont: string;
  panel: string;
  ink: string;
  highlight: string;
  accent: string;
}

export interface SceneHandle {
  destroy: () => void;
}

const TEXTURE_SIZE = 1024;
const TEXTURE_RADIUS = TEXTURE_SIZE / 2 - 40;
const RING_COUNT = 12;
const RING_SPACING = 0.55;
const Z_MIN = 0.5;
const Z_RANGE = RING_COUNT * RING_SPACING;
const Z_MAX = Z_MIN + Z_RANGE;
const STAR_COUNT = 180;

const RING_PHRASES = [
  "THE INFRARED SKY · ",
  "EPOCH A · EPOCH B · ",
  "102 BANDS · SIX DETECTORS · ",
  "SEE WHAT MOVED · SEE WHAT CHANGED · ",
  "BARNARD'S STAR · EPSILON INDI B · WISE 0855 · RW AURIGAE · R DRACONIS · ",
  "EVERY SIX MONTHS · SURVEY PASS · ",
];

function smoothstep(edge0: number, edge1: number, value: number): number {
  const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

function positiveModulo(value: number, modulus: number): number {
  return ((value % modulus) + modulus) % modulus;
}

/** Deterministic pseudo-random sequence so the star field is stable. */
function seededRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296;
    return state / 4294967296;
  };
}

function makeRingTexture(
  phrase: string,
  color: string,
  font: string,
): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = TEXTURE_SIZE;
  canvas.height = TEXTURE_SIZE;
  const context = canvas.getContext("2d");
  if (!context) return canvas;
  const size = 30;
  context.font = `${size}px ${font}`;
  context.fillStyle = color;
  context.textAlign = "center";
  context.textBaseline = "middle";
  const advance = size * 0.6 + 6;
  const count = Math.floor((2 * Math.PI * TEXTURE_RADIUS) / advance);
  const step = (2 * Math.PI) / count;
  let text = phrase;
  while (text.length < count) text += phrase;
  // Leave a short gap so each ring reads as a broken band, not a closed loop.
  const used = Math.floor(count * 0.93);
  for (let index = 0; index < used; index += 1) {
    const character = text[index];
    if (character === " ") continue;
    const angle = index * step;
    context.save();
    context.translate(
      TEXTURE_SIZE / 2 + TEXTURE_RADIUS * Math.sin(angle),
      TEXTURE_SIZE / 2 - TEXTURE_RADIUS * Math.cos(angle),
    );
    context.rotate(angle);
    context.fillText(character, 0, 0);
    context.restore();
  }
  return canvas;
}

export function createRingScene(
  canvas: HTMLCanvasElement,
  frame: (dtSeconds: number) => SceneInput,
  options: SceneOptions,
): SceneHandle {
  const context = canvas.getContext("2d");
  if (!context) return { destroy: () => undefined };

  const textures = RING_PHRASES.map((phrase, index) =>
    makeRingTexture(
      phrase,
      index === 3 ? options.highlight : index === 1 ? options.accent : options.ink,
      options.monoFont,
    ),
  );
  const random = seededRandom(20261115);
  const stars = Array.from({ length: STAR_COUNT }, () => ({
    x: (random() * 2 - 1) * 1.7,
    y: (random() * 2 - 1) * 1.7,
    z: random() * Z_RANGE,
    size: 0.6 + random() * 1.2,
  }));

  let animationFrame = 0;
  let lastTime = 0;
  let clock = 0;
  let travel = 0;
  let width = 0;
  let height = 0;
  let pixelRatio = 1;
  let smoothX = 0;
  let smoothY = 0;
  let lastSignature = "";

  const resize = () => {
    pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.max(1, Math.round(width * pixelRatio));
    canvas.height = Math.max(1, Math.round(height * pixelRatio));
    lastSignature = "";
  };

  const draw = (input: SceneInput, speed: number) => {
    const rect = input.rect;
    const reveal = easeInOut(Math.min(1, input.dive * 1.7));
    if (!rect || (reveal === 0 && (rect.y + rect.h < 0 || rect.y > height))) {
      canvas.style.visibility = "hidden";
      return;
    }
    canvas.style.visibility = "visible";

    // The visible window grows from the hero panel to the whole viewport.
    const left = rect.x * (1 - reveal);
    const top = rect.y * (1 - reveal);
    const right = (rect.x + rect.w) * (1 - reveal) + width * reveal;
    const bottom = (rect.y + rect.h) * (1 - reveal) + height * reveal;
    canvas.style.clipPath = `inset(${Math.max(0, top)}px ${Math.max(0, width - right)}px ${Math.max(0, height - bottom)}px ${Math.max(0, left)}px)`;

    const centreX = (left + right) / 2;
    const centreY = (top + bottom) / 2;
    const unit = 0.62 * Math.min(right - left, bottom - top);
    const arrive = smoothstep(0.8, 1, input.dive);
    const tunnelAlpha = 1 - arrive;

    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.globalAlpha = 1;
    context.fillStyle = options.panel;
    context.fillRect(left, top, right - left, bottom - top);

    const parallax = unit * 0.22;
    const offsetAt = (z: number) => (z - 1) / (z + 1);
    const depthOf = (base: number) =>
      Z_MIN + positiveModulo(base - travel - input.scroll * 1.4, Z_RANGE);
    const depthAlpha = (z: number) =>
      smoothstep(Z_MAX, Z_MAX - 1.2, z) * smoothstep(Z_MIN, Z_MIN + 0.3, z);

    // Stars: points at rest, streaks while the camera moves.
    context.strokeStyle = options.ink;
    context.fillStyle = options.ink;
    context.lineCap = "round";
    for (const star of stars) {
      const z = depthOf(star.z);
      const alpha = depthAlpha(z) * (0.35 + 0.65 * (1 - z / Z_MAX));
      if (alpha <= 0.01) continue;
      const shift = offsetAt(z) * parallax;
      const x = centreX + smoothX * shift + (star.x * unit) / z;
      const y = centreY + smoothY * shift + (star.y * unit) / z;
      const radius = Math.min(3, Math.max(0.5, star.size / z));
      context.globalAlpha = alpha;
      const tail = speed * 0.05;
      if (tail > 0.02) {
        const zTail = z + tail;
        context.lineWidth = radius * 1.4;
        context.beginPath();
        context.moveTo(
          centreX + smoothX * shift + (star.x * unit) / zTail,
          centreY + smoothY * shift + (star.y * unit) / zTail,
        );
        context.lineTo(x, y);
        context.stroke();
      } else {
        context.beginPath();
        context.arc(x, y, radius, 0, Math.PI * 2);
        context.fill();
      }
    }

    // Rings, far to near.
    if (tunnelAlpha > 0.01) {
      const rings = Array.from({ length: RING_COUNT }, (_, index) => ({
        index,
        z: depthOf(index * RING_SPACING),
      })).sort((a, b) => b.z - a.z);
      for (const ring of rings) {
        const alpha = depthAlpha(ring.z) * tunnelAlpha;
        if (alpha <= 0.01) continue;
        const scale = unit / ring.z / TEXTURE_RADIUS;
        const drawn = TEXTURE_SIZE * scale;
        const shift = offsetAt(ring.z) * parallax;
        const direction = ring.index % 2 === 0 ? 1 : -1;
        const angle =
          direction * (clock * (0.05 + (ring.index % 3) * 0.015) + travel * 0.18) +
          ring.index * 1.3;
        context.save();
        context.globalAlpha = alpha;
        context.translate(centreX + smoothX * shift, centreY + smoothY * shift);
        context.rotate(angle);
        context.drawImage(
          textures[ring.index % textures.length],
          -drawn / 2,
          -drawn / 2,
          drawn,
          drawn,
        );
        context.restore();
      }
    }

    // Centre marker: one position stays, the other blinks, like a mover
    // between two survey passes. On arrival a reticle locks on instead.
    const markerAlpha = Math.max(0, 1 - input.dive * 4);
    if (markerAlpha > 0) {
      context.globalAlpha = markerAlpha;
      context.strokeStyle = options.ink;
      context.lineWidth = 1;
      context.beginPath();
      context.arc(centreX - 7, centreY + 4, 4, 0, Math.PI * 2);
      context.stroke();
      const lit = options.reducedMotion || Math.floor(clock / 0.6) % 2 === 0;
      if (lit) {
        context.fillStyle = options.accent;
        context.beginPath();
        context.arc(centreX + 5, centreY - 3, 5, 0, Math.PI * 2);
        context.fill();
      }
    }
    if (arrive > 0) {
      const radius = 46 + (1 - arrive) * unit * 0.5;
      context.globalAlpha = arrive;
      context.strokeStyle = options.ink;
      context.lineWidth = 1;
      context.setLineDash([4, 5]);
      context.beginPath();
      context.arc(centreX, centreY, radius, 0, Math.PI * 2);
      context.stroke();
      context.setLineDash([]);
      context.beginPath();
      for (const [dx, dy] of [
        [0, -1],
        [0, 1],
        [-1, 0],
        [1, 0],
      ]) {
        context.moveTo(centreX + dx * (radius - 12), centreY + dy * (radius - 12));
        context.lineTo(centreX + dx * (radius + 24), centreY + dy * (radius + 24));
      }
      context.stroke();
      context.fillStyle = options.accent;
      context.beginPath();
      context.arc(centreX, centreY, 5, 0, Math.PI * 2);
      context.fill();
    }
    context.globalAlpha = 1;
  };

  const tick = (time: number) => {
    const dt = lastTime === 0 ? 0 : Math.min(0.05, (time - lastTime) / 1000);
    lastTime = time;
    const input = frame(dt);
    const cruise = 1 - smoothstep(0.78, 1, input.dive) * 0.92;
    const speed = options.reducedMotion
      ? 0
      : 0.035 + 9 * easeInOut(Math.min(1, input.dive * 1.25)) * cruise;
    if (!options.reducedMotion) {
      clock += dt;
      travel += speed * dt;
      const follow = Math.min(1, dt * 4);
      smoothX += (input.pointerX - smoothX) * follow;
      smoothY += (input.pointerY - smoothY) * follow;
      draw(input, speed);
    } else {
      // Static scene: repaint only when its placement changes.
      const rect = input.rect;
      const signature = rect
        ? `${rect.x}|${rect.y}|${rect.w}|${rect.h}|${input.scroll}|${input.dive}`
        : "none";
      if (signature !== lastSignature) {
        lastSignature = signature;
        draw({ ...input, scroll: 0 }, 0);
      }
    }
    animationFrame = window.requestAnimationFrame(tick);
  };

  resize();
  window.addEventListener("resize", resize);
  animationFrame = window.requestAnimationFrame(tick);

  return {
    destroy: () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", resize);
    },
  };
}
