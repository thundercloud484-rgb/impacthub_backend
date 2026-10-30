"use client";

import { CalendarDays } from "lucide-react";

export default function EventsPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <div className="card text-center py-16">
        <CalendarDays className="h-12 w-12 mx-auto mb-4 text-civic-500" />
        <h1 className="font-display font-bold text-2xl text-slate-800">
          Events
        </h1>
        <p className="text-sm text-slate-400 mt-2">
          No events are available yet.
        </p>
      </div>
    </div>
  );
}
