"use client";

import { ArrowLeft, Flame, ListChecks, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { CertifSummary, LessonSummary, YearIndex } from "@/lib/content/types";

import {
  accuracy,
  certifLessons,
  formatDate,
  formatPercent,
  groupBy,
  lessonHref,
  STATUS_STEPS,
  useStudentData,
  type StudentData,
} from "./data";
import { LabelledProgress, PoleBadge } from "./parts";
import { StatusControl } from "./status-control";

const HIGH_YIELD_THRESHOLD = 3;

export function CertifPage({ index, certif }: { index: YearIndex; certif: CertifSummary }) {
  const data = useStudentData(index);
  const lessons = certifLessons(certif);
  const byLesson = useMemo(() => groupBy(data.attempts, (item) => item.lessonId), [data.attempts]);

  const count = (minimum: number) =>
    lessons.filter((lesson) => {
      const record = data.progress[lesson.id];
      return record && STATUS_STEPS.indexOf(record.status) >= minimum;
    }).length;
  const read = count(0);
  const revised = count(1);
  const mastered = count(3);
  const percent = (value: number) => (lessons.length ? Math.round((value / lessons.length) * 100) : 0);
  const available = lessons.filter((lesson) => lesson.available).length;
  const certifAttempts = lessons.flatMap((lesson) => byLesson.get(lesson.id) ?? []);
  const score = accuracy(certifAttempts);
  const yearHref = `/${index.faculty}/${index.year}`;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Link href={yearHref} className="inline-flex items-center gap-1 self-start text-sm text-muted hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden />
          Mes certifs
        </Link>
        <div className="flex items-start gap-3">
          <PoleBadge pole={certif.pole} className="mt-1 shrink-0" />
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">{certif.title}</h1>
            <p className="text-sm text-muted">
              {index.yearLabel} · {lessons.length} cours · {available} disponible{available > 1 ? "s" : ""}
              {certif.pastExams > 0 && ` · ${certif.pastExams} examens archivés`}
            </p>
          </div>
        </div>
      </div>

      <Card className="grid gap-5 p-5 md:grid-cols-[1fr_auto] md:items-end">
        <div className="grid gap-4 sm:grid-cols-3">
          <LabelledProgress id="certif-read" label="Lus" value={percent(read)} detail={`${read} / ${lessons.length}`} />
          <LabelledProgress
            id="certif-revised"
            label="Révisés"
            value={percent(revised)}
            detail={`${revised} / ${lessons.length}`}
          />
          <LabelledProgress
            id="certif-mastered"
            label="Maîtrisés"
            value={percent(mastered)}
            detail={`${mastered} / ${lessons.length}`}
            tone="correct"
          />
        </div>
        <div className="flex flex-col gap-2 md:items-end">
          <p className="text-sm text-muted">
            Précision : <span className="font-medium text-foreground tabular-nums">{formatPercent(score.percent)}</span>
            {score.total > 0 && ` sur ${score.total} réponses`}
          </p>
          <Button asChild>
            <Link href={`${yearHref}/quiz?certif=${encodeURIComponent(certif.slug)}`}>
              <PlayCircle aria-hidden />
              Quiz sur ce certif
            </Link>
          </Button>
        </div>
      </Card>

      <section aria-labelledby="fiche-title" className="flex flex-col gap-4">
        <h2 id="fiche-title" className="flex items-center gap-2 text-lg font-semibold">
          <ListChecks className="size-5 text-primary" aria-hidden />
          Fiche de suivi
        </h2>
        {certif.modules.map((mod) => (
          <Card key={mod.slug} className="overflow-hidden">
            <h3 className="border-b border-border bg-surface-muted/50 px-4 py-3 text-sm font-semibold">
              {mod.title}
              <span className="ml-2 font-normal text-muted">{mod.lessons.length} cours</span>
            </h3>
            <ol className="divide-y divide-border">
              {[...mod.lessons]
                .sort((a, b) => a.order - b.order)
                .map((lesson) => (
                  <LessonRow
                    key={lesson.id}
                    index={index}
                    lesson={lesson}
                    data={data}
                    attempts={byLesson.get(lesson.id) ?? []}
                  />
                ))}
            </ol>
          </Card>
        ))}
      </section>
    </div>
  );
}

function LessonRow({
  index,
  lesson,
  data,
  attempts,
}: {
  index: YearIndex;
  lesson: LessonSummary;
  data: StudentData;
  attempts: StudentData["attempts"];
}) {
  const record = data.progress[lesson.id];
  const score = accuracy(attempts);

  return (
    <li className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <span className="mt-0.5 w-6 shrink-0 text-right text-sm text-muted tabular-nums">{lesson.order}</span>
        <div className="flex min-w-0 flex-col gap-1">
          {lesson.available ? (
            <Link href={lessonHref(index, lesson)} className="font-medium text-foreground hover:text-primary hover:underline">
              {lesson.title}
            </Link>
          ) : (
            <span className="text-muted">
              {lesson.title}
              <span className="ml-2 text-xs italic">bientôt disponible</span>
            </span>
          )}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
            {lesson.pastExamCount >= HIGH_YIELD_THRESHOLD ? (
              <Badge tone="highyield">
                <Flame aria-hidden />
                Tombe souvent · {lesson.pastExamCount} examens
              </Badge>
            ) : lesson.pastExamCount > 0 ? (
              <Badge>
                {lesson.pastExamCount} examen{lesson.pastExamCount > 1 ? "s" : ""}
              </Badge>
            ) : null}
            <span>
              {lesson.exerciseCount} exercice{lesson.exerciseCount > 1 ? "s" : ""}
            </span>
            <span>
              Précision <span className="text-foreground tabular-nums">{formatPercent(score.percent)}</span>
              {score.total > 0 && ` (${score.total})`}
            </span>
            {record && !data.loading && <span>Mis à jour le {formatDate(record.updatedAt, data.now)}</span>}
          </div>
        </div>
      </div>
      <div className="pl-9 sm:pl-0">
        {data.loading ? (
          <div className="h-8 w-40 animate-pulse rounded-full bg-surface-muted" aria-hidden />
        ) : (
          <StatusControl
            status={record?.status ?? null}
            lessonTitle={lesson.title}
            onChange={(status) => data.setStatus(lesson.id, status)}
          />
        )}
      </div>
    </li>
  );
}
