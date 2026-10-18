// Exam dates: a certif is planned between today and three years ahead. Anything else (an empty
// value, or a year a date field auto-filled such as 2001) is treated as "no date set".

function iso(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** min/max attributes for an exam date field. */
export function examDateBounds(now: Date = new Date()): { min: string; max: string } {
  const max = new Date(now.getFullYear() + 3, now.getMonth(), now.getDate());
  return { min: iso(now), max: iso(max) };
}

/** The exam date if it is plausible (YYYY-MM-DD, not before last month, at most 3 years ahead). */
export function validExamDate(examDate: string | null | undefined, now: Date = new Date()): string | null {
  if (!examDate || !/^\d{4}-\d{2}-\d{2}$/.test(examDate)) return null;
  const [y, m, d] = examDate.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const earliest = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
  const latest = new Date(now.getFullYear() + 3, now.getMonth(), now.getDate());
  return date >= earliest && date <= latest ? examDate : null;
}

/** Ref callback for an exam date field: limits the picker to the next three years (browser-side,
 * so pages never read the clock while prerendering). */
export function setExamDateBounds(input: HTMLInputElement | null): void {
  if (!input) return;
  const { min, max } = examDateBounds();
  input.min = min;
  input.max = max;
}
