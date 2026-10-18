"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { Children, type ReactNode } from "react";

export function CompareTabs({ labels, children }: { labels: string[]; children: ReactNode }) {
  const panels = Children.toArray(children);
  return (
    <Tabs.Root defaultValue="0" className="flex flex-col gap-4">
      <Tabs.List className="flex flex-wrap gap-x-6 border-b border-border" aria-label="Versions">
        {labels.map((label, index) => (
          <Tabs.Trigger
            key={label}
            value={String(index)}
            className="-mb-px min-h-12 border-b-2 border-transparent text-sm text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=active]:border-primary data-[state=active]:text-foreground"
          >
            {label}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      {panels.map((panel, index) => (
        <Tabs.Content key={index} value={String(index)} forceMount className="data-[state=inactive]:hidden">
          {panel}
        </Tabs.Content>
      ))}
    </Tabs.Root>
  );
}
