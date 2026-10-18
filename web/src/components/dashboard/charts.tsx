"use client";

import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, type TooltipContentProps } from "recharts";

// One simple chart, in the single accent colour. Axes recessive, no grid; a screen-reader table
// sits next to it.

export interface ActivityRow {
  key: string;
  label: string; // "12 oct."
  count: number;
}

function ActivityTooltip({ active, payload }: Pick<TooltipContentProps<number, string>, "active" | "payload">) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as ActivityRow;
  return (
    <div className="rounded-card border border-border bg-surface px-3 py-2 text-sm">
      <span className="text-foreground">{row.label}</span>
      <span className="text-muted tabular-nums">
        {" "}
        · {row.count} question{row.count > 1 ? "s" : ""}
      </span>
    </div>
  );
}

export function ActivityChart({ rows }: { rows: ActivityRow[] }) {
  return (
    <div className="h-40" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 4, right: 16, bottom: 0, left: 16 }} barCategoryGap={2}>
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--muted)", fontSize: 13 }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            interval={9}
          />
          <Tooltip cursor={{ fill: "var(--surface-muted)" }} content={(props) => <ActivityTooltip active={props.active} payload={props.payload} />} />
          <Bar dataKey="count" fill="var(--primary)" radius={[2, 2, 0, 0]} maxBarSize={12} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
