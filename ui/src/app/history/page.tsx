"use client";

import { Card, CardContent } from "@/components/ui/card";
import { ClockIcon } from "@/components/icons";

export default function HistoryPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">Processing History</h2>
        <p className="mt-1 text-sm text-slate-500">Documents analysed in this session</p>
      </div>

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
            <ClockIcon className="h-6 w-6 text-slate-400" />
          </div>
          <h3 className="text-base font-semibold text-slate-700">No documents processed yet</h3>
          <p className="mt-1 max-w-sm text-sm text-slate-400">
            Start a new triage analysis to see results here. History is stored in-session and resets on page reload.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
