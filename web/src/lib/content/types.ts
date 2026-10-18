// Static course content produced by scripts/export_web_content.py from the pipeline
// (data/<year>/catalog, lessons, exercises, figures). Generated content stays a draft until a
// medical reviewer accepts it; `status` is shown to students.

export type ReviewStatus = "draft_unreviewed" | "reviewed";

export interface YearIndex {
  faculty: string; // "sfax"
  facultyLabel: string; // "Faculté de Médecine de Sfax"
  year: string; // "dcem1"
  yearLabel: string; // "DCEM1 — 3e année"
  certifs: CertifSummary[];
}

export interface CertifSummary {
  slug: string; // "d-pediatrie"
  title: string;
  pole: string;
  modules: ModuleSummary[];
  pastExams: number;
}

export interface ModuleSummary {
  slug: string;
  title: string;
  lessons: LessonSummary[];
}

export interface LessonSummary {
  id: string; // "d-pediatrie.pediatrie.asthme"
  title: string;
  order: number;
  aliases: string[];
  available: boolean; // a reconstructed, validated lesson exists
  exerciseCount: number;
  pastExamCount: number; // past papers linked to this lesson (high-yield signal)
}

export interface SourceRef {
  key: string; // "S1"
  label: string;
  role: "official_slides" | "official_polycopie" | "student_summary" | "tips" | "tutorial" | "reference_book";
}

export interface Figure {
  source: string; // "S1"
  page: number;
  src: string; // public URL path
  width: number;
  height: number;
}

export interface Lesson {
  id: string;
  title: string;
  certif: string;
  certifTitle: string;
  module: string;
  status: ReviewStatus;
  markdown: string; // lesson.md body (front matter removed)
  sources: SourceRef[];
  figures: Figure[];
}

// Exercises ---------------------------------------------------------------------------------

interface ExerciseBase {
  id: string; // "<lesson_id>#q3"
  lessonId: string;
  stem: string;
  hints: [string, string, string]; // what is asked, what to eliminate, the rule
  explanation: string;
  citations: string; // "[S1 p.3; S2 p.10]"
  highYield: boolean;
  difficulty: 1 | 2 | 3;
}

export interface Option {
  id: string; // "A"
  text: string;
}

export interface QcmExercise extends ExerciseBase {
  type: "qcm";
  options: Option[];
  answer: string;
}

export interface QrmExercise extends ExerciseBase {
  type: "qrm";
  options: Option[];
  answer: string[];
}

export interface TrueFalseExercise extends ExerciseBase {
  type: "vrai_faux";
  answer: boolean;
}

export interface FillBlankExercise extends ExerciseBase {
  type: "texte_a_trous";
  text: string; // "La PL se fait en {{1}} …"
  blanks: Record<string, string[]>; // accepted answers per blank, compared case- and accent-insensitively
}

export interface MatchingExercise extends ExerciseBase {
  type: "association";
  left: Option[];
  right: Option[];
  pairs: Record<string, string>; // left id -> right id
}

export interface OrderingExercise extends ExerciseBase {
  type: "ordre";
  items: Option[]; // shown shuffled
  order: string[]; // correct order of item ids
}

export interface CategorizingExercise extends ExerciseBase {
  type: "categories";
  categories: Option[];
  items: Option[];
  mapping: Record<string, string>; // item id -> category id
}

export interface NumericExercise extends ExerciseBase {
  type: "numerique";
  value: number;
  tolerance: number;
  unit: string;
}

export interface ImageExercise extends ExerciseBase {
  type: "image";
  figure: Figure;
  options: Option[];
  answer: string;
}

export type Exercise =
  | QcmExercise
  | QrmExercise
  | TrueFalseExercise
  | FillBlankExercise
  | MatchingExercise
  | OrderingExercise
  | CategorizingExercise
  | NumericExercise
  | ImageExercise;

export interface ExerciseSet {
  lessonId: string;
  status: ReviewStatus;
  items: Exercise[];
}
