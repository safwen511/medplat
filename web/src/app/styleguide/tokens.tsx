"use client";

import { Flame, Target, Timer } from "lucide-react";

import { CertifDeck } from "@/components/cards/certif-deck";
import { certifTheme } from "@/components/cards/themes";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { Progress } from "@/components/ui/progress";
import { ProgressRing } from "@/components/ui/progress-ring";
import { StatTile } from "@/components/ui/stat-tile";

const COLORS = [
  { name: "background", label: "Page (niveau 1)" },
  { name: "panel", label: "Panneau (niveau 2)" },
  { name: "surface", label: "Carte (niveau 3)" },
  { name: "surface-muted", label: "Carte, état" },
  { name: "border", label: "Bordure" },
  { name: "foreground", label: "Texte" },
  { name: "muted", label: "Texte secondaire" },
  { name: "primary", label: "Accent" },
  { name: "highyield", label: "Tombe souvent" },
  { name: "correct", label: "Bonne réponse" },
  { name: "wrong", label: "Mauvaise réponse" },
];

const DEPTHS = [
  { className: "shadow-depth-1", label: "Profondeur 1" },
  { className: "shadow-depth-2", label: "Profondeur 2" },
  { className: "shadow-depth-3", label: "Profondeur 3" },
  { className: "shadow-glow", label: "Lueur (focus, survol)" },
  { className: "shadow-glow-strong", label: "Lueur forte (sélection)" },
];

export function Tokens() {
  return (
    <div className="flex flex-col gap-12">
      <Panel title="Couleurs" subtitle="Thème actif — change-le avec le bouton du haut (sombre par défaut).">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {COLORS.map((color) => (
            <div
              key={color.name}
              className="flex items-center gap-3 rounded-card border border-border bg-surface p-3"
            >
              <span
                className="size-10 shrink-0 rounded-control border border-border"
                style={{ background: `var(--${color.name})` }}
              />
              <span className="flex flex-col text-sm">
                <span className="font-medium">{color.label}</span>
                <code className="text-xs text-muted">--{color.name}</code>
              </span>
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="Profondeur et lueur"
        subtitle="Ombres pour les cartes, lueur seulement pour le focus, le survol et la sélection."
      >
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-5">
          {DEPTHS.map((depth) => (
            <div
              key={depth.label}
              className={`flex h-24 items-end rounded-card bg-surface p-3 text-sm ${depth.className}`}
            >
              {depth.label}
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Rayons, espacements, mouvement">
        <div className="grid gap-6 sm:grid-cols-3">
          <div className="flex flex-col gap-3 text-sm">
            <div className="h-14 rounded-panel border border-border bg-surface px-3 py-2">
              Panneau · 20 px
            </div>
            <div className="h-14 rounded-card border border-border bg-surface px-3 py-2">Carte · 16 px</div>
            <div className="h-14 rounded-control border border-border bg-surface px-3 py-2">
              Contrôle · 12 px
            </div>
          </div>
          <div className="flex flex-col gap-2 text-sm text-muted">
            <p>Échelle 4/8 px. Panneaux : 24–32 px de marge intérieure.</p>
            <p>Entre deux panneaux : 48–64 px.</p>
            <div className="flex items-end gap-2">
              {[4, 8, 16, 24, 32, 48, 64].map((step) => (
                <span key={step} className="flex flex-col items-center gap-1">
                  <span className="w-3 rounded-sm bg-primary" style={{ height: step }} />
                  <span className="text-xs">{step}</span>
                </span>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2 text-sm text-muted">
            <p>Rapide 150 ms · base 200 ms · lent 300 ms ; transform et opacity seulement.</p>
            <p>Réduction des animations respectée : pas d&apos;inclinaison, retournement instantané.</p>
          </div>
        </div>
      </Panel>

      <Panel title="Composants" subtitle="Tuiles de statistiques, anneau, barre, bouton, dossier de certif.">
        <div className="grid gap-4 sm:grid-cols-3">
          <StatTile
            value="1 284"
            label="Questions répondues"
            icon={<Target className="size-4" aria-hidden />}
          />
          <StatTile value="87 %" label="Bonnes réponses" hint="sur les 30 derniers jours" />
          <StatTile
            value="12"
            label="Jours d'affilée"
            icon={<Flame className="size-4 text-highyield" aria-hidden />}
          />
        </div>
        <div className="flex flex-wrap items-center gap-8">
          <ProgressRing value={65} label="Objectif du jour">
            13/20
          </ProgressRing>
          <div className="flex min-w-60 flex-1 flex-col gap-3">
            <div className="flex justify-between text-sm">
              <span>Neurologie</span>
              <span className="numeral text-muted">8 / 26</span>
            </div>
            <Progress value={31} />
            <div className="flex items-center gap-2 text-sm text-muted">
              <Timer className="size-4" aria-hidden /> Temps médian par question :{" "}
              <span className="numeral text-foreground">14 s</span>
            </div>
          </div>
          <Button size="lg" className="shadow-glow">
            Commencer un quiz
          </Button>
        </div>
        <div className="max-w-sm">
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
      </Panel>
    </div>
  );
}
