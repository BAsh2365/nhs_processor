const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export interface Framework {
  id: string;
  name: string;
  description: string;
}

export interface Scope {
  id: string;
  name: string;
  description: string;
}

export interface FrameworkConfig {
  id: string;
  name: string;
  branding: {
    primary_color: string;
    secondary_color: string;
    success_color: string;
    logo_text: string;
    subtitle: string;
  };
  urgency_levels: string[];
}

// --- Clinical data types ---

export interface BloodTest {
  key: string;
  name: string;
  abbr: string;
  value: number;
  unit: string;
  category: string;
  flag: "normal" | "low" | "high" | "critical_low" | "critical_high";
  reference_range: string;
}

export interface Medication {
  name: string;
  drug_class: string;
  dose: string | null;
  frequency: string | null;
}

export interface ClinicalScore {
  name: string;
  value: number | string;
  unit: string;
  interpretation: string;
  reference: string;
  components?: Record<string, number | string>;
}

export interface ClinicalData {
  patient_demographics: {
    age?: number;
    sex?: string;
    height_cm?: number;
    weight_kg?: number;
    bmi_stated?: number;
  };
  vitals: {
    systolic_bp?: number;
    diastolic_bp?: number;
    heart_rate?: number;
    spo2?: number;
    temperature_c?: number;
    respiratory_rate?: number;
  };
  blood_tests: BloodTest[];
  medications: Medication[];
  clinical_scores: ClinicalScore[];
}

// --- Main result ---

export interface ProcessResult {
  status: string;
  patient_id_hash?: string;
  summary?: string;
  clinical_data?: ClinicalData;
  risk_assessment?: {
    urgency: string;
    red_flags: string[];
  };
  recommendation?: {
    recommendation_type: string;
    urgency: string;
    suggested_timeframe: string;
    red_flags: string[];
    confidence_level: string;
    evidence_basis: string;
    reasoning: string;
    model_source: string;
  };
  knowledge_base_refs?: number;
  text_length?: number;
  framework?: string;
  processing_notes?: string[];
  error?: string;
}

export interface HealthStatus {
  status: string;
  auth_enabled: boolean;
  rate_limiting: boolean;
  processors_loaded: string[];
  processor_count: number;
  using_local_models: boolean;
  cuda_available: boolean;
  gpu_info?: {
    device_name: string;
    memory_allocated_mb: number;
    memory_reserved_mb: number;
  };
  frameworks: string[];
  scopes: string[];
}

export async function fetchFrameworks(): Promise<{
  frameworks: Framework[];
  scopes: Scope[];
}> {
  const res = await fetch(`${API_BASE}/frameworks`, {
    credentials: "include",
  });
  return res.json();
}

export async function fetchFrameworkConfig(
  id: string
): Promise<FrameworkConfig> {
  const res = await fetch(`${API_BASE}/framework-config/${id}`, {
    credentials: "include",
  });
  return res.json();
}

export async function processDocument(
  file: File,
  framework: string,
  scopes: string[]
): Promise<ProcessResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("framework", framework);
  if (scopes.length > 0) formData.append("scopes", scopes.join(","));

  const res = await fetch(`${API_BASE}/process`, {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  return res.json();
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function login(password: string): Promise<{ status: string; error?: string }> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
    credentials: "include",
  });
  return res.json();
}
