"use client";

import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronDown, ChevronUp, GripVertical } from "lucide-react";
import { useId } from "react";

import type { Option, OrderingExercise } from "@/lib/content/types";
import { cn } from "@/lib/utils";

import type { Response } from "../grading";
import { Mark } from "./marks";

export function OrderingAnswer({
  exercise,
  response,
  onChange,
  submitted,
}: {
  exercise: OrderingExercise;
  response: Extract<Response, { type: "ordre" }>;
  onChange: (response: Response) => void;
  submitted: boolean;
}) {
  const dndId = useId();
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const byId = Object.fromEntries(exercise.items.map((item) => [item.id, item]));
  const order = response.order;

  const move = (from: number, to: number) => {
    if (submitted || to < 0 || to >= order.length) return;
    onChange({ type: "ordre", order: arrayMove(order, from, to) });
  };
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    move(order.indexOf(String(active.id)), order.indexOf(String(over.id)));
  };

  return (
    <div className="flex flex-col gap-3">
      {!submitted && (
        <p className="text-sm text-muted">
          Glisse les éléments avec la poignée, ou utilise les flèches pour les déplacer.
        </p>
      )}
      <DndContext
        id={dndId}
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={onDragEnd}
        accessibility={{
          screenReaderInstructions: {
            draggable:
              "Pour déplacer un élément, appuie sur espace ou entrée, utilise les flèches, puis appuie de nouveau sur espace ou entrée pour le déposer. Échap pour annuler.",
          },
        }}
      >
        <SortableContext items={order} strategy={verticalListSortingStrategy}>
          <ol className="flex flex-col gap-2">
            {order.map((id, index) => (
              <SortableRow
                key={id}
                item={byId[id]}
                index={index}
                count={order.length}
                submitted={submitted}
                correctIndex={exercise.order.indexOf(id)}
                onMove={(to) => move(index, to)}
              />
            ))}
          </ol>
        </SortableContext>
      </DndContext>
    </div>
  );
}

function SortableRow({
  item,
  index,
  count,
  submitted,
  correctIndex,
  onMove,
}: {
  item: Option;
  index: number;
  count: number;
  submitted: boolean;
  correctIndex: number;
  onMove: (to: number) => void;
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
    disabled: submitted,
  });
  const ok = correctIndex === index;
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "flex items-center gap-2 rounded-card border bg-surface px-2 py-2 text-[0.95rem]",
        isDragging ? "relative z-10 border-primary shadow-lg" : "border-border",
        submitted && (ok ? "border-correct bg-correct-soft" : "border-wrong bg-wrong-soft"),
      )}
    >
      {!submitted ? (
        <button
          ref={setActivatorNodeRef}
          type="button"
          {...attributes}
          {...listeners}
          aria-label={`Déplacer « ${item.text} »`}
          className="flex size-9 shrink-0 cursor-grab touch-none items-center justify-center rounded-md text-muted hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
        >
          <GripVertical className="size-4" aria-hidden />
        </button>
      ) : (
        <Mark state={ok ? "correct" : "wrong"} className="mx-1.5" />
      )}
      <span className="w-6 shrink-0 text-center text-sm font-semibold text-muted">{index + 1}</span>
      <span className="flex-1 text-foreground">{item.text}</span>
      {submitted && !ok && (
        <span className="shrink-0 rounded-md bg-surface px-2 py-0.5 text-xs text-muted">
          place attendue : <span className="font-semibold text-foreground">{correctIndex + 1}</span>
        </span>
      )}
      {!submitted && (
        <span className="flex shrink-0 gap-0.5">
          <button
            type="button"
            onClick={() => onMove(index - 1)}
            disabled={index === 0}
            aria-label={`Monter « ${item.text} »`}
            className="flex size-9 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-30"
          >
            <ChevronUp className="size-4" aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => onMove(index + 1)}
            disabled={index === count - 1}
            aria-label={`Descendre « ${item.text} »`}
            className="flex size-9 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-30"
          >
            <ChevronDown className="size-4" aria-hidden />
          </button>
        </span>
      )}
    </li>
  );
}
