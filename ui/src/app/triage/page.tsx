"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import {
  fetchFrameworks,
  fetchGuidelines,
  processDocument,
  type Framework,
  type Scope,
  type ProcessResult,
  type BloodTest,
  type ClinicalData,
  type ClinicalScore,
  type GuidelineReference,
  type ClinicalEquation,
} from "@/lib/api";
import {
  SparklesIcon,
  DocumentIcon,
  AlertTriangleIcon,
  ShieldCheckIcon,
  UploadIcon,
  CheckCircleIcon,
} from "@/components/icons";

const STEP_LABELS = [
  "Extracting text from document",
  "Extracting clinical data",
  "Anonymising patient data",
  "Querying knowledge base",
  "Generating clinical reasoning",
];

function urgencyClass(u: string) {
  const up = u.toUpperCase();
  if (up.includes("EMERGENCY") || up.includes("EMERGENT")) return "emergency";
  if (up.includes("URGENT")) return "urgent";
  return "routine";
}

const urgencyStyles: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  emergency: { bg: "bg-red-50", border: "border-red-200", text: "text-red-700", badge: "bg-red-100 text-red-800" },
  urgent: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", badge: "bg-amber-100 text-amber-800" },
  routine: { bg: "bg-green-50", border: "border-green-200", text: "text-green-700", badge: "bg-green-100 text-green-800" },
};

const flagColors: Record<string, string> = {
  normal: "text-green-700 bg-green-50",
  low: "text-amber-700 bg-amber-50",
  high: "text-amber-700 bg-amber-50",
  critical_low: "text-red-700 bg-red-50 font-semibold",
  critical_high: "text-red-700 bg-red-50 font-semibold",
};

const flagLabels: Record<string, string> = {
  normal: "Normal",
  low: "Low",
  high: "High",
  critical_low: "Critical Low",
  critical_high: "Critical High",
};

const categoryLabels: Record<string, string> = {
  cardiac_biomarkers: "Cardiac Biomarkers",
  lipids: "Lipid Panel",
  metabolic: "Metabolic",
  haematology: "Haematology",
  liver: "Liver Function",
  thyroid: "Thyroid",
  other: "Other",
};

const FLAG_CHART_COLORS: Record<string, string> = {
  normal: "#16a34a",
  low: "#f59e0b",
  high: "#f59e0b",
  critical_low: "#dc2626",
  critical_high: "#dc2626",
};

// ── Blood test table row ──

function BloodTestBar({ test }: { test: BloodTest }) {
  const isCritical = test.flag.startsWith("critical");
  const isAbnormal = test.flag !== "normal";
  return (
    <tr className={`border-b border-slate-100 last:border-0 ${isCritical ? "bg-red-50/50" : ""}`}>
      <td className="py-2 pr-3 text-xs font-medium text-slate-700 whitespace-nowrap">{test.abbr}</td>
      <td className="py-2 pr-3 text-xs text-slate-900 font-mono tabular-nums text-right">{test.value}</td>
      <td className="py-2 pr-3 text-xs text-slate-400">{test.unit}</td>
      <td className="py-2 pr-3 text-xs text-slate-400">{test.reference_range}</td>
      <td className="py-2">
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${flagColors[test.flag]}`}>
          {isAbnormal && (
            <svg className="mr-0.5 h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              {test.flag.includes("high") ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              )}
            </svg>
          )}
          {flagLabels[test.flag]}
        </span>
      </td>
    </tr>
  );
}

// ── Clinical score display ──

function ScoreCard({ score }: { score: ClinicalScore }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-slate-600">{score.name}</span>
        <span className="text-lg font-bold text-slate-900 font-mono tabular-nums">
          {score.value}<span className="text-xs font-normal text-slate-400 ml-0.5">{score.unit}</span>
        </span>
      </div>
      <p className="mt-1 text-[11px] text-slate-500 leading-snug">{score.interpretation}</p>
      <p className="mt-1 text-[10px] text-slate-400 italic">{score.reference}</p>
      {score.components && (
        <div className="mt-2 flex flex-wrap gap-1">
          {Object.entries(score.components).map(([k, v]) => (
            <span key={k} className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] ${
              v === 0 ? "bg-slate-50 text-slate-400" : "bg-blue-50 text-blue-700"
            }`}>
              {k}: {String(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Vitals gauge ──

function VitalItem({ label, value, unit, range }: { label: string; value?: number; unit: string; range?: string }) {
  if (value === undefined || value === null) return null;
  return (
    <div className="flex flex-col items-center rounded-lg border border-slate-200 bg-white px-4 py-3 min-w-[100px]">
      <span className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">{label}</span>
      <span className="text-xl font-bold text-slate-900 font-mono tabular-nums">{value}</span>
      <span className="text-[10px] text-slate-400">{unit}</span>
      {range && <span className="text-[10px] text-slate-300 mt-0.5">{range}</span>}
    </div>
  );
}

// ── Blood test visual bar ──

function BloodTestVisualBar({ test }: { test: BloodTest }) {
  const ref = test.reference_range;
  let low: number | null = null;
  let high: number | null = null;
  const rangeMatch = ref.match(/^(\d+\.?\d*)\s*[–-]\s*(\d+\.?\d*)$/);
  const gtMatch = ref.match(/^>(\d+\.?\d*)$/);
  const ltMatch = ref.match(/^<(\d+\.?\d*)$/);
  if (rangeMatch) { low = parseFloat(rangeMatch[1]); high = parseFloat(rangeMatch[2]); }
  else if (gtMatch) { low = parseFloat(gtMatch[1]); high = low * 2; }
  else if (ltMatch) { high = parseFloat(ltMatch[1]); low = 0; }
  if (low === null || high === null) return null;
  const range = high - low;
  const min = low - range * 0.3;
  const max = high + range * 0.3;
  const totalRange = max - min;
  const normalStart = ((low - min) / totalRange) * 100;
  const normalWidth = (range / totalRange) * 100;
  const valuePos = Math.max(0, Math.min(100, ((test.value - min) / totalRange) * 100));
  return (
    <div className="w-full h-3 relative mt-1 mb-0.5">
      <div className="absolute inset-0 rounded-full bg-slate-100" />
      <div className="absolute top-0 h-full rounded-full bg-green-200" style={{ left: `${normalStart}%`, width: `${normalWidth}%` }} />
      <div className={`absolute top-1/2 -translate-y-1/2 h-2.5 w-2.5 rounded-full border-2 border-white shadow-sm ${
        test.flag === "normal" ? "bg-green-500" : test.flag.startsWith("critical") ? "bg-red-500" : "bg-amber-500"
      }`} style={{ left: `calc(${valuePos}% - 5px)` }} />
    </div>
  );
}

// ── Statistics charts ──

function BloodTestStatusChart({ bloodTests }: { bloodTests: BloodTest[] }) {
  const counts = { Normal: 0, Abnormal: 0, Critical: 0 };
  for (const bt of bloodTests) {
    if (bt.flag === "normal") counts.Normal++;
    else if (bt.flag.startsWith("critical")) counts.Critical++;
    else counts.Abnormal++;
  }
  const data = [
    { name: "Normal", value: counts.Normal, color: "#16a34a" },
    { name: "Abnormal", value: counts.Abnormal, color: "#f59e0b" },
    { name: "Critical", value: counts.Critical, color: "#dc2626" },
  ].filter(d => d.value > 0);
  return (
    <div className="flex items-center gap-6">
      <ResponsiveContainer width={120} height={120}>
        <PieChart>
          <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={30} outerRadius={50} paddingAngle={3} strokeWidth={0}>
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Pie>
          <Tooltip formatter={(v) => [`${v} tests`, ""]} />
        </PieChart>
      </ResponsiveContainer>
      <div className="space-y-1.5">
        {data.map(d => (
          <div key={d.name} className="flex items-center gap-2 text-xs">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: d.color }} />
            <span className="text-slate-600">{d.name}</span>
            <span className="font-mono font-bold text-slate-900">{d.value}</span>
          </div>
        ))}
        <div className="text-[10px] text-slate-400 pt-1">{bloodTests.length} total tests</div>
      </div>
    </div>
  );
}

function BloodTestBarChart({ bloodTests }: { bloodTests: BloodTest[] }) {
  const abnormal = bloodTests.filter(bt => bt.flag !== "normal").slice(0, 10);
  if (abnormal.length === 0) return null;
  const data = abnormal.map(bt => ({
    name: bt.abbr,
    value: bt.value,
    color: FLAG_CHART_COLORS[bt.flag] || "#64748b",
  }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} />
        <YAxis tick={{ fontSize: 10 }} width={45} />
        <Tooltip formatter={(v) => [v, "Value"]} labelStyle={{ fontSize: 11 }} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((d, i) => <Cell key={i} fill={d.color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function VitalsRadarChart({ vitals }: { vitals: ClinicalData["vitals"] }) {
  const items = [
    { key: "heart_rate", label: "HR", value: vitals.heart_rate, min: 40, max: 160, normalMin: 60, normalMax: 100 },
    { key: "spo2", label: "SpO2", value: vitals.spo2, min: 80, max: 100, normalMin: 94, normalMax: 100 },
    { key: "systolic_bp", label: "SBP", value: vitals.systolic_bp, min: 60, max: 220, normalMin: 90, normalMax: 140 },
    { key: "diastolic_bp", label: "DBP", value: vitals.diastolic_bp, min: 40, max: 130, normalMin: 60, normalMax: 90 },
    { key: "respiratory_rate", label: "RR", value: vitals.respiratory_rate, min: 6, max: 40, normalMin: 12, normalMax: 20 },
    { key: "temperature_c", label: "Temp", value: vitals.temperature_c, min: 34, max: 42, normalMin: 36.1, normalMax: 37.2 },
  ].filter(item => item.value !== undefined);
  if (items.length < 3) return null;
  const data = items.map(item => ({
    label: item.label,
    value: Math.round(((item.value! - item.min) / (item.max - item.min)) * 100),
    normalMin: Math.round(((item.normalMin - item.min) / (item.max - item.min)) * 100),
    normalMax: Math.round(((item.normalMax - item.min) / (item.max - item.min)) * 100),
    actual: item.value,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
        <PolarGrid stroke="#e2e8f0" />
        <PolarAngleAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} />
        <PolarRadiusAxis tick={false} axisLine={false} domain={[0, 100]} />
        <Radar name="Value" dataKey="value" stroke="#991b1b" fill="#991b1b" fillOpacity={0.2} strokeWidth={2} />
        <Tooltip formatter={(v, _name, props) => [(props as { payload?: { actual?: number } }).payload?.actual ?? v, "Value"]} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ── Evidence Library Panel ──

function EvidenceLibraryPanel({ frameworkId }: { frameworkId: string }) {
  const [guidelines, setGuidelines] = useState<GuidelineReference[]>([]);
  const [equations, setEquations] = useState<ClinicalEquation[]>([]);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tab, setTab] = useState<"guidelines" | "equations">("guidelines");

  useEffect(() => {
    fetchGuidelines(frameworkId).then(data => {
      setGuidelines(data.guidelines || []);
      setEquations(data.equations || []);
    }).catch(() => {});
  }, [frameworkId]);

  const q = search.toLowerCase();
  const filteredGuidelines = guidelines.filter(g =>
    !q || g.title.toLowerCase().includes(q) || g.organization.toLowerCase().includes(q) ||
    g.summary.toLowerCase().includes(q) || g.code.toLowerCase().includes(q) ||
    g.key_recommendations.some(r => r.toLowerCase().includes(q))
  );
  const filteredEquations = equations.filter(e =>
    !q || e.name.toLowerCase().includes(q) || e.formula.toLowerCase().includes(q) ||
    e.use_case.toLowerCase().includes(q) || e.category.toLowerCase().includes(q)
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
          Evidence Library
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Search */}
        <div className="relative mb-4">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            placeholder="Search guidelines, equations, recommendations..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-red-300 focus:ring-2 focus:ring-red-100 outline-none"
          />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-4 border-b border-slate-100">
          <button onClick={() => setTab("guidelines")} className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${tab === "guidelines" ? "border-red-700 text-red-700" : "border-transparent text-slate-400 hover:text-slate-600"}`}>
            Guidelines ({filteredGuidelines.length})
          </button>
          <button onClick={() => setTab("equations")} className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${tab === "equations" ? "border-red-700 text-red-700" : "border-transparent text-slate-400 hover:text-slate-600"}`}>
            Equations ({filteredEquations.length})
          </button>
        </div>

        {/* Guidelines list */}
        {tab === "guidelines" && (
          <div className="space-y-2">
            {filteredGuidelines.length === 0 && <p className="text-xs text-slate-400 py-4 text-center">No guidelines match your search</p>}
            {filteredGuidelines.map(g => {
              const isExpanded = expandedId === g.id;
              return (
                <div key={g.id} className={`rounded-lg border transition-colors ${isExpanded ? "border-red-200 bg-red-50/30" : "border-slate-200 hover:border-slate-300"}`}>
                  <button onClick={() => setExpandedId(isExpanded ? null : g.id)} className="w-full text-left px-4 py-3 flex items-start gap-3">
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[10px] font-bold text-slate-600">
                      {g.organization.slice(0, 4)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-slate-900">{g.title}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <Badge variant="outline" className="text-[10px] border-slate-200">{g.code}</Badge>
                        <span className="text-[10px] text-slate-400">{g.organization} &middot; {g.year} &middot; Updated {g.last_updated}</span>
                      </div>
                    </div>
                    <svg className={`h-4 w-4 text-slate-400 shrink-0 mt-1 transition-transform ${isExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                    </svg>
                  </button>
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-3">
                      <p className="text-xs leading-relaxed text-slate-600">{g.summary}</p>
                      <div>
                        <div className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1.5">Key Recommendations</div>
                        <ul className="space-y-1">
                          {g.key_recommendations.map((r, i) => (
                            <li key={i} className="flex items-start gap-2 text-xs text-slate-700">
                              <CheckCircleIcon className="h-3.5 w-3.5 text-green-600 shrink-0 mt-0.5" />
                              {r}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <a href={g.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-xs font-medium text-red-700 hover:text-red-900">
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                        </svg>
                        View full guideline
                      </a>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Equations list */}
        {tab === "equations" && (
          <div className="space-y-2">
            {filteredEquations.length === 0 && <p className="text-xs text-slate-400 py-4 text-center">No equations match your search</p>}
            {filteredEquations.map(eq => {
              const isExpanded = expandedId === eq.id;
              return (
                <div key={eq.id} className={`rounded-lg border transition-colors ${isExpanded ? "border-blue-200 bg-blue-50/30" : "border-slate-200 hover:border-slate-300"}`}>
                  <button onClick={() => setExpandedId(isExpanded ? null : eq.id)} className="w-full text-left px-4 py-3 flex items-start gap-3">
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V13.5zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V18zm2.498-6.75h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V13.5zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V18zm2.504-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-slate-900">{eq.name}</div>
                      <Badge variant="outline" className="text-[10px] border-slate-200 mt-0.5">{eq.category.replace(/_/g, " ")}</Badge>
                    </div>
                    <svg className={`h-4 w-4 text-slate-400 shrink-0 mt-1 transition-transform ${isExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                    </svg>
                  </button>
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-2">
                      <div className="rounded-md bg-slate-900 px-4 py-3">
                        <code className="text-xs text-green-400 font-mono">{eq.formula}</code>
                      </div>
                      <p className="text-xs text-slate-600"><span className="font-medium">Use:</span> {eq.use_case}</p>
                      <p className="text-[10px] text-slate-400 italic">{eq.reference}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ════════════════════════════════════════════════════════════
// MAIN PAGE
// ════════════════════════════════════════════════════════════

function TriagePageContent() {
  const searchParams = useSearchParams();
  const [frameworks, setFrameworks] = useState<Framework[]>([]);
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [selectedFramework, setSelectedFramework] = useState(searchParams.get("framework") || "nhs_uk");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const stepInterval = useRef<ReturnType<typeof setInterval>>(null);

  useEffect(() => {
    fetchFrameworks().then((d) => {
      setFrameworks(d.frameworks || []);
      setScopes(d.scopes || []);
    }).catch(() => {});
  }, []);

  const handleFile = useCallback((f: File) => {
    const ext = f.name.split(".").pop()?.toLowerCase();
    if (!ext || !["pdf", "txt"].includes(ext)) { setError("Please upload a PDF or TXT file."); return; }
    if (f.size > 16 * 1024 * 1024) { setError("File exceeds 16 MB limit."); return; }
    setFile(f);
    setError(null);
    setResult(null);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  const handleProcess = async () => {
    if (!file) return;
    setProcessing(true);
    setResult(null);
    setError(null);
    setCurrentStep(0);
    stepInterval.current = setInterval(() => {
      setCurrentStep((s) => Math.min(s + 1, STEP_LABELS.length - 1));
    }, 2500);
    try {
      const data = await processDocument(file, selectedFramework, selectedScopes);
      clearInterval(stepInterval.current!);
      setCurrentStep(STEP_LABELS.length);
      setTimeout(() => {
        setProcessing(false);
        if (data.status === "success") { setResult(data); } else { setError(data.error || "An unexpected error occurred."); }
      }, 500);
    } catch {
      clearInterval(stepInterval.current!);
      setProcessing(false);
      setError("Network error. Please check your connection and ensure the backend is running.");
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setProcessing(false);
    setCurrentStep(0);
    if (fileRef.current) fileRef.current.value = "";
  };

  const fmtSize = (b: number) =>
    b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;

  // ════════════════════════════════════════════
  // RESULTS VIEW
  // ════════════════════════════════════════════

  if (result) {
    const rec = result.recommendation;
    const risk = result.risk_assessment;
    const cd = result.clinical_data;
    const urgency = rec?.urgency || risk?.urgency || "ROUTINE";
    const uc = urgencyClass(urgency);
    const styles = urgencyStyles[uc];
    const allFlags = [...new Set([...(risk?.red_flags || []), ...(rec?.red_flags || [])])];
    const conf = (rec?.confidence_level || "moderate").toLowerCase();

    // Group blood tests by category
    const bloodTestsByCategory: Record<string, BloodTest[]> = {};
    if (cd?.blood_tests) {
      for (const bt of cd.blood_tests) {
        const cat = bt.category || "other";
        if (!bloodTestsByCategory[cat]) bloodTestsByCategory[cat] = [];
        bloodTestsByCategory[cat].push(bt);
      }
    }

    const hasVitals = cd?.vitals && Object.keys(cd.vitals).length > 0;
    const hasDemographics = cd?.patient_demographics && Object.keys(cd.patient_demographics).length > 0;
    const hasBloodTests = cd?.blood_tests && cd.blood_tests.length > 0;
    const hasMeds = cd?.medications && cd.medications.length > 0;
    const hasScores = cd?.clinical_scores && cd.clinical_scores.length > 0;

    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">Triage Result</h2>
            <p className="mt-1 text-sm text-slate-500">
              Analysis complete &middot; Framework: <span className="font-medium text-slate-700">{result.framework || selectedFramework}</span>
            </p>
          </div>
          <Button onClick={reset} variant="outline">New Analysis</Button>
        </div>

        {/* ── Urgency Banner ── */}
        <div className={`rounded-xl ${styles.bg} ${styles.border} border p-6`}>
          <div className="flex items-center gap-5 flex-wrap">
            <div className={`flex h-14 w-14 items-center justify-center rounded-2xl ${styles.bg} ${styles.text}`}>
              {uc === "routine" ? <CheckCircleIcon className="h-7 w-7" /> : <AlertTriangleIcon className="h-7 w-7" />}
            </div>
            <div className="flex-1">
              <div className={`text-2xl font-bold ${styles.text}`}>{urgency}</div>
              {rec?.suggested_timeframe && (
                <div className="text-sm text-slate-600 mt-0.5">{rec.suggested_timeframe}</div>
              )}
            </div>
            <div className="flex flex-col items-end gap-2">
              <Badge className={styles.badge}>
                {conf.charAt(0).toUpperCase() + conf.slice(1)} confidence
              </Badge>
              {rec?.model_source && (
                <span className="text-[11px] font-mono text-slate-400">{rec.model_source}</span>
              )}
              {result.framework && (
                <Badge variant="outline" className="text-[10px]">{result.framework}</Badge>
              )}
            </div>
          </div>
        </div>

        {/* ── Patient Demographics & Vitals ── */}
        {(hasDemographics || hasVitals) && (
          <div className="grid gap-4 md:grid-cols-2">
            {hasDemographics && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                    </svg>
                    Patient Demographics
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    {cd!.patient_demographics.age !== undefined && (
                      <div className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Age</div>
                        <div className="text-sm font-semibold text-slate-900">{cd!.patient_demographics.age} years</div>
                      </div>
                    )}
                    {cd!.patient_demographics.sex && (
                      <div className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Sex</div>
                        <div className="text-sm font-semibold text-slate-900">{cd!.patient_demographics.sex}</div>
                      </div>
                    )}
                    {cd!.patient_demographics.height_cm !== undefined && (
                      <div className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Height</div>
                        <div className="text-sm font-semibold text-slate-900">{cd!.patient_demographics.height_cm} cm</div>
                      </div>
                    )}
                    {cd!.patient_demographics.weight_kg !== undefined && (
                      <div className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Weight</div>
                        <div className="text-sm font-semibold text-slate-900">{cd!.patient_demographics.weight_kg} kg</div>
                      </div>
                    )}
                    {cd!.patient_demographics.bmi_stated !== undefined && (
                      <div className="rounded-lg bg-slate-50 px-3 py-2 col-span-2">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">BMI (stated)</div>
                        <div className="text-sm font-semibold text-slate-900">{cd!.patient_demographics.bmi_stated} kg/m²</div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {hasVitals && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
                    </svg>
                    Vital Signs
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-3">
                    {cd!.vitals.systolic_bp !== undefined && cd!.vitals.diastolic_bp !== undefined && (
                      <div className="flex flex-col items-center rounded-lg border border-slate-200 bg-white px-4 py-3 min-w-[100px]">
                        <span className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">BP</span>
                        <span className="text-xl font-bold text-slate-900 font-mono tabular-nums">{cd!.vitals.systolic_bp}/{cd!.vitals.diastolic_bp}</span>
                        <span className="text-[10px] text-slate-400">mmHg</span>
                      </div>
                    )}
                    <VitalItem label="HR" value={cd!.vitals.heart_rate} unit="bpm" range="60-100" />
                    <VitalItem label="SpO2" value={cd!.vitals.spo2} unit="%" range=">94%" />
                    <VitalItem label="Temp" value={cd!.vitals.temperature_c} unit="°C" range="36.1-37.2" />
                    <VitalItem label="RR" value={cd!.vitals.respiratory_rate} unit="/min" range="12-20" />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* ── Vitals Radar + Blood Test Summary Charts ── */}
        {(hasVitals || hasBloodTests) && (
          <div className="grid gap-4 md:grid-cols-2">
            {hasVitals && cd?.vitals && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Vitals Overview</CardTitle>
                </CardHeader>
                <CardContent>
                  <VitalsRadarChart vitals={cd.vitals} />
                </CardContent>
              </Card>
            )}
            {hasBloodTests && cd?.blood_tests && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Blood Test Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <BloodTestStatusChart bloodTests={cd.blood_tests} />
                  <div className="mt-4">
                    <div className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-2">Abnormal Values</div>
                    <BloodTestBarChart bloodTests={cd.blood_tests} />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* ── Clinical Summary ── */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <DocumentIcon className="h-4 w-4 text-slate-400" />Clinical Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-slate-700">{result.summary || "No summary available."}</p>
          </CardContent>
        </Card>

        {/* ── Blood Tests ── */}
        {hasBloodTests && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                </svg>
                Blood Test Results
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(bloodTestsByCategory).map(([cat, tests]) => (
                  <div key={cat}>
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                      {categoryLabels[cat] || cat}
                    </h4>
                    <div className="rounded-lg border border-slate-200 overflow-hidden">
                      <table className="w-full">
                        <thead>
                          <tr className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-400">
                            <th className="py-1.5 px-3 text-left font-medium">Test</th>
                            <th className="py-1.5 px-3 text-right font-medium">Value</th>
                            <th className="py-1.5 px-3 text-left font-medium">Unit</th>
                            <th className="py-1.5 px-3 text-left font-medium">Ref Range</th>
                            <th className="py-1.5 px-3 text-left font-medium">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tests.map((t) => <BloodTestBar key={t.key} test={t} />)}
                        </tbody>
                      </table>
                    </div>
                    <div className="mt-2 space-y-1 px-1">
                      {tests.map((t) => (
                        <div key={`bar-${t.key}`}>
                          <div className="flex items-center justify-between text-[10px] text-slate-400">
                            <span>{t.abbr}</span>
                            <span className="font-mono">{t.value} {t.unit}</span>
                          </div>
                          <BloodTestVisualBar test={t} />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── Medications ── */}
        {hasMeds && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                </svg>
                Medications ({cd!.medications.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {cd!.medications.map((med, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5">
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-500">Rx</div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-900 capitalize truncate">{med.name}</div>
                      <div className="text-[11px] text-slate-500">{[med.dose, med.frequency].filter(Boolean).join(" · ") || med.drug_class}</div>
                      <Badge variant="outline" className="mt-1 text-[10px] border-slate-200 text-slate-400">{med.drug_class}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── Clinical Scores ── */}
        {hasScores && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V13.5zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V18zm2.498-6.75h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V13.5zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V18zm2.504-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zm0 2.25h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V18zm2.498-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zM8.25 6h7.5v2.25h-7.5V6zM12 2.25c-1.892 0-3.758.11-5.593.322C5.307 2.7 4.5 3.65 4.5 4.757V19.5a2.25 2.25 0 002.25 2.25h10.5a2.25 2.25 0 002.25-2.25V4.757c0-1.108-.806-2.057-1.907-2.185A48.507 48.507 0 0012 2.25z" />
                </svg>
                Clinical Scores & Equations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {cd!.clinical_scores.map((s, i) => <ScoreCard key={i} score={s} />)}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ── Red Flags & Evidence ── */}
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <AlertTriangleIcon className="h-4 w-4 text-slate-400" />Red Flags
              </CardTitle>
            </CardHeader>
            <CardContent>
              {allFlags.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {allFlags.map((f, i) => (
                    <Badge key={i} variant="secondary" className={`${uc === "routine" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-red-50 text-red-700 border-red-200"} border`}>{f}</Badge>
                  ))}
                </div>
              ) : <p className="text-sm text-slate-400">No red flags detected</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <ShieldCheckIcon className="h-4 w-4 text-slate-400" />Evidence Basis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs leading-relaxed text-slate-600 whitespace-pre-wrap max-h-40 overflow-y-auto">
                {rec?.evidence_basis || "No evidence references available."}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* ── Clinical Reasoning ── */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <SparklesIcon className="h-4 w-4 text-slate-400" />Clinical Reasoning
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-xs leading-relaxed text-slate-600 whitespace-pre-wrap max-h-64 overflow-y-auto">
              {rec?.reasoning || "No clinical reasoning available."}
            </div>
          </CardContent>
        </Card>

        {/* ── Evidence Library ── */}
        <EvidenceLibraryPanel frameworkId={result.framework || selectedFramework} />
      </div>
    );
  }

  // ════════════════════════════════════════════
  // UPLOAD FORM VIEW
  // ════════════════════════════════════════════

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">New Triage</h2>
        <p className="mt-1 text-sm text-slate-500">Upload a referral document for AI-powered clinical triage</p>
      </div>

      {/* Config */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
            </svg>
            Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-500 uppercase tracking-wide">Framework</label>
              <select
                value={selectedFramework}
                onChange={(e) => setSelectedFramework(e.target.value)}
                disabled={processing}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-red-300 focus:ring-2 focus:ring-red-100 outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {frameworks.map((fw) => (
                  <option key={fw.id} value={fw.id}>{fw.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-500 uppercase tracking-wide">Clinical Scopes</label>
              <div className="flex flex-wrap gap-2 pt-1">
                {scopes.length > 0 ? scopes.map((s) => (
                  <button
                    key={s.id}
                    disabled={processing}
                    onClick={() =>
                      setSelectedScopes((prev) =>
                        prev.includes(s.id) ? prev.filter((x) => x !== s.id) : [...prev, s.id]
                      )
                    }
                    className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                      selectedScopes.includes(s.id)
                        ? "border-red-200 bg-red-50 text-red-700"
                        : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                    }`}
                  >
                    <span className={`h-3 w-3 rounded border flex items-center justify-center ${
                      selectedScopes.includes(s.id) ? "bg-red-700 border-red-700" : "border-slate-300"
                    }`}>
                      {selectedScopes.includes(s.id) && (
                        <svg className="h-2 w-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={4}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      )}
                    </span>
                    {s.name}
                  </button>
                )) : (
                  <span className="text-xs text-slate-400">No additional scopes available</span>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Upload */}
      {!processing && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <UploadIcon className="h-4 w-4 text-slate-400" /> Upload Document
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className={`relative rounded-xl border-2 border-dashed transition-colors ${
                dragOver ? "border-red-400 bg-red-50" : file ? "border-red-200 bg-red-50/50" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
              } ${file ? "p-4" : "p-12"} text-center cursor-pointer`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
            >
              <input ref={fileRef} type="file" accept=".pdf,.txt" className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
              {file ? (
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-red-200 bg-white text-red-600">
                    <DocumentIcon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 text-left">
                    <div className="text-sm font-medium text-slate-900 truncate">{file.name}</div>
                    <div className="text-xs text-slate-400">{fmtSize(file.size)}</div>
                  </div>
                  <Button size="sm" variant="ghost" className="text-slate-400 hover:text-red-600" onClick={(e) => { e.stopPropagation(); reset(); }}>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </Button>
                </div>
              ) : (
                <>
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-slate-200 bg-white">
                    <UploadIcon className="h-5 w-5 text-slate-400" />
                  </div>
                  <p className="text-sm text-slate-600">
                    Drop your referral document here, or <span className="font-semibold text-red-700">browse</span>
                  </p>
                  <p className="mt-1 text-xs text-slate-400">PDF or TXT, up to 16 MB</p>
                </>
              )}
            </div>
            <Button className="mt-4 w-full bg-red-800 text-white hover:bg-red-900 h-11" disabled={!file} onClick={handleProcess}>
              <SparklesIcon className="mr-2 h-4 w-4" />
              Analyse Document
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Processing */}
      {processing && (
        <Card className="text-center py-10">
          <CardContent>
            <div className="mx-auto mb-6 h-12 w-12 animate-spin rounded-full border-[3px] border-slate-200 border-t-red-700" />
            <h3 className="text-lg font-semibold text-slate-900">Analysing Document</h3>
            <p className="mb-8 text-sm text-slate-400">Running AI-powered clinical triage pipeline</p>
            <div className="mx-auto max-w-xs space-y-2 text-left">
              {STEP_LABELS.map((label, i) => {
                const done = i < currentStep;
                const active = i === currentStep && currentStep < STEP_LABELS.length;
                return (
                  <div key={i} className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${active ? "bg-slate-50 text-slate-900" : done ? "text-slate-600" : "text-slate-300"}`}>
                    <div className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                      done ? "border-green-500 bg-green-50" : active ? "border-red-400 bg-red-50" : "border-slate-200"
                    }`}>
                      {done ? (
                        <svg className="h-3 w-3 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                      ) : active ? (
                        <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
                      ) : null}
                    </div>
                    {label}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangleIcon className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}

export default function TriagePage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center py-20 text-slate-400">Loading...</div>}>
      <TriagePageContent />
    </Suspense>
  );
}
