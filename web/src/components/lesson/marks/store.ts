"use client";

// Highlights ("marks") kept in this browser, one entry per lesson. Storage can be blocked (private
// mode): every access is guarded and the page keeps working without them.

export type MarkStyle = "highlight" | "underline" | "box";

export interface Point {
  /** Unit id: the n-th text block of the lesson body ("u12"). */
  unit: string;
  /** Character offset in the unit's own text (source chips excluded). */
  offset: number;
}

export interface Mark {
  id: string;
  start: Point;
  end: Point;
  /** The marked text, to check the anchor and to find it again if the lesson changed. */
  quote: string;
  style: MarkStyle;
  /** 0..4, one of the five reader colours. */
  color: number;
  createdAt: string;
}

export interface LessonMarks {
  lessonId: string;
  title: string;
  href: string;
  marks: Mark[];
}

const PREFIX = "medplat:v1:marks:";
const EVENT = "medplat:marks";

function key(lessonId: string) {
  return `${PREFIX}${lessonId}`;
}

export function readLessonMarks(lessonId: string): LessonMarks | null {
  try {
    const raw = window.localStorage.getItem(key(lessonId));
    return raw ? (JSON.parse(raw) as LessonMarks) : null;
  } catch {
    return null;
  }
}

export function writeLessonMarks(entry: LessonMarks) {
  try {
    if (entry.marks.length === 0) window.localStorage.removeItem(key(entry.lessonId));
    else window.localStorage.setItem(key(entry.lessonId), JSON.stringify(entry));
  } catch {
    // kept on screen for this visit only
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: entry.lessonId }));
}

/** Every lesson with marks, most recent first. */
export function readAllMarks(): LessonMarks[] {
  const result: LessonMarks[] = [];
  try {
    for (let index = 0; index < window.localStorage.length; index++) {
      const name = window.localStorage.key(index);
      if (!name?.startsWith(PREFIX)) continue;
      const entry = JSON.parse(window.localStorage.getItem(name) ?? "null") as LessonMarks | null;
      if (entry?.marks.length) result.push(entry);
    }
  } catch {
    return result;
  }
  const latest = (entry: LessonMarks) => entry.marks.reduce((max, mark) => (mark.createdAt > max ? mark.createdAt : max), "");
  return result.sort((a, b) => latest(b).localeCompare(latest(a)));
}

export function removeMark(lessonId: string, markId: string) {
  const entry = readLessonMarks(lessonId);
  if (!entry) return;
  writeLessonMarks({ ...entry, marks: entry.marks.filter((mark) => mark.id !== markId) });
}

/** Re-renders on any change to the marks (this tab or another). */
export function onMarksChange(callback: () => void): () => void {
  const onStorage = (event: StorageEvent) => event.key?.startsWith(PREFIX) && callback();
  window.addEventListener(EVENT, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, callback);
    window.removeEventListener("storage", onStorage);
  };
}

export function newMarkId() {
  return `m${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}
