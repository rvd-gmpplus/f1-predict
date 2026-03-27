"use client";

import { cn } from "@/lib/utils";

interface Tab {
  id: string;
  label: string;
}

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (id: string) => void;
}

export function Tabs({ tabs, activeTab, onTabChange }: TabsProps) {
  return (
    <div className="flex gap-1 bg-f1-surface rounded-xl p-1 border border-f1-border">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            "flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200",
            activeTab === tab.id
              ? "bg-f1-red text-white shadow-lg shadow-f1-red/20"
              : "text-f1-muted hover:text-white",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
