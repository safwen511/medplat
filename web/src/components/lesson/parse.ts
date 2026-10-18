// Splits a lesson's markdown into a heading tree so sections can be folded, badged and listed
// in the table of contents. Pure and server-safe.

export interface LessonSection {
  id: string; // anchor id, unique within the lesson
  level: number; // 2 for "##", 3 for "###" ...
  title: string; // heading text, markers removed (may contain inline markdown)
  highYield: boolean; // "{examen}" marker
  folded: boolean; // "{plié}" marker, or the reviewer section
  reviewer: boolean; // "Points à vérifier par le relecteur médical"
  body: string; // markdown between this heading and the first sub-heading
  children: LessonSection[];
}

export interface ParsedLesson {
  preface: string; // content before the first section (H1 title removed)
  sections: LessonSection[];
}

const HEADING = /^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$/;
const FENCE = /^[ \t]{0,3}(```|~~~)/;
const MARKER = /\{\s*(examen|pli[ée])\s*\}/giu;

/** Lowercase, accent-free, whitespace-collapsed form for comparisons. */
export function plainKey(value: string) {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

export function isReviewerTitle(title: string) {
  return plainKey(title).startsWith("points a verifier");
}

function slugify(value: string) {
  const slug = plainKey(value.replace(/\[[^\]]*\]/g, "").replace(/[*_`]/g, ""))
    .replace(/ /g, "-")
    .slice(0, 60);
  return slug || "section";
}

/** Plain heading text (inline markdown removed), e.g. for the table of contents. */
export function plainTitle(title: string) {
  return title
    .replace(/\[(S\d+\b[^\]]*)\]/g, "")
    .replace(/[*_`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function parseLesson(markdown: string): ParsedLesson {
  const root: LessonSection = {
    id: "",
    level: 0,
    title: "",
    highYield: false,
    folded: false,
    reviewer: false,
    body: "",
    children: [],
  };
  const stack: LessonSection[] = [root];
  const used = new Map<string, number>();
  let buffer: string[] = [];
  let current = root;
  let inFence = false;
  let titleDropped = false;

  const flush = () => {
    current.body = buffer.join("\n").trim();
    buffer = [];
  };

  for (const line of markdown.split(/\r?\n/)) {
    if (FENCE.test(line)) inFence = !inFence;
    const match = inFence ? null : HEADING.exec(line);
    if (!match) {
      buffer.push(line);
      continue;
    }
    const level = match[1].length;
    const raw = match[2];
    // The lesson title is shown in the page header.
    if (level === 1 && !titleDropped && root.children.length === 0) {
      titleDropped = true;
      continue;
    }
    flush();
    const markers = [...raw.matchAll(MARKER)].map((item) => plainKey(item[1]));
    const title = raw.replace(MARKER, "").replace(/\s+/g, " ").trim();
    const reviewer = isReviewerTitle(title);
    const base = slugify(title);
    const count = used.get(base) ?? 0;
    used.set(base, count + 1);
    const section: LessonSection = {
      id: count ? `${base}-${count + 1}` : base,
      level,
      title,
      highYield: markers.includes("examen"),
      folded: markers.includes("plie") || reviewer,
      reviewer,
      body: "",
      children: [],
    };
    while (stack.length > 1 && stack[stack.length - 1].level >= level) stack.pop();
    stack[stack.length - 1].children.push(section);
    stack.push(section);
    current = section;
  }
  flush();
  return { preface: root.body, sections: root.children };
}
