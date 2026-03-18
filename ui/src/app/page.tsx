import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  HeartIcon,
  ShieldCheckIcon,
  SparklesIcon,
  DocumentIcon,
  ArrowRightIcon,
  LockIcon,
  ServerIcon,
  CrossIcon,
  CpuIcon,
  AlertTriangleIcon,
} from "@/components/icons";

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="group rounded-xl border border-border bg-white p-6 transition-all hover:shadow-lg hover:border-red-200 hover:-translate-y-0.5">
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-red-50 text-red-700 transition-colors group-hover:bg-red-100">
        {icon}
      </div>
      <h3 className="mb-2 text-base font-semibold text-slate-900">{title}</h3>
      <p className="text-sm leading-relaxed text-slate-500">{description}</p>
    </div>
  );
}

function TrustBadge({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 shadow-sm">
      {icon}
      {label}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* ── Navigation ─────────────────────────────── */}
      <nav className="sticky top-0 z-50 border-b border-slate-100 bg-white/80 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-800 text-white">
              <CrossIcon className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold tracking-tight text-slate-900">
              CardioTriage<span className="text-red-700"> AI</span>
            </span>
          </div>
          <div className="hidden items-center gap-8 md:flex">
            <a href="#features" className="text-sm font-medium text-slate-500 transition-colors hover:text-slate-900">Features</a>
            <a href="#how-it-works" className="text-sm font-medium text-slate-500 transition-colors hover:text-slate-900">How It Works</a>
            <a href="#security" className="text-sm font-medium text-slate-500 transition-colors hover:text-slate-900">Security</a>
          </div>
          <Link href="/dashboard">
            <Button className="bg-red-800 text-white hover:bg-red-900 shadow-sm">
              Open Dashboard
              <ArrowRightIcon className="ml-1 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────── */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-red-50/60 via-white to-white" />
        <div className="absolute left-1/2 top-0 h-[600px] w-[800px] -translate-x-1/2 rounded-full bg-red-100/40 blur-3xl" />

        <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-24 text-center md:pt-32 md:pb-28">
          <Badge variant="secondary" className="mb-6 border-red-200 bg-red-50 text-red-700 px-4 py-1.5 text-xs font-semibold tracking-wide">
            <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
            LOCAL AI MODELS &mdash; DTAC COMPLIANT
          </Badge>

          <h1 className="mx-auto max-w-4xl text-5xl font-extrabold tracking-tight text-slate-900 md:text-6xl lg:text-7xl">
            AI-Powered{" "}
            <span className="bg-gradient-to-r from-red-800 via-red-700 to-red-600 bg-clip-text text-transparent">
              Cardiovascular
            </span>{" "}
            Referral Triage
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-500 md:text-xl">
            Process medical referral letters with local AI models. Identify red
            flags, assess urgency, and generate evidence-based triage
            recommendations in seconds &mdash; all without data leaving your
            infrastructure.
          </p>

          <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link href="/dashboard">
              <Button size="lg" className="bg-red-800 text-white hover:bg-red-900 shadow-lg shadow-red-200/50 px-8 text-base h-12">
                <SparklesIcon className="mr-2 h-5 w-5" />
                Launch Triage Dashboard
              </Button>
            </Link>
            <a href="#how-it-works">
              <Button size="lg" variant="outline" className="border-slate-200 text-slate-700 hover:bg-slate-50 px-8 text-base h-12">
                See How It Works
              </Button>
            </a>
          </div>

          <div className="mt-14 flex flex-wrap items-center justify-center gap-3">
            <TrustBadge icon={<ShieldCheckIcon className="h-3.5 w-3.5 text-green-600" />} label="NHS DTAC Compliant" />
            <TrustBadge icon={<LockIcon className="h-3.5 w-3.5 text-blue-600" />} label="Patient Data Anonymised" />
            <TrustBadge icon={<ServerIcon className="h-3.5 w-3.5 text-purple-600" />} label="100% Local Processing" />
            <TrustBadge icon={<DocumentIcon className="h-3.5 w-3.5 text-red-600" />} label="Audit Logged" />
          </div>
        </div>
      </section>

      {/* ── Features ───────────────────────────────── */}
      <section id="features" className="border-t border-slate-100 bg-slate-50/50 py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-14 text-center">
            <Badge variant="secondary" className="mb-4 border-slate-200 text-slate-600">
              Capabilities
            </Badge>
            <h2 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
              Clinical Intelligence, <span className="text-red-700">Locally Deployed</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-500">
              Purpose-built for cardiovascular referral triage with multi-framework clinical guidelines and evidence-based recommendations.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <FeatureCard icon={<SparklesIcon className="h-5 w-5" />} title="AI Clinical Reasoning" description="Multi-tier AI pipeline with BioGPT and Phi-3 models generates structured triage recommendations with confidence scoring." />
            <FeatureCard icon={<AlertTriangleIcon className="h-5 w-5" />} title="Red Flag Detection" description="Evidence-based pattern matching identifies critical cardiac red flags including aortic emergencies, arrhythmias, and acute coronary syndromes." />
            <FeatureCard icon={<DocumentIcon className="h-5 w-5" />} title="Smart Document Processing" description="Extract text from PDFs with OCR fallback. Automatic patient data anonymisation before any AI processing begins." />
            <FeatureCard icon={<ShieldCheckIcon className="h-5 w-5" />} title="Multi-Framework Support" description="Switch between NHS UK and US AHA/ACC guidelines with framework-specific urgency levels, clinical terms, and evidence references." />
            <FeatureCard icon={<CpuIcon className="h-5 w-5" />} title="Local Model Inference" description="All AI models run locally with GPU acceleration. No patient data leaves your infrastructure. Full DTAC and HIPAA alignment." />
            <FeatureCard icon={<HeartIcon className="h-5 w-5" />} title="Cardiac Knowledge Base" description="Vector database of NICE, AHA/ACC, and ESC clinical guidelines powers evidence-based recommendations with source citations." />
          </div>
        </div>
      </section>

      {/* ── How It Works ───────────────────────────── */}
      <section id="how-it-works" className="border-t border-slate-100 py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-14 text-center">
            <Badge variant="secondary" className="mb-4 border-slate-200 text-slate-600">
              Pipeline
            </Badge>
            <h2 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
              Four Steps to <span className="text-red-700">Clinical Insight</span>
            </h2>
          </div>

          <div className="grid gap-0 md:grid-cols-4">
            {[
              { step: "01", title: "Upload", desc: "Upload a referral letter (PDF or TXT). The document is stored temporarily and deleted after processing.", color: "bg-red-50 text-red-700 border-red-200" },
              { step: "02", title: "Anonymise", desc: "Patient identifiers (NHS numbers, postcodes, SSNs) are automatically redacted before any AI model sees the text.", color: "bg-amber-50 text-amber-700 border-amber-200" },
              { step: "03", title: "Analyse", desc: "Local AI models assess clinical urgency, detect red flags, query guideline knowledge bases, and generate structured reasoning.", color: "bg-blue-50 text-blue-700 border-blue-200" },
              { step: "04", title: "Triage", desc: "Receive an evidence-based triage recommendation with urgency level, timeframe, red flags, confidence score, and clinical reasoning.", color: "bg-green-50 text-green-700 border-green-200" },
            ].map((item) => (
              <div key={item.step} className="relative flex flex-col items-center px-6 py-8 text-center">
                <div className={`mb-5 flex h-12 w-12 items-center justify-center rounded-full border text-lg font-bold ${item.color}`}>
                  {item.step}
                </div>
                <h3 className="mb-2 text-base font-semibold text-slate-900">{item.title}</h3>
                <p className="text-sm leading-relaxed text-slate-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Security ───────────────────────────────── */}
      <section id="security" className="border-t border-slate-100 bg-slate-50/50 py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-14 text-center">
            <Badge variant="secondary" className="mb-4 border-slate-200 text-slate-600">
              Compliance &amp; Security
            </Badge>
            <h2 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
              Built for <span className="text-red-700">Clinical Trust</span>
            </h2>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: <LockIcon className="h-5 w-5" />, title: "DTAC Compliant", desc: "Meets NHS Digital Technology Assessment Criteria for clinical safety and data protection." },
              { icon: <ServerIcon className="h-5 w-5" />, title: "Air-Gapped Ready", desc: "All inference runs locally. Deploy in air-gapped environments with zero external API calls." },
              { icon: <ShieldCheckIcon className="h-5 w-5" />, title: "PII Anonymisation", desc: "NHS numbers, postcodes, SSNs, and MRNs redacted before AI processing via regex and NLP." },
              { icon: <DocumentIcon className="h-5 w-5" />, title: "Audit Logging", desc: "Append-only daily audit logs track every access, recommendation, and error for compliance." },
            ].map((item, i) => (
              <div key={i} className="rounded-xl border border-slate-200 bg-white p-6">
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                  {item.icon}
                </div>
                <h3 className="mb-1.5 text-sm font-semibold text-slate-900">{item.title}</h3>
                <p className="text-xs leading-relaxed text-slate-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────── */}
      <section className="border-t border-slate-100 py-20 md:py-28">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-800 text-white shadow-lg shadow-red-200/50">
            <CrossIcon className="h-8 w-8" />
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
            Ready to Triage?
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-slate-500">
            Upload your first referral document and see AI-powered clinical triage in action.
          </p>
          <div className="mt-8">
            <Link href="/dashboard">
              <Button size="lg" className="bg-red-800 text-white hover:bg-red-900 shadow-lg shadow-red-200/50 px-10 text-base h-12">
                Open Dashboard
                <ArrowRightIcon className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────── */}
      <footer className="border-t border-slate-100 py-10">
        <div className="mx-auto max-w-6xl px-6">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-red-800 text-white">
                <CrossIcon className="h-3.5 w-3.5" />
              </div>
              <span className="text-sm font-semibold text-slate-700">CardioTriage AI</span>
            </div>
            <p className="text-xs text-slate-400">
              Research demonstration only. Not for direct clinical use. All outputs require clinician review.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
