import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
export interface ModalProps {
  onClose: () => void;
  labelledBy: string;
  className?: string;
  children: ReactNode;
}
/** Portal leaves the application inert; dialog owns focus until closed. */
export function Modal({
  onClose,
  labelledBy,
  className,
  children,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const restore = document.activeElement as HTMLElement | null;
    const root = document.getElementById("root");
    const wasInert = root?.inert ?? false;
    if (root) root.inert = true;
    const scroll = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const panel = panelRef.current;
      const items = Array.from(
        panel.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter(
        (el) =>
          !el.hasAttribute("disabled") &&
          el.getClientRects().length > 0 &&
          !el.closest("[inert]"),
      );
      if (!items.length) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0],
        last = items[items.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === panel ||
          !panel.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          !panel.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      if (root) root.inert = wasInert;
      document.body.style.overflow = scroll;
      if (restore?.isConnected) restore.focus();
    };
  }, []);
  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) closeRef.current();
      }}
    >
      <div
        ref={panelRef}
        className={`modal-panel ${className ?? ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
