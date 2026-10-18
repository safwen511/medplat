// Development fixtures only: generic placeholder items (no medical content) so every exercise type
// can be tried on /dev/quiz before real, source-grounded exercises are exported.

import type { Exercise, Figure, YearIndex } from "@/lib/content/types";

const LESSON_A = "demo.module-1.lecon-1";
const LESSON_B = "demo.module-1.lecon-2";
const LESSON_C = "demo.module-2.lecon-3";

const hints: [string, string, string] = [
  "Indice de démonstration : reformuler ce que la question demande.",
  "Indice de démonstration : écarter les propositions incompatibles.",
  "Indice de démonstration : rappeler la règle du cours concernée.",
];

const base = (n: number, lessonId: string) => ({
  id: `${lessonId}#demo${n}`,
  lessonId,
  stem: `Question de démonstration n°${n}`,
  hints,
  explanation: `Explication de démonstration pour la question n°${n}.`,
  citations: "[S1 p.1]",
  highYield: n % 3 === 0,
  difficulty: ((n % 3) + 1) as 1 | 2 | 3,
});

const options = (count: number) =>
  Array.from({ length: count }, (_, i) => {
    const id = String.fromCharCode(65 + i);
    return { id, text: `Proposition ${id}` };
  });

function placeholderSvg(label: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400">
<rect width="640" height="400" fill="#eef3f5"/>
<rect x="40" y="40" width="560" height="320" rx="16" fill="none" stroke="#5a6b76" stroke-width="2" stroke-dasharray="8 6"/>
<circle cx="200" cy="190" r="60" fill="#e0f1f2" stroke="#0b6e74" stroke-width="3"/>
<rect x="340" y="130" width="140" height="120" rx="10" fill="#fdf3e1" stroke="#b7791f" stroke-width="3"/>
<text x="200" y="198" font-family="sans-serif" font-size="28" text-anchor="middle" fill="#0b6e74">A</text>
<text x="410" y="198" font-family="sans-serif" font-size="28" text-anchor="middle" fill="#b7791f">B</text>
<text x="320" y="320" font-family="sans-serif" font-size="20" text-anchor="middle" fill="#5a6b76">${label}</text>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const figure = (label: string): Figure => ({ source: "S1", page: 1, src: placeholderSvg(label), width: 640, height: 400 });

export const fixtureExercises: Exercise[] = [
  { ...base(1, LESSON_A), type: "qcm", options: options(4), answer: "B" },
  { ...base(2, LESSON_B), type: "qcm", options: options(5), answer: "D" },
  { ...base(3, LESSON_A), type: "qrm", options: options(5), answer: ["A", "C", "D"] },
  { ...base(4, LESSON_C), type: "qrm", options: options(4), answer: ["B", "C"] },
  { ...base(5, LESSON_A), type: "vrai_faux", stem: "Affirmation de démonstration n°5 (attendu : vrai).", answer: true },
  { ...base(6, LESSON_B), type: "vrai_faux", stem: "Affirmation de démonstration n°6 (attendu : faux).", answer: false },
  {
    ...base(7, LESSON_A),
    type: "texte_a_trous",
    stem: "Question de démonstration n°7 : compléter la phrase.",
    text: "Phrase de démonstration : le premier mot attendu est {{1}} et le second est {{2}}.",
    blanks: { "1": ["alpha"], "2": ["bêta", "beta"] },
  },
  {
    ...base(8, LESSON_C),
    type: "texte_a_trous",
    stem: "Question de démonstration n°8 : compléter le texte.",
    text: "Texte de démonstration avec un seul trou : {{1}}.",
    blanks: { "1": ["élément", "element"] },
  },
  {
    ...base(9, LESSON_B),
    type: "association",
    stem: "Question de démonstration n°9 : associer chaque terme à sa définition.",
    left: [
      { id: "L1", text: "Terme 1" },
      { id: "L2", text: "Terme 2" },
      { id: "L3", text: "Terme 3" },
    ],
    right: [
      { id: "R1", text: "Définition 1" },
      { id: "R2", text: "Définition 2" },
      { id: "R3", text: "Définition 3" },
    ],
    pairs: { L1: "R1", L2: "R2", L3: "R3" },
  },
  {
    ...base(10, LESSON_A),
    type: "association",
    stem: "Question de démonstration n°10 : associer les éléments.",
    left: [
      { id: "L1", text: "Élément gauche 1" },
      { id: "L2", text: "Élément gauche 2" },
      { id: "L3", text: "Élément gauche 3" },
      { id: "L4", text: "Élément gauche 4" },
    ],
    right: [
      { id: "R1", text: "Élément droit 1" },
      { id: "R2", text: "Élément droit 2" },
      { id: "R3", text: "Élément droit 3" },
      { id: "R4", text: "Élément droit 4" },
    ],
    pairs: { L1: "R1", L2: "R2", L3: "R3", L4: "R4" },
  },
  {
    ...base(11, LESSON_C),
    type: "ordre",
    stem: "Question de démonstration n°11 : remettre les étapes dans l'ordre.",
    items: [
      { id: "E1", text: "Étape 1" },
      { id: "E2", text: "Étape 2" },
      { id: "E3", text: "Étape 3" },
      { id: "E4", text: "Étape 4" },
    ],
    order: ["E1", "E2", "E3", "E4"],
  },
  {
    ...base(12, LESSON_B),
    type: "ordre",
    stem: "Question de démonstration n°12 : ordonner les éléments.",
    items: [
      { id: "E1", text: "Premier élément" },
      { id: "E2", text: "Deuxième élément" },
      { id: "E3", text: "Troisième élément" },
      { id: "E4", text: "Quatrième élément" },
      { id: "E5", text: "Cinquième élément" },
    ],
    order: ["E1", "E2", "E3", "E4", "E5"],
  },
  {
    ...base(13, LESSON_A),
    type: "categories",
    stem: "Question de démonstration n°13 : classer chaque élément.",
    categories: [
      { id: "C1", text: "Catégorie 1" },
      { id: "C2", text: "Catégorie 2" },
    ],
    items: [
      { id: "I1", text: "Élément 1 (cat. 1)" },
      { id: "I2", text: "Élément 2 (cat. 2)" },
      { id: "I3", text: "Élément 3 (cat. 1)" },
      { id: "I4", text: "Élément 4 (cat. 2)" },
    ],
    mapping: { I1: "C1", I2: "C2", I3: "C1", I4: "C2" },
  },
  {
    ...base(14, LESSON_C),
    type: "categories",
    stem: "Question de démonstration n°14 : répartir les éléments.",
    categories: [
      { id: "C1", text: "Groupe A" },
      { id: "C2", text: "Groupe B" },
      { id: "C3", text: "Groupe C" },
    ],
    items: [
      { id: "I1", text: "Élément A1" },
      { id: "I2", text: "Élément B1" },
      { id: "I3", text: "Élément C1" },
      { id: "I4", text: "Élément A2" },
      { id: "I5", text: "Élément C2" },
    ],
    mapping: { I1: "C1", I2: "C2", I3: "C3", I4: "C1", I5: "C3" },
  },
  {
    ...base(15, LESSON_A),
    type: "numerique",
    stem: "Question de démonstration n°15 : saisir la valeur 42 (tolérance 0,5).",
    value: 42,
    tolerance: 0.5,
    unit: "unités",
  },
  {
    ...base(16, LESSON_B),
    type: "numerique",
    stem: "Question de démonstration n°16 : saisir la valeur 1,5 (exacte).",
    value: 1.5,
    tolerance: 0,
    unit: "u",
  },
  {
    ...base(17, LESSON_C),
    type: "image",
    stem: "Question de démonstration n°17 : quelle forme porte la lettre A ?",
    figure: figure("Figure de démonstration n°1"),
    options: [
      { id: "A", text: "Proposition A (le cercle)" },
      { id: "B", text: "Proposition B (le rectangle)" },
      { id: "C", text: "Proposition C" },
    ],
    answer: "A",
  },
  {
    ...base(18, LESSON_A),
    type: "image",
    stem: "Question de démonstration n°18 : quelle forme porte la lettre B ?",
    figure: figure("Figure de démonstration n°2"),
    options: [
      { id: "A", text: "Proposition A (le cercle)" },
      { id: "B", text: "Proposition B (le rectangle)" },
      { id: "C", text: "Proposition C" },
      { id: "D", text: "Proposition D" },
    ],
    answer: "B",
  },
];

const lessonSummary = (id: string, title: string, order: number) => ({
  id,
  title,
  order,
  aliases: [],
  available: true,
  exerciseCount: fixtureExercises.filter((item) => item.lessonId === id).length,
  pastExamCount: 0,
});

export const fixtureIndex: YearIndex = {
  faculty: "demo",
  facultyLabel: "Faculté de démonstration",
  year: "demo",
  yearLabel: "Année de démonstration",
  certifs: [
    {
      slug: "demo",
      title: "Certificat de démonstration",
      pole: "Pôle de démonstration",
      pastExams: 0,
      modules: [
        {
          slug: "module-1",
          title: "Module de démonstration 1",
          lessons: [lessonSummary(LESSON_A, "Leçon de démonstration 1", 1), lessonSummary(LESSON_B, "Leçon de démonstration 2", 2)],
        },
        {
          slug: "module-2",
          title: "Module de démonstration 2",
          lessons: [lessonSummary(LESSON_C, "Leçon de démonstration 3", 1)],
        },
      ],
    },
  ],
};
