/**
 * Landing-page typefaces. The font data is embedded (see fontData.ts), so the
 * app still runs fully offline and the build emits no font files. They load
 * with the lazy landing chunk and are never used by the viewer.
 */
import {
  ANTON_WOFF2 as antonUrl,
  GARAMOND_ITALIC_WOFF2 as garamondItalicUrl,
  MONO_BOLD_WOFF2 as monoBoldUrl,
  MONO_REGULAR_WOFF2 as monoRegularUrl,
} from "./fontData";

export const DISPLAY_FAMILY = "SkyBlink Display";
export const SERIF_FAMILY = "SkyBlink Serif";
export const MONO_FAMILY = "SkyBlink Mono";

let loading: Promise<void> | null = null;

export function loadLandingFonts(): Promise<void> {
  if (loading) return loading;
  if (typeof FontFace === "undefined" || !document.fonts) {
    loading = Promise.resolve();
    return loading;
  }
  const faces = [
    new FontFace(DISPLAY_FAMILY, `url(${antonUrl})`, { weight: "400" }),
    new FontFace(SERIF_FAMILY, `url(${garamondItalicUrl})`, {
      weight: "500",
      style: "italic",
    }),
    new FontFace(MONO_FAMILY, `url(${monoRegularUrl})`, { weight: "400" }),
    new FontFace(MONO_FAMILY, `url(${monoBoldUrl})`, { weight: "700" }),
  ];
  loading = Promise.all(
    faces.map((face) =>
      face.load().then((loaded) => {
        document.fonts.add(loaded);
      }),
    ),
  ).then(
    () => undefined,
    // A font that fails to decode falls back to the system stack.
    () => undefined,
  );
  return loading;
}
