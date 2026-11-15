import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Root from "./Root";
import "./styles/global.css";
import "./styles/theme.css";
import { loadLandingFonts } from "./landing/fonts";

// Embedded typefaces for the landing page and the viewer theme (offline-safe).
void loadLandingFonts();

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element #root is missing from index.html");
}

createRoot(container).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
