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
          Glisse les éléments par la poignée, ou utilise les flèches.
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
        "flex min-h-14 items-center gap-1 rounded-card border bg-surface px-1 py-1 text-[1.0625rem] leading-snug",
        isDragging ? "relative z-10 border-primary" : "border-border",
        submitted && (ok ? "border-correct/60 bg-correct-soft" : "border-wrong/60 bg-wrong-soft"),
      )}
    >
      {!submitted ? (
        <button
          ref={setActivatorNodeRef}
          type="button"
          {...attributes}
          {...listeners}
          aria-label={`Déplacer « ${item.text} »`}
          className="flex h-12 w-10 shrink-0 cursor-grab touch-none items-center justify-center rounded-card text-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
        >
          <GripVertical className="size-4" strokeWidth={1.5} aria-hidden />
        </button>
      ) : (
        <Mark state={ok ? "correct" : "wrong"} className="mx-2" />
      )}
      <span className="w-6 shrink-0 text-center text-sm tabular-nums text-muted">{index + 1}</span>
      <span className="flex-1 py-2 text-foreground">{item.text}</span>
      {submitted && !ok && (
        <span className="shrink-0 px-2 text-sm text-muted">
          attendu : <span className="font-medium text-foreground">{correctIndex + 1}</span>
        </span>
      )}
      {!submitted && (
        <span className="flex shrink-0 gap-0.5">
          <button
            type="button"
            onClick={() => onMove(index - 1)}
            disabled={index === 0}
            aria-label={`Monter « ${item.text} »`}
            className="flex h-12 w-10 items-center justify-center rounded-card text-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-30"
          >
            <ChevronUp className="size-5" strokeWidth={1.5} aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => onMove(index + 1)}
            disabled={index === count - 1}
            aria-label={`Descendre « ${item.text} »`}
            className="flex h-12 w-10 items-center justify-center rounded-card text-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-30"
          >
            <ChevronDown className="size-5" strokeWidth={1.5} aria-hidden />
          </button>
        </span>
      )}
    </li>
  );
}
