import {
  Apple,
  Baby,
  Bone,
  Brain,
  BrainCog,
  Droplet,
  Droplets,
  Ear,
  Eye,
  FingerprintPattern,
  FlaskConical,
  HeartPulse,
  Microscope,
  Pill,
  ScanFace,
  Scissors,
  Stethoscope,
  Venus,
  Wind,
  type LucideIcon,
} from "lucide-react";
import type { CSSProperties } from "react";

import type { CertifSummary } from "@/lib/content/types";

/** Visual identity of a certif: an OKLCH hue/chroma for the card art and a line-art emblem. */
export interface CertifTheme {
  hue: number;
  chroma: number;
  emblem: LucideIcon;
  /** Short name for the emblem, used in accessible descriptions. */
  emblemLabel: string;
}

/**
 * Keyed by the certif slug without its pole prefix ("a-cardio" -> "cardio", "cd-communs" ->
 * "communs"). Hues are spread so that certifs of one year stay distinguishable; the art always
 * carries white line-art, and the lightness is set in cards.css for both color schemes.
 */
const THEMES: Record<string, CertifTheme> = {
  cardio: { hue: 22, chroma: 0.115, emblem: HeartPulse, emblemLabel: "cœur" },
  pharmaco: { hue: 305, chroma: 0.1, emblem: Pill, emblemLabel: "gélule" },
  pharmacologie: { hue: 305, chroma: 0.1, emblem: Pill, emblemLabel: "gélule" },
  pneumo: { hue: 228, chroma: 0.1, emblem: Wind, emblemLabel: "souffle" },
  "uro-nephro": { hue: 262, chroma: 0.1, emblem: Droplets, emblemLabel: "gouttes" },
  "chir-gastro": { hue: 48, chroma: 0.11, emblem: Scissors, emblemLabel: "ciseaux" },
  hemato: { hue: 0, chroma: 0.115, emblem: Droplet, emblemLabel: "goutte" },
  infectieuse: { hue: 150, chroma: 0.1, emblem: Microscope, emblemLabel: "microscope" },
  dermatologie: { hue: 62, chroma: 0.08, emblem: FingerprintPattern, emblemLabel: "empreinte" },
  endocrinologie: { hue: 85, chroma: 0.09, emblem: FlaskConical, emblemLabel: "fiole" },
  "maxillo-facial": { hue: 205, chroma: 0.08, emblem: ScanFace, emblemLabel: "visage" },
  neurologie: { hue: 275, chroma: 0.11, emblem: Brain, emblemLabel: "cerveau" },
  ophtalmologie: { hue: 185, chroma: 0.09, emblem: Eye, emblemLabel: "œil" },
  orl: { hue: 238, chroma: 0.11, emblem: Ear, emblemLabel: "oreille" },
  psychiatrie: { hue: 332, chroma: 0.1, emblem: BrainCog, emblemLabel: "esprit" },
  communs: { hue: 130, chroma: 0.08, emblem: Apple, emblemLabel: "pomme" },
  "gyneco-obstetrique": { hue: 355, chroma: 0.1, emblem: Venus, emblemLabel: "symbole féminin" },
  orthopedie: { hue: 105, chroma: 0.07, emblem: Bone, emblemLabel: "os" },
  pediatrie: { hue: 165, chroma: 0.1, emblem: Baby, emblemLabel: "nourrisson" },
};

const POLE_FALLBACK: Record<string, number> = { A: 22, B: 150, C: 275, D: 48 };

function hashHue(value: string): number {
  let hash = 0;
  for (const char of value) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  return hash;
}

export function certifTheme(certif: Pick<CertifSummary, "slug" | "pole">): CertifTheme {
  const key = certif.slug.replace(/^[a-z]{1,2}-/, "");
  const theme = THEMES[key];
  if (theme) return theme;
  const pole = certif.pole.trim().charAt(0).toUpperCase();
  return {
    hue: POLE_FALLBACK[pole] ?? hashHue(certif.slug),
    chroma: 0.09,
    emblem: Stethoscope,
    emblemLabel: "stéthoscope",
  };
}

/** CSS custom properties consumed by cards.css. */
export function themeStyle(theme: CertifTheme): CSSProperties {
  return { "--hue": theme.hue, "--chroma": theme.chroma } as CSSProperties;
}
