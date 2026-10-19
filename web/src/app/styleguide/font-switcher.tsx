"use client";

import { Check } from "lucide-react";
import { useState, type CSSProperties } from "react";

import { CertifDeck } from "@/components/cards/certif-deck";
import { certifTheme } from "@/components/cards/themes";

export interface Pairing {
  id: string;
  label: string;
  display: string;
  body: string;
}

type Mode = "dark" | "light";

// Preview-only console colours (step 2 turns these into the real tokens).
const CONSOLE: Record<Mode, Record<string, string>> = {
  dark: {
    page: "#070b16",
    panel: "#0f1626",
    card: "#162036",
    border: "#22304d",
    text: "#e6ecf7",
    muted: "#8d9ab3",
    accent: "#5cc8d6",
  },
  light: {
    page: "#eef2f8",
    panel: "#ffffff",
    card: "#f5f7fb",
    border: "#d9e0ec",
    text: "#121a2b",
    muted: "#5b6782",
    accent: "#0f7c8c",
  },
};

function Sample({ pairing, mode }: { pairing: Pairing; mode: Mode }) {
  const c = CONSOLE[mode];
  const vars = {
    "--font-source-serif": pairing.display,
    "--font-public-sans": pairing.body,
    fontFamily: pairing.body,
    background: c.page,
    color: c.text,
  } as CSSProperties;
  const display = { fontFamily: pairing.display } as CSSProperties;
  const panel = { background: c.panel, border: `1px solid ${c.border}` } as CSSProperties;
  return (
    <section style={vars} className="flex flex-col gap-6 rounded-[20px] p-5 sm:p-8">
      <p className="text-xs tracking-[0.2em] uppercase" style={{ color: c.muted }}>
        {pairing.label}
      </p>

      <div style={panel} className="flex flex-col gap-3 rounded-[18px] p-6">
        <h1 style={display} className="text-4xl leading-tight font-semibold">
          Révise tes certifs, à ton rythme
        </h1>
        <h2 style={display} className="text-2xl font-semibold">
          Pôle C · Neurologie et psychiatrie
        </h2>
        <h3 style={display} className="text-lg font-medium">
          Épilepsies de l&apos;enfant : démarche diagnostique
        </h3>
        <p className="max-w-prose text-[1.0625rem] leading-relaxed" style={{ color: c.text }}>
          Après ta réponse, une explication te montre le raisonnement : « devant une céphalée brutale, penser
          d&apos;abord à l&apos;hémorragie méningée ». Ça, c&apos;est l&apos;essentiel à retenir — même à J-3
          du certif. Où ? Là. Déjà vu, révisé, maîtrisé ; ç, œ, æ, à, è, ù, ï, ô.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {[
          { value: "87 %", label: "Bonnes réponses" },
          { value: "1 284", label: "Questions répondues" },
          { value: "12 j", label: "Série de jours" },
        ].map((tile) => (
          <div
            key={tile.label}
            style={{ background: c.card, border: `1px solid ${c.border}` }}
            className="flex flex-col gap-1 rounded-[16px] p-5"
          >
            <span style={display} className="text-4xl font-semibold tabular-nums">
              {tile.value}
            </span>
            <span className="text-sm" style={{ color: c.muted }}>
              {tile.label}
            </span>
          </div>
        ))}
      </div>

      <div className="max-w-sm" style={{ "--font-source-serif": pairing.display } as CSSProperties}>
        <CertifDeck
          href="#"
          title="Neurologie"
          fullTitle="Certificat intégré de neurologie"
          pole="C"
          theme={certifTheme({ slug: "c-neurologie", pole: "C" })}
          counts={{ non_lu: 18, lu: 4, revise_1: 2, revise_2: 1, maitrise: 1 }}
          available={8}
          precision={74}
          answered={46}
        />
      </div>

      <div style={panel} className="flex flex-col gap-4 rounded-[18px] p-6">
        <p className="text-sm" style={{ color: c.muted }}>
          Question 4 / 10
        </p>
        <p style={display} className="text-xl leading-snug font-medium">
          Devant une première crise convulsive fébrile chez un nourrisson de 14 mois, quel élément impose une
          ponction lombaire ?
        </p>
        {[
          "Une fièvre supérieure à 39 °C",
          "Des signes méningés à l'examen",
          "Une crise de plus de 5 minutes",
          "Des antécédents familiaux d'épilepsie",
        ].map((option, i) => (
          <div
            key={option}
            className="flex min-h-14 items-center gap-3 rounded-[14px] px-4 text-[1.0625rem]"
            style={{
              border: `1px solid ${i === 1 ? c.accent : c.border}`,
              background: i === 1 ? `${c.accent}1f` : "transparent",
            }}
          >
            <span
              className="flex size-5 items-center justify-center rounded-full"
              style={{ border: `1.5px solid ${i === 1 ? c.accent : c.muted}` }}
            >
              {i === 1 && <Check className="size-3" style={{ color: c.accent }} />}
            </span>
            {option}
          </div>
        ))}
      </div>
    </section>
  );
}

export function FontSwitcher({ pairings }: { pairings: Pairing[] }) {
  const [selected, setSelected] = useState<string>("all");
  const [mode, setMode] = useState<Mode>("dark");
  const shown = selected === "all" ? pairings : pairings.filter((pairing) => pairing.id === selected);
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <header className="flex flex-col gap-4">
        <h1 className="text-2xl">Typographie : comparaison</h1>
        <p className="max-w-2xl text-muted">
          Trois associations titre + texte, chacune avec des titres, un paragraphe accentué, des tuiles de
          statistiques, un dossier de certif et une question de quiz. Choisis-en une.
        </p>
        <div className="flex flex-wrap gap-2">
          {[
            { id: "all", label: "Comparer les 3" },
            ...pairings.map((p) => ({ id: p.id, label: `(${p.id}) ${p.label}` })),
          ].map((option) => (
            <button
              key={option.id}
              type="button"
              aria-pressed={selected === option.id}
              onClick={() => setSelected(option.id)}
              className="min-h-12 rounded-full border border-border px-4 text-sm aria-pressed:border-primary aria-pressed:bg-primary-soft aria-pressed:text-primary"
            >
              {option.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setMode(mode === "dark" ? "light" : "dark")}
            className="min-h-12 rounded-full border border-border px-4 text-sm"
          >
            Aperçu : {mode === "dark" ? "sombre" : "clair"}
          </button>
        </div>
      </header>
      <div className={selected === "all" ? "grid gap-6 xl:grid-cols-3" : "flex flex-col gap-6"}>
        {shown.map((pairing) => (
          <Sample key={pairing.id} pairing={pairing} mode={mode} />
        ))}
      </div>
    </div>
  );
}
