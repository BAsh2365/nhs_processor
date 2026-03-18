"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { fetchHealth, fetchFrameworks, type HealthStatus, type Framework } from "@/lib/api";
import { SparklesIcon, DocumentIcon, AlertTriangleIcon, HeartIcon, ArrowRightIcon, ShieldCheckIcon } from "@/components/icons";

const frameworkMeta: Record<string, { color: string; bg: string; border: string; hoverBorder: string; accent: string; icon: string; desc: string; guidelines: string }> = {
  nhs_uk: {
    color: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-blue-100",
    hoverBorder: "hover:border-blue-300",
    accent: "bg-[#005EB8]",
    icon: "NHS",
    desc: "NICE guidelines for UK cardiovascular referral triage with EMERGENCY / URGENT / ROUTINE classification.",
    guidelines: "NICE CG95, NG185, NG208, NG106",
  },
  us_aha: {
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-100",
    hoverBorder: "hover:border-red-300",
    accent: "bg-[#C8102E]",
    icon: "AHA",
    desc: "AHA/ACC guidelines for US cardiovascular referral triage with EMERGENT / URGENT / ELECTIVE classification.",
    guidelines: "AHA/ACC 2025 ACS, 2020 VHD, 2022 HF",
  },
};

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [frameworks, setFrameworks] = useState<Framework[]>([]);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => {});
    fetchFrameworks().then((d) => setFrameworks(d.frameworks || [])).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      {/* Welcome */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">Dashboard</h2>
        <p className="mt-1 text-sm text-slate-500">
          Choose a clinical framework and start triaging referral documents
        </p>
      </div>

      {/* Disclaimer */}
      <Alert className="border-amber-200 bg-amber-50">
        <AlertTriangleIcon className="h-4 w-4 text-amber-600" />
        <AlertDescription className="text-xs text-amber-800">
          <strong>Research demonstration only.</strong> All triage outputs must be validated by a qualified clinician before any clinical decision is made.
        </AlertDescription>
      </Alert>

      {/* Framework Selection */}
      <div>
        <h3 className="mb-4 text-sm font-semibold text-slate-700 flex items-center gap-2">
          <ShieldCheckIcon className="h-4 w-4 text-slate-400" />
          Choose Clinical Framework
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          {frameworks.map((fw) => {
            const meta = frameworkMeta[fw.id] || frameworkMeta.nhs_uk;
            return (
              <Link key={fw.id} href={`/triage?framework=${fw.id}`}>
                <Card className={`group relative overflow-hidden ${meta.border} ${meta.hoverBorder} hover:shadow-lg transition-all cursor-pointer h-full`}>
                  <div className={`absolute right-0 top-0 h-40 w-40 translate-x-10 -translate-y-10 rounded-full ${meta.bg} transition-transform group-hover:scale-150 opacity-60`} />
                  <CardContent className="relative p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div className={`flex h-14 w-14 items-center justify-center rounded-2xl ${meta.accent} text-white shadow-sm`}>
                        <span className="text-lg font-extrabold tracking-tight">{meta.icon}</span>
                      </div>
                      <ArrowRightIcon className={`h-5 w-5 ${meta.color} opacity-0 -translate-x-2 transition-all group-hover:opacity-100 group-hover:translate-x-0`} />
                    </div>
                    <h3 className="mb-1 text-lg font-bold text-slate-900">{fw.name}</h3>
                    <p className="mb-3 text-sm leading-relaxed text-slate-500">{meta.desc}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {meta.guidelines.split(", ").map((g) => (
                        <Badge key={g} variant="secondary" className={`${meta.bg} ${meta.color} border ${meta.border} text-[10px] font-medium`}>
                          {g}
                        </Badge>
                      ))}
                    </div>
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <Button className={`${meta.accent} text-white hover:opacity-90 w-full`}>
                        <SparklesIcon className="mr-2 h-4 w-4" />
                        Start {meta.icon} Triage
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-slate-500">System Status</CardTitle>
            <span className="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_6px_rgba(34,197,94,.5)]" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-700">Healthy</div>
            <p className="text-xs text-slate-400 mt-1">All systems operational</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-slate-500">AI Models</CardTitle>
            <SparklesIcon className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">Local</div>
            <p className="text-xs text-slate-400 mt-1">
              {health?.cuda_available ? health.gpu_info?.device_name || "GPU Active" : "CPU Mode"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-slate-500">Frameworks</CardTitle>
            <DocumentIcon className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{health?.frameworks?.length || 0}</div>
            <p className="text-xs text-slate-400 mt-1">Clinical guideline sets</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-slate-500">Processors</CardTitle>
            <HeartIcon className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{health?.processor_count ?? 0}</div>
            <p className="text-xs text-slate-400 mt-1">Cached instances</p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/triage">
          <Card className="group relative overflow-hidden border-red-100 hover:border-red-200 hover:shadow-md transition-all cursor-pointer h-full">
            <div className="absolute right-0 top-0 h-32 w-32 translate-x-8 -translate-y-8 rounded-full bg-red-50 transition-transform group-hover:scale-125" />
            <CardContent className="relative p-6">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-red-800 text-white shadow-sm">
                <SparklesIcon className="h-6 w-6" />
              </div>
              <h3 className="mb-1 text-lg font-semibold text-slate-900">New Triage</h3>
              <p className="text-sm text-slate-500">
                Upload a referral document and get AI-powered clinical triage recommendations.
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/history">
          <Card className="group relative overflow-hidden hover:border-slate-300 hover:shadow-md transition-all cursor-pointer h-full">
            <div className="absolute right-0 top-0 h-32 w-32 translate-x-8 -translate-y-8 rounded-full bg-slate-50 transition-transform group-hover:scale-125" />
            <CardContent className="relative p-6">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="mb-1 text-lg font-semibold text-slate-900">View History</h3>
              <p className="text-sm text-slate-500">
                Review previously processed documents and triage results from this session.
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* System info */}
      {health && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-slate-700">System Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { label: "Auth", value: health.auth_enabled ? "Enabled" : "Disabled" },
                { label: "Rate Limiting", value: health.rate_limiting ? "Active" : "Disabled" },
                { label: "CUDA", value: health.cuda_available ? "Available" : "Not Available" },
                { label: "Frameworks", value: health.frameworks?.join(", ") || "None" },
                { label: "Scopes", value: health.scopes?.join(", ") || "None" },
                { label: "Local Models", value: "Yes" },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <span className="text-xs font-medium text-slate-500">{item.label}</span>
                  <Badge variant="secondary" className="text-[10px]">{item.value}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
