"use client";

import { motion, useMotionValue, useReducedMotion, useSpring, useTransform } from "motion/react";
import { useState, type PointerEvent } from "react";

import { CertifArt } from "@/components/cards/certif-art";
import { certifTheme } from "@/components/cards/themes";
import { SPRING_SOFT } from "@/lib/motion";

const CARDS = [
  { slug: "c-neurologie", pole: "C", title: "Accidents vasculaires cérébraux", certif: "Neurologie", n: 4 },
  { slug: "a-pneumo", pole: "A", title: "Embolie pulmonaire", certif: "Pneumologie", n: 7 },
  { slug: "c-ophtalmologie", pole: "C", title: "Glaucomes", certif: "Ophtalmologie", n: 2 },
  { slug: "a-cardio", pole: "A", title: "Insuffisance cardiaque", certif: "Cardiologie", n: 15 },
];

// Fanned (rest) and spread (open) positions, back card first.
const REST = [
  { x: -54, y: 18, r: -12 },
  { x: -18, y: 4, r: -4 },
  { x: 18, y: 4, r: 4 },
  { x: 54, y: 18, r: 12 },
];
const OPEN = [
  { x: -150, y: 30, r: -14 },
  { x: -52, y: -6, r: -5 },
  { x: 52, y: -6, r: 5 },
  { x: 150, y: 30, r: 14 },
];

/**
 * The hero's hand of course cards. A hovering pointer (mouse or stylus) tilts the hand and fans
 * it open; on touch screens a tap opens and closes it.
 */
export function HeroDeck() {
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);
  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], [-10, 10]), SPRING_SOFT);
  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], [8, -8]), SPRING_SOFT);

  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "touch" || reduce) return;
    const rect = event.currentTarget.getBoundingClientRect();
    px.set((event.clientX - rect.left) / rect.width - 0.5);
    py.set((event.clientY - rect.top) / rect.height - 0.5);
  };

  return (
    <div
      className="relative flex h-[22rem] w-full items-center justify-center [perspective:1400px] sm:h-[26rem]"
      onPointerMove={onMove}
      onPointerEnter={(event) => event.pointerType !== "touch" && setOpen(true)}
      onPointerLeave={(event) => {
        if (event.pointerType === "touch") return;
        setOpen(false);
        px.set(0);
        py.set(0);
      }}
    >
      <button
        type="button"
        aria-label={open ? "Refermer l'éventail de cours" : "Ouvrir l'éventail de cours"}
        aria-pressed={open}
        onClick={() => setOpen((value) => !value)}
        className="absolute inset-0 z-10 cursor-pointer rounded-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <motion.div style={{ rotateX, rotateY, transformStyle: "preserve-3d" }} className="relative h-full w-full">
        {CARDS.map((card, index) => {
          const theme = certifTheme(card);
          const place = (open ? OPEN : REST)[index];
          return (
            <motion.div
              key={card.slug}
              initial={reduce ? false : { opacity: 0, y: 60, rotate: 0 }}
              animate={{ opacity: 1, x: place.x, y: place.y, rotate: place.r }}
              transition={{ ...SPRING_SOFT, delay: reduce ? 0 : 0.15 + index * 0.08 }}
              className="absolute top-1/2 left-1/2 -mt-[8.5rem] -ml-[5.75rem] w-[11.5rem] sm:-mt-[9.75rem] sm:-ml-[6.5rem] sm:w-[13rem]"
              style={{ zIndex: index === 3 ? 4 : index }}
            >
              <div className="overflow-hidden rounded-[18px] border border-white/10 bg-surface shadow-depth-3">
                <CertifArt theme={theme} variant={card.n} emblemSize={30} className="aspect-[4/3] w-full">
                  <span className="absolute top-2 left-2 rounded-md bg-black/30 px-1.5 py-0.5 text-[11px] font-semibold text-white tabular-nums backdrop-blur-sm">
                    {card.n}
                  </span>
                </CertifArt>
                <div className="flex flex-col gap-1 p-3">
                  <span className="eyebrow !text-[0.625rem]">{card.certif}</span>
                  <span className="line-clamp-2 text-sm leading-snug font-semibold">{card.title}</span>
                  <span className="mt-2 flex items-center justify-between text-[11px] text-muted">
                    <span>10 exercices</span>
                    <span className="text-primary">Lu</span>
                  </span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
