"use client";

import { Highlighter, Square, Trash2, Underline } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";

import { useReaderSettings } from "@/lib/reader-settings";
import { cn } from "@/lib/utils";

import { rangeOf } from "./anchor";
import { BODY_SELECTOR, revealAndScroll } from "./marked-body";
import { onMarksChange, readAllMarks, removeMark, type LessonMarks, type MarkStyle } from "./store";

const ICONS: Record<MarkStyle, typeof Highlighter> = { highlight: Highlighter, underline: Underline, box: Square };

let cache: { key: string; value: LessonMarks[] } | null = null;
function snapshot(): LessonMarks[] {
  const value = readAllMarks();
  const key = JSON.stringify(value);
  if (cache?.key !== key) cache = { key, value };
  return cache.value;
}
const NONE: LessonMarks[] = [];

/**
 * Every highlight across lessons, grouped by lesson (the current one first). A tap goes to the
 * passage (here, or on its lesson page); each can be deleted.
 */
export function AllMarks({ currentLessonId, onNavigate }: { currentLessonId?: string; onNavigate?: () => void }) {
  const all = useSyncExternalStore(onMarksChange, snapshot, () => NONE);
  const { colors } = useReaderSettings();
  const groups = [...all].sort((a, b) => Number(b.lessonId === currentLessonId) - Number(a.lessonId === currentLessonId));

  if (groups.length === 0)
    return (
      <p className="font-sans text-muted">
        Choisis un stylo dans la barre d&apos;outils, puis sélectionne un passage : il apparaîtra ici.
      </p>
    );

  const goHere = (lessonId: string, markId: string) => {
    const body = document.querySelector(BODY_SELECTOR);
    const mark = groups.find((group) => group.lessonId === lessonId)?.marks.find((item) => item.id === markId);
    const range = body && mark && rangeOf(body, mark);
    if (!range) return;
    onNavigate?.();
    window.setTimeout(() => revealAndScroll(range), 60);
  };

  return (
    <div className="flex flex-col gap-6 font-sans" data-no-highlight>
      {groups.map((group) => (
        <section key={group.lessonId} aria-label={group.title} className="flex flex-col gap-2">
          <h3 className="flex items-baseline justify-between gap-3 text-[0.95rem]">
            <span className="min-w-0 truncate">{group.title}</span>
            <span className="numeral shrink-0 text-xs text-muted">{group.marks.length}</span>
          </h3>
          <ul className="flex flex-col gap-1.5">
            {group.marks.map((mark) => {
              const Icon = ICONS[mark.style];
              const here = group.lessonId === currentLessonId;
              const body = (
                <>
                  <Icon className="mt-1 size-3.5 shrink-0" style={{ color: colors[mark.color] }} aria-hidden />
                  <span className="line-clamp-2 leading-snug">{mark.quote}</span>
                </>
              );
              const rowClass =
                "flex min-h-12 min-w-0 flex-1 items-start gap-2.5 rounded-control px-2 py-2 text-left text-sm transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
              return (
                <li key={mark.id} className="flex items-start gap-1">
                  {here ? (
                    <button type="button" onClick={() => goHere(group.lessonId, mark.id)} className={rowClass}>
                      {body}
                    </button>
                  ) : (
                    <Link href={`${group.href}#mark=${mark.id}`} onClick={onNavigate} className={rowClass}>
                      {body}
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => removeMark(group.lessonId, mark.id)}
                    aria-label="Supprimer ce surlignage"
                    className={cn(
                      "flex size-11 shrink-0 items-center justify-center rounded-control text-muted transition-colors hover:bg-wrong-soft hover:text-wrong",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    )}
                  >
                    <Trash2 className="size-4" strokeWidth={1.6} aria-hidden />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
