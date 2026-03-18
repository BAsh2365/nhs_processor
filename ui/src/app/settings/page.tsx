"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchHealth, type HealthStatus } from "@/lib/api";
import { ShieldCheckIcon, CpuIcon, LockIcon, ServerIcon, DocumentIcon } from "@/components/icons";

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">Settings</h2>
        <p className="mt-1 text-sm text-slate-500">System configuration and compliance status</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CpuIcon className="h-4 w-4 text-slate-400" /> AI Models
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Inference</span>
              <Badge variant="secondary" className="bg-green-50 text-green-700 border-green-200 border">Local Only</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">GPU</span>
              <Badge variant="secondary">
                {health?.cuda_available ? health.gpu_info?.device_name || "Active" : "CPU Mode"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Cached Processors</span>
              <Badge variant="secondary">{health?.processor_count ?? 0}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <ShieldCheckIcon className="h-4 w-4 text-slate-400" /> Compliance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">DTAC</span>
              <Badge variant="secondary" className="bg-green-50 text-green-700 border-green-200 border">Compliant</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">PII Anonymisation</span>
              <Badge variant="secondary" className="bg-green-50 text-green-700 border-green-200 border">Enabled</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Audit Logging</span>
              <Badge variant="secondary" className="bg-green-50 text-green-700 border-green-200 border">Active</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <LockIcon className="h-4 w-4 text-slate-400" /> Security
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Authentication</span>
              <Badge variant="secondary">{health?.auth_enabled ? "Enabled" : "Disabled (Dev)"}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Rate Limiting</span>
              <Badge variant="secondary">{health?.rate_limiting ? "Active" : "Disabled"}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Limits</span>
              <span className="text-xs text-slate-500 font-mono">10/min &middot; 60/hr</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <DocumentIcon className="h-4 w-4 text-slate-400" /> Frameworks
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Available</span>
              <div className="flex gap-1">
                {health?.frameworks?.map((f) => (
                  <Badge key={f} variant="secondary" className="text-[10px]">{f}</Badge>
                )) || <Badge variant="secondary">Loading...</Badge>}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Scopes</span>
              <div className="flex gap-1">
                {health?.scopes?.map((s) => (
                  <Badge key={s} variant="secondary" className="text-[10px]">{s}</Badge>
                )) || <Badge variant="secondary">Loading...</Badge>}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">File Limit</span>
              <span className="text-xs text-slate-500 font-mono">16 MB &middot; PDF, TXT</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
