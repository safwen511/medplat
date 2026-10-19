"use client";

import { ShieldAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useMember } from "@/components/layout/use-member";

/**
 * Deterrence on lesson pages (docs/protection.md): no printing (CSS hides the lesson; Ctrl/Cmd+P
 * shows a notice), no copying the text (selection stays, for highlights), and a faint diagonal
 * watermark with the tester's name and masked code. None of this is security.
 */
export function LessonGuard({ articleId }: { articleId: string }) {
  const me = useMember();
  const [notice, setNotice] = useState<string | null>(null);
  const timer = useRef(0);

  const toast = useCallback((message: string) => {
    window.clearTimeout(timer.current);
    setNotice(message);
    timer.current = window.setTimeout(() => setNotice(null), 2600);
  }, []);

  useEffect(() => {
    const article = document.getElementById(articleId);
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "p") {
        event.preventDefault();
        toast("L'impression n'est pas disponible sur MedPlat.");
      }
    };
    const onCopy = (event: ClipboardEvent) => {
      event.preventDefault();
      toast("La copie du cours est désactivée. Tu peux surligner le texte.");
    };
    const onDrag = (event: DragEvent) => event.preventDefault();
    window.addEventListener("keydown", onKey, true);
    article?.addEventListener("copy", onCopy);
    article?.addEventListener("cut", onCopy);
    article?.addEventListener("dragstart", onDrag);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      article?.removeEventListener("copy", onCopy);
      article?.removeEventListener("cut", onCopy);
      article?.removeEventListener("dragstart", onDrag);
      window.clearTimeout(timer.current);
    };
  }, [articleId, toast]);

  const mark = me?.member ? me.mark : null;
  const tile = useMemo(() => (mark ? watermarkTile(mark) : null), [mark]);

  return (
    <>
      {tile && (
        <div
          aria-hidden
          className="lesson-watermark pointer-events-none fixed inset-0 z-20 select-none print:hidden"
          style={{ backgroundImage: tile }}
        />
      )}
      <AnimatePresence>
        {notice && (
          <motion.div
            role="status"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-x-0 bottom-24 z-50 flex justify-center px-4"
          >
            <p className="flex items-center gap-2.5 rounded-full border border-border-strong bg-panel px-5 py-3 text-sm shadow-depth-3">
              <ShieldAlert className="size-4 shrink-0 text-highyield" aria-hidden />
              {notice}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
      <p className="print-notice">L&apos;impression n&apos;est pas disponible sur MedPlat.</p>
    </>
  );
}

/** A repeating SVG tile with the text written at -30°. */
function watermarkTile(text: string): string {
  const escaped = text.replace(/[<>&"']/g, (char) => `&#${char.charCodeAt(0)};`);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="420" height="260"><text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" transform="rotate(-30 210 130)" font-family="IBM Plex Sans, sans-serif" font-size="15" fill="#808897">${escaped}</text></svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}
