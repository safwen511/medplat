"use client";

import {
  DndContext,
  DragOverlay,
  MouseSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { GripVertical, Undo2 } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import type { Option } from "@/lib/content/types";
import { cn } from "@/lib/utils";

import { Mark } from "./marks";

const POOL = "__pool__";

/**
 * Drag chips onto targets (association: one chip per target; categories: any number), with a
 * tap-to-select alternative: tap a chip, then tap its destination. Every control is a button,
 * so the board is fully keyboard operable without the drag sensors.
 */
export function PlacementBoard({
  chips,
  targets,
  placement,
  onChange,
  submitted,
  expected,
  capacity,
  layout,
  poolLabel,
}: {
  chips: Option[];
  targets: Option[];
  placement: Record<string, string>; // chip id -> target id
  onChange: (placement: Record<string, string>) => void;
  submitted: boolean;
  expected: Record<string, string>; // chip id -> target id
  capacity?: number;
  layout: "columns" | "buckets";
  poolLabel: string;
}) {
  const dndId = useId();
  const [selected, setSelected] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 6 } }),
  );
  const byId = Object.fromEntries(chips.map((chip) => [chip.id, chip]));
  const targetText = Object.fromEntries(targets.map((target) => [target.id, target.text]));
  const pool = chips.filter((chip) => !placement[chip.id]);
  const showPool = !submitted || pool.length > 0;

  const place = (chipId: string, targetId: string | null) => {
    if (submitted) return;
    const next = { ...placement };
    delete next[chipId];
    if (targetId) {
      if (capacity) {
        const occupants = Object.keys(next).filter((id) => next[id] === targetId);
        for (const id of occupants.slice(0, Math.max(0, occupants.length - capacity + 1))) delete next[id];
      }
      next[chipId] = targetId;
    }
    onChange(next);
    setSelected(null);
  };

  const onDragStart = (event: DragStartEvent) => {
    setDragging(String(event.active.id));
    setSelected(null);
  };
  const onDragEnd = (event: DragEndEvent) => {
    setDragging(null);
    const over = event.over ? String(event.over.id) : null;
    if (!over) return;
    place(String(event.active.id), over === POOL ? null : over);
  };

  const chipButton = (chip: Option, placed: boolean) => (
    <DraggableChip
      key={chip.id}
      chip={chip}
      disabled={submitted}
      selected={selected === chip.id}
      onSelect={() => setSelected((current) => (current === chip.id ? null : chip.id))}
      onReturn={placed && !submitted ? () => place(chip.id, null) : undefined}
      result={
        submitted
          ? {
              ok: placed && expected[chip.id] === placement[chip.id],
              expected: placed && capacity === 1 ? undefined : targetText[expected[chip.id]],
            }
          : undefined
      }
    />
  );

  const poolArea = (
    <DropZone id={POOL} disabled={submitted} onActivate={selected && placement[selected] ? () => place(selected, null) : undefined}>
      {(active) => (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">{poolLabel}</p>
          <div
            className={cn(
              "flex min-h-14 gap-2 rounded-card border border-dashed p-2 transition-colors duration-150",
              layout === "columns" ? "flex-col" : "flex-wrap",
              active ? "border-primary bg-primary-soft" : "border-transparent",
            )}
          >
            {pool.map((chip) => chipButton(chip, false))}
            {pool.length === 0 && <p className="px-1 py-2 text-sm text-muted">Tout est placé.</p>}
          </div>
        </div>
      )}
    </DropZone>
  );

  const targetArea = (target: Option) => {
    const placed = chips.filter((chip) => placement[chip.id] === target.id);
    const missing =
      submitted && capacity === 1 && !placed.some((chip) => expected[chip.id] === target.id)
        ? chips.find((chip) => expected[chip.id] === target.id)
        : undefined;
    const activatable = selected !== null && !submitted;
    return (
      <DropZone
        key={target.id}
        id={target.id}
        disabled={submitted}
        onActivate={selected ? () => place(selected, target.id) : undefined}
      >
        {(active) => (
          <div className="flex flex-col gap-2">
            <button
              type="button"
              disabled={submitted}
              aria-label={
                selected ? `Placer « ${byId[selected]?.text} » dans « ${target.text} »` : `Destination : ${target.text}`
              }
              className="rounded-card text-left text-base font-medium leading-snug text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default"
            >
              {target.text}
            </button>
            <div
              className={cn(
                "flex min-h-14 flex-wrap items-center gap-2 rounded-card border p-2 transition-colors duration-150",
                submitted ? "border-transparent p-0" : "border-dashed",
                !submitted && (active ? "border-primary bg-primary-soft" : activatable ? "cursor-pointer border-primary/60" : "border-border"),
              )}
            >
              {placed.map((chip) => chipButton(chip, true))}
              {placed.length === 0 && !submitted && (
                <span className="px-1 text-sm text-muted">{selected ? "Touche pour placer ici" : "Dépose ici"}</span>
              )}
              {placed.length === 0 && submitted && <span className="text-sm text-muted">Rien de placé</span>}
            </div>
            {missing && (
              <p className="text-sm text-muted">
                Attendu : <span className="text-correct">{missing.text}</span>
              </p>
            )}
          </div>
        )}
      </DropZone>
    );
  };

  return (
    <DndContext id={dndId} sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
      {!submitted && (
        <p className="mb-4 text-sm text-muted">Glisse chaque élément vers sa place, ou touche un élément puis sa destination.</p>
      )}
      {layout === "columns" ? (
        <div className={cn("grid gap-6", showPool && "grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]")}>
          <div className="flex flex-col gap-5">{targets.map(targetArea)}</div>
          {showPool && <div className="sticky top-20 self-start">{poolArea}</div>}
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {showPool && poolArea}
          <div className={cn("grid gap-5", targets.length > 2 ? "sm:grid-cols-3" : "sm:grid-cols-2")}>
            {targets.map(targetArea)}
          </div>
        </div>
      )}
      <DragOverlay dropAnimation={{ duration: 160, easing: "cubic-bezier(0.2, 0, 0, 1)" }}>
        {dragging && byId[dragging] ? <ChipFace text={byId[dragging].text} lifted /> : null}
      </DragOverlay>
    </DndContext>
  );
}

function DropZone({
  id,
  disabled,
  onActivate,
  children,
}: {
  id: string;
  disabled: boolean;
  onActivate?: () => void;
  children: (active: boolean) => ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id, disabled });
  return (
    <div ref={setNodeRef} onClick={onActivate}>
      {children(isOver)}
    </div>
  );
}

function DraggableChip({
  chip,
  disabled,
  selected,
  onSelect,
  onReturn,
  result,
}: {
  chip: Option;
  disabled: boolean;
  selected: boolean;
  onSelect: () => void;
  onReturn?: () => void;
  result?: { ok: boolean; expected?: string };
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: chip.id, disabled });
  if (result) {
    return (
      <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
        <span
          className={cn(
            "inline-flex min-h-12 items-center gap-2 rounded-card border px-3 py-2 text-base text-foreground",
            result.ok ? "border-correct/60 bg-correct-soft" : "border-wrong/60 bg-wrong-soft",
          )}
        >
          <Mark state={result.ok ? "correct" : "wrong"} />
          {chip.text}
        </span>
        {!result.ok && result.expected && (
          <span className="text-sm text-muted">
            attendu : <span className="text-correct">{result.expected}</span>
          </span>
        )}
      </span>
    );
  }
  if (disabled) return <ChipFace text={chip.text} />;
  return (
    <div className={cn("flex items-stretch gap-1", isDragging && "opacity-30")}>
      <button
        ref={setNodeRef}
        type="button"
        {...attributes}
        {...listeners}
        aria-pressed={selected}
        aria-roledescription="élément déplaçable"
        onClick={(event) => {
          event.stopPropagation();
          onSelect();
        }}
        className="rounded-card text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChipFace text={chip.text} selected={selected} />
      </button>
      {onReturn && (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onReturn();
          }}
          aria-label={`Retirer « ${chip.text} »`}
          className="flex min-h-12 w-10 items-center justify-center rounded-card text-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Undo2 className="size-4" strokeWidth={1.5} aria-hidden />
        </button>
      )}
    </div>
  );
}

function ChipFace({ text, selected, lifted }: { text: string; selected?: boolean; lifted?: boolean }) {
  return (
    <span
      className={cn(
        "flex min-h-12 cursor-grab touch-manipulation select-none items-center gap-2 rounded-card border bg-surface px-3 py-2 text-base leading-snug text-foreground transition-colors duration-150",
        selected ? "border-primary bg-primary-soft" : "border-border",
        lifted && "cursor-grabbing border-primary",
      )}
    >
      <GripVertical className="size-4 shrink-0 text-muted" strokeWidth={1.5} aria-hidden />
      {text}
    </span>
  );
}
