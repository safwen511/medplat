"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";

// Single-series charts: one hue (--primary), recessive grid and axes in token inks, text never in
// the series color. Every chart has a screen-reader table next to it.

const tick = { fill: "var(--muted)", fontSize: 12 };

function ChartTooltip({
  active,
  payload,
  format,
}: Pick<TooltipContentProps<number, string>, "active" | "payload"> & {
  format: (row: Record<string, unknown>) => { title: string; lines: string[] };
}) {
  if (!active || !payload?.length) return null;
  const { title, lines } = format(payload[0].payload as Record<string, unknown>);
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-foreground">{title}</p>
      {lines.map((line) => (
        <p key={line} className="text-muted tabular-nums">
          {line}
        </p>
      ))}
    </div>
  );
}

export interface CertifAccuracyRow {
  label: string;
  title: string;
  percent: number;
  total: number;
}

export function CertifAccuracyChart({ rows }: { rows: CertifAccuracyRow[] }) {
  const height = rows.length * 40 + 32;
  return (
    <div style={{ height }} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 0 }} barCategoryGap={10}>
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis
            type="number"
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tick={tick}
            tickFormatter={(value: number) => `${value} %`}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={116}
            tick={tick}
            axisLine={false}
            tickLine={false}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: "var(--surface-muted)" }}
            content={(props) => (
              <ChartTooltip
                active={props.active}
                payload={props.payload}
                format={(row) => ({
                  title: String(row.title),
                  lines: [`Précision ${row.percent} %`, `${row.total} réponses`],
                })}
              />
            )}
          />
          <Bar dataKey="percent" fill="var(--primary)" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false}>
            <LabelList
              dataKey="percent"
              position="right"
              formatter={(value) => `${value} %`}
              style={{ fill: "var(--foreground)", fontSize: 12 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface ActivityRow {
  key: string;
  label: string; // "12 oct."
  count: number;
}

export function ActivityChart({ rows }: { rows: ActivityRow[] }) {
  return (
    <div className="h-56" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: -20 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="label" tick={tick} axisLine={false} tickLine={false} interval={6} minTickGap={8} />
          <YAxis allowDecimals={false} tick={tick} axisLine={false} tickLine={false} width={44} />
          <Tooltip
            cursor={{ fill: "var(--surface-muted)" }}
            content={(props) => (
              <ChartTooltip
                active={props.active}
                payload={props.payload}
                format={(row) => ({
                  title: String(row.label),
                  lines: [`${row.count} question${Number(row.count) > 1 ? "s" : ""}`],
                })}
              />
            )}
          />
          <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={14} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
