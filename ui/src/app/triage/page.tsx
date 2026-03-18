"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  fetchFrameworks,
  fetchFrameworkConfig,
  processDocument,
  type Framework,
  type Scope,
  type ProcessResult,
} from "@/lib/api";
import {
  SparklesIcon,
  DocumentIcon,
  AlertTriangleIcon,
  ShieldCheckIcon,
  UploadIcon,
  CheckCircleIcon,
  ClockIcon,
} from "@/components/icons";

const STEP_LABELS = [
  "Extracting text from document",
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

export default function TriagePage() {
  const [frameworks, setFrameworks] = useState<Framework[]>([]);
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [selectedFramework, setSelectedFramework] = useState("nhs_uk");
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
    if (!ext || !["pdf", "txt"].includes(ext)) {
      setError("Please upload a PDF or TXT file.");
      return;
    }
    if (f.size > 16 * 1024 * 1024) {
      setError("File exceeds 16 MB limit.");
      return;
    }
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
        if (data.status === "success") {
          setResult(data);
        } else {
          setError(data.error || "An unexpected error occurred.");
        }
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

  // Results rendering
  if (result) {
    const rec = result.recommendation;
    const risk = result.risk_assessment;
    const urgency = rec?.urgency || risk?.urgency || "ROUTINE";
    const uc = urgencyClass(urgency);
    const styles = urgencyStyles[uc];
    const allFlags = [...new Set([...(risk?.red_flags || []), ...(rec?.red_flags || [])])];
    const conf = (rec?.confidence_level || "moderate").toLowerCase();

    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">Triage Result</h2>
            <p className="mt-1 text-sm text-slate-500">Analysis complete for uploaded document</p>
          </div>
          <Button onClick={reset} variant="outline">New Analysis</Button>
        </div>

        {/* Urgency Banner */}
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

        {/* Cards */}
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="md:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm"><DocumentIcon className="h-4 w-4 text-slate-400" />Clinical Summary</CardTitle>
            </CardHeader>
            <CardContent><p className="text-sm leading-relaxed text-slate-700">{result.summary || "No summary available."}</p></CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm"><AlertTriangleIcon className="h-4 w-4 text-slate-400" />Red Flags</CardTitle>
            </CardHeader>
            <CardContent>
              {allFlags.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {allFlags.map((f, i) => (
                    <Badge key={i} variant="secondary" className={`${uc === "routine" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-red-50 text-red-700 border-red-200"} border`}>
                      {f}
                    </Badge>
                  ))}
                </div>
              ) : <p className="text-sm text-slate-400">No red flags detected</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm"><ShieldCheckIcon className="h-4 w-4 text-slate-400" />Evidence Basis</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs leading-relaxed text-slate-600 whitespace-pre-wrap">{rec?.evidence_basis || "No evidence references available."}</p>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm"><SparklesIcon className="h-4 w-4 text-slate-400" />Clinical Reasoning</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-xs leading-relaxed text-slate-600 whitespace-pre-wrap max-h-64 overflow-y-auto">
                {rec?.reasoning || "No clinical reasoning available."}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

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
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-red-300 focus:ring-2 focus:ring-red-100 outline-none"
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
                    onClick={() =>
                      setSelectedScopes((prev) =>
                        prev.includes(s.id) ? prev.filter((x) => x !== s.id) : [...prev, s.id]
                      )
                    }
                    className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
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
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.txt"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              {file ? (
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-red-200 bg-white text-red-600">
                    <DocumentIcon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 text-left">
                    <div className="text-sm font-medium text-slate-900 truncate">{file.name}</div>
                    <div className="text-xs text-slate-400">{fmtSize(file.size)}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-slate-400 hover:text-red-600"
                    onClick={(e) => { e.stopPropagation(); reset(); }}
                  >
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

            <Button
              className="mt-4 w-full bg-red-800 text-white hover:bg-red-900 h-11"
              disabled={!file}
              onClick={handleProcess}
            >
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
