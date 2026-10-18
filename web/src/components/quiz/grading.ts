import type { Exercise, Option } from "@/lib/content/types";
import { answerKey, shuffle } from "@/lib/utils";

/** What the student entered, per exercise type. */
export type Response =
  | { type: "qcm" | "image"; choice: string | null }
  | { type: "qrm"; choices: string[] }
  | { type: "vrai_faux"; value: boolean | null }
  | { type: "texte_a_trous"; blanks: Record<string, string> }
  | { type: "association"; pairs: Record<string, string> } // left id -> right id
  | { type: "ordre"; order: string[] }
  | { type: "categories"; mapping: Record<string, string> } // item id -> category id
  | { type: "numerique"; value: string };

export interface Grade {
  correct: boolean;
  /** Units judged correct out of the units in the item (propositions, blanks, pairs...). */
  score: number;
  total: number;
}

export const TYPE_LABELS: Record<Exercise["type"], string> = {
  qcm: "QCM",
  qrm: "QRM",
  vrai_faux: "Vrai / Faux",
  texte_a_trous: "Texte à trous",
  association: "Association",
  ordre: "Remise en ordre",
  categories: "Catégories",
  numerique: "Numérique",
  image: "Image",
};

/** Stable 32-bit seed from a question id (FNV-1a), so shuffles never change between renders. */
export function seedOf(id: string) {
  let hash = 2166136261;
  for (let i = 0; i < id.length; i++) {
    hash ^= id.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function shuffledOptions(id: string, options: Option[]) {
  return shuffle(options, seedOf(id));
}

/** Initial order of an ordering item: shuffled, and never already solved. */
export function initialOrder(id: string, items: Option[], order: string[]) {
  const ids = shuffle(
    items.map((item) => item.id),
    seedOf(id),
  );
  if (ids.length > 1 && ids.every((value, i) => value === order[i])) ids.push(ids.shift()!);
  return ids;
}

export function emptyResponse(exercise: Exercise): Response {
  switch (exercise.type) {
    case "qcm":
    case "image":
      return { type: exercise.type, choice: null };
    case "qrm":
      return { type: "qrm", choices: [] };
    case "vrai_faux":
      return { type: "vrai_faux", value: null };
    case "texte_a_trous":
      return { type: "texte_a_trous", blanks: {} };
    case "association":
      return { type: "association", pairs: {} };
    case "ordre":
      return { type: "ordre", order: initialOrder(exercise.id, exercise.items, exercise.order) };
    case "categories":
      return { type: "categories", mapping: {} };
    case "numerique":
      return { type: "numerique", value: "" };
  }
}

export function parseNumber(value: string) {
  const cleaned = value.replace(/\s/g, "").replace(",", ".");
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(cleaned)) return null;
  return Number(cleaned);
}

export function blankIds(text: string) {
  return [...text.matchAll(/\{\{\s*([^}\s]+)\s*\}\}/g)].map((match) => match[1]);
}

export function blankAccepted(accepted: string[] | undefined, value: string | undefined) {
  const key = answerKey(value ?? "");
  return key !== "" && (accepted ?? []).some((answer) => answerKey(answer) === key);
}

/** Whether the response is complete enough to be submitted. */
export function isAnswerable(exercise: Exercise, response: Response) {
  switch (response.type) {
    case "qcm":
    case "image":
      return response.choice !== null;
    case "qrm":
      return response.choices.length > 0;
    case "vrai_faux":
      return response.value !== null;
    case "texte_a_trous":
      return Object.values(response.blanks).some((value) => value.trim() !== "");
    case "association":
      return exercise.type === "association" && exercise.left.every((left) => response.pairs[left.id]);
    case "ordre":
      return true;
    case "categories":
      return exercise.type === "categories" && exercise.items.every((item) => response.mapping[item.id]);
    case "numerique":
      return parseNumber(response.value) !== null;
  }
}

const all = (score: number, total: number): Grade => ({ correct: total > 0 && score === total, score, total });

export function grade(exercise: Exercise, response: Response): Grade {
  switch (exercise.type) {
    case "qcm":
    case "image": {
      const ok = response.type === exercise.type && response.choice === exercise.answer;
      return all(ok ? 1 : 0, 1);
    }
    case "qrm": {
      const chosen = new Set(response.type === "qrm" ? response.choices : []);
      const expected = new Set(exercise.answer);
      const score = exercise.options.filter((option) => chosen.has(option.id) === expected.has(option.id)).length;
      return all(score, exercise.options.length);
    }
    case "vrai_faux":
      return all(response.type === "vrai_faux" && response.value === exercise.answer ? 1 : 0, 1);
    case "texte_a_trous": {
      const ids = blankIds(exercise.text);
      const blanks = response.type === "texte_a_trous" ? response.blanks : {};
      return all(ids.filter((id) => blankAccepted(exercise.blanks[id], blanks[id])).length, ids.length);
    }
    case "association": {
      const pairs = response.type === "association" ? response.pairs : {};
      return all(exercise.left.filter((left) => pairs[left.id] === exercise.pairs[left.id]).length, exercise.left.length);
    }
    case "ordre": {
      const order = response.type === "ordre" ? response.order : [];
      return all(exercise.order.filter((id, i) => order[i] === id).length, exercise.order.length);
    }
    case "categories": {
      const mapping = response.type === "categories" ? response.mapping : {};
      return all(
        exercise.items.filter((item) => mapping[item.id] === exercise.mapping[item.id]).length,
        exercise.items.length,
      );
    }
    case "numerique": {
      const value = response.type === "numerique" ? parseNumber(response.value) : null;
      return all(value !== null && Math.abs(value - exercise.value) <= exercise.tolerance + 1e-9 ? 1 : 0, 1);
    }
  }
}

/** Compact, JSON-friendly record of the response for the attempts log. */
export function responsePayload(response: Response): unknown {
  const { type, ...rest } = response;
  void type;
  return rest;
}

export function formatDuration(ms: number) {
  const seconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

export function median(values: number[]) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/** Fresh seed for a new session (call from event handlers only). */
export function randomSeed() {
  return Math.floor(Math.random() * 4294967296);
}
