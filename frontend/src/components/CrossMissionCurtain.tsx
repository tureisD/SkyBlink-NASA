import { useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";

export interface CrossMissionCurtainProps {
  opticalUrl: string;
  infraredUrl: string;
  opticalLabel?: string;
  infraredLabel?: string;
  /** Manifest-side attribution for the reference cutouts. */
  attribution?: string | null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Draggable optical / mid-infrared reference split.
 *
 * Uses the manifest's real reference overlays and hides itself if either
 * side is unavailable.
 */
export function CrossMissionCurtain({
  opticalUrl,
  infraredUrl,
  opticalLabel = "Optical · DSS/Gaia",
  infraredLabel = "Mid-IR · WISE",
  attribution = null,
}: CrossMissionCurtainProps) {
  const [split, setSplit] = useState(50);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);

  if (!opticalUrl || !infraredUrl) return null;

  const setFromClientX = (clientX: number) => {
    const stage = stageRef.current;
    if (!stage) return;
    const rect = stage.getBoundingClientRect();
    if (rect.width <= 0) return;
    setSplit(clamp(((clientX - rect.left) / rect.width) * 100, 0, 100));
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    draggingRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
    setFromClientX(event.clientX);
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    setFromClientX(event.clientX);
  };

  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    draggingRef.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const onHandleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    let next = split;
    if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      next = clamp(split - 2, 0, 100);
    } else if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      next = clamp(split + 2, 0, 100);
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = 100;
    } else {
      return;
    }
    event.preventDefault();
    setSplit(next);
  };

  const infraPercent = Math.round(100 - split);

  return (
    <div className="curtain">
      <div
        ref={stageRef}
        className="curtain-stage"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <img
          className="curtain-img"
          src={opticalUrl}
          alt={`${opticalLabel} reference view of the field`}
          draggable={false}
        />
        <img
          className="curtain-img curtain-img--ir"
          src={infraredUrl}
          alt={`${infraredLabel} reference view of the field`}
          draggable={false}
          style={{ clipPath: `inset(0 0 0 ${split}%)` }}
        />
        <div className="curtain-divider" style={{ left: `${split}%` }}>
          <div
            className="curtain-handle"
            role="slider"
            tabIndex={0}
            aria-label="Optical to mid-infrared split"
            aria-orientation="horizontal"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(split)}
            aria-valuetext={`${Math.round(split)}% optical, ${infraPercent}% mid-infrared`}
            onKeyDown={onHandleKeyDown}
          >
            <span aria-hidden="true">↔</span>
          </div>
        </div>
        <span className="curtain-tag curtain-tag--left">{opticalLabel}</span>
        <span className="curtain-tag curtain-tag--right">{infraredLabel}</span>
      </div>

      <div className="curtain-meta">
        <span className="mono">{Math.round(split)}% optical · {infraPercent}% mid-IR</span>
        <span className="curtain-real">REAL REFERENCE CUTOUTS · SAME WCS</span>
      </div>
      {attribution ? <p className="curtain-attribution">{attribution}</p> : null}
      <p className="control-hint">
        Reference cutouts on the same WCS, not simultaneous exposures. Drag the
        divider or focus it and use ←/→.
      </p>
    </div>
  );
}
