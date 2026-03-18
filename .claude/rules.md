# .claude/rules.md — Clinical Rules for Cardiovascular Triage AI

## Purpose

These rules govern how Claude (or any AI assistant) should reason, respond, and contribute to this codebase. They are grounded in current NHS UK and US AHA/ACC cardiovascular guidelines and DTAC requirements. All rules apply during code generation, config authoring, test writing, and any clinical content generation.

---

## 1. Absolute Safety Rules (Non-Negotiable)

### 1.1 AI is a Support Tool — Not a Decision Maker
- All AI-generated triage outputs are **advisory only**.
- Every recommendation must include explicit language stating that a qualified clinician must review the output before any clinical action.
- Never generate output that implies autonomous clinical authority.
- The system prompt in every framework config **must** contain a disclaimer equivalent to: *"This output is for clinical decision support only and must be reviewed by a qualified clinician."*

### 1.2 Conservative Urgency Bias
- When clinical signals are ambiguous, **always escalate to the higher urgency level**.
- Rule: If scoring places a case at the boundary between URGENT and EMERGENCY, default to EMERGENCY.
- This aligns with the NHS principle that delay in identifying an emergency is more harmful than over-triage.
- For ACHD/Fontan/Eisenmenger presentations, default escalation to URGENT minimum even on sparse signal.

### 1.3 No Fabrication of Clinical Evidence
- The AI must never invent clinical facts, lab values, imaging findings, or patient histories.
- If a referral letter lacks information needed for confident triage, the output must state: *"Insufficient information; recommend urgent clinician review."*
- Knowledge base snippets must never be paraphrased to change their clinical meaning.

### 1.4 No Diagnosis Generation
- The system must not generate primary diagnoses. It generates triage recommendations and highlights red flags.
- Output must never state "The patient has [condition]" — only "The referral contains signals consistent with [condition], warranting [urgency level] review."

---

## 2. Urgency Classification Rules

### 2.1 NHS UK Framework (nhs_uk) — EMERGENCY / URGENT / ROUTINE

Reference: NICE NG185 (ACS, Nov 2020, reviewed Dec 2024), NICE NG208 (Valve Disease, Nov 2021, reviewed Oct 2025), NICE NG106 (Chronic HF, Sep 2025 update), NICE CG95 (Chest Pain, confirmed current 2019), NHS England Adult Cardiac Surgery Service Specification (Jul 2024).

**EMERGENCY triggers (immediate escalation via local emergency protocol):**
- STEMI or suspected STEMI / ST-elevation pattern on documented ECG
- Aortic dissection (any type) — tearing chest/back pain, pulse deficit, mediastinal widening
- Cardiogenic shock — hypotension + haemodynamic instability, cold/clammy peripheries
- Ongoing/rest ischaemic chest pain unresponsive to GTN within 20 minutes
- Cardiac arrest, VF arrest, VT storm
- Complete heart block (third-degree AV block)
- Oxygen saturation < 90% with acute cardiac cause
- Acute decompensated heart failure with pulmonary oedema and haemodynamic compromise
- Mechanical complication of MI (VSD, papillary muscle rupture, free wall rupture)
- Pericardial tamponade — Beck's triad (hypotension, JVD, muffled heart sounds)
- Exertional syncope in the context of severe aortic stenosis (aortic gradient ≥ 40 mmHg or AVA < 1.0 cm²)

**URGENT triggers (assessment within 2 weeks per NICE ACS/chest-pain pathways):**
- NSTEMI / raised troponin (high-sensitivity assay positive) without haemodynamic instability
- Unstable angina (new-onset angina at rest or on minimal exertion, crescendo pattern)
- Symptomatic severe aortic stenosis without haemodynamic emergency (exertional dyspnoea, angina, pre-syncope) — NICE NG208 §1.4: offer intervention for symptomatic severe HVD
- Severe mitral regurgitation with symptoms or declining LVEF (< 60%) or increasing LVESD (> 45 mm) — NICE NG208 §1.5
- Suspected infective endocarditis (fever + new murmur + positive blood cultures / vegetation on echo)
- Syncope/presyncope with structural heart disease or ECG abnormality
- Rapid AF with uncontrolled ventricular rate causing haemodynamic compromise
- LVEF ≤ 35% — new finding, any aetiology
- Left main stem disease ≥ 50% stenosis on imaging/angiography
- Triple-vessel CAD with reduced LV function (LVEF < 50%)

**ROUTINE (standard outpatient pathway, 18-week RTT):**
- Stable exertional angina, moderate symptom burden, preserved haemodynamics
- Mild-moderate valve disease, asymptomatic, normal LV dimensions/function
- Hypertrophic cardiomyopathy — initial workup referral, no haemodynamic compromise
- Incidental findings requiring specialist review but no acute symptoms

### 2.2 US AHA/ACC Framework (us_aha) — EMERGENT / URGENT / ELECTIVE

Reference: 2025 ACC/AHA/ACEP/NAEMSP/SCAI Guideline for ACS (JACC/Circulation, Feb 2025, replaces 2013 STEMI + 2014 NSTE-ACS guidelines); ACC/AHA 2020 VHD Guideline; AHA/ACC/HFSA 2022 Heart Failure Guideline; AHA/ACC/ASE/CHEST 2021 Chest Pain Evaluation Guideline.

**EMERGENT triggers (immediate cath lab activation or ED protocol):**
- STEMI — ECG acquired and interpreted within 10 min of presentation; FMC-to-device goal ≤ 90 min (2025 ACS Guideline §3.2)
- Resuscitated cardiac arrest with STEMI — preferential EMS transport to PPCI-capable centre
- Cardiogenic shock complicating ACS — consider short-term MCS as bridge to revascularisation or surgery
- Aortic dissection (Type A) — immediate surgical consultation
- Cardiac tamponade
- Flash pulmonary oedema with haemodynamic instability
- Sustained VT / VF / complete heart block with haemodynamic compromise
- Mechanical complication of MI — managed at facility with cardiac surgical expertise (2025 ACS Guideline §6.3)

**URGENT triggers (cardiology consultation within 72 hours):**
- NSTEMI at intermediate-high ischaemic risk — invasive strategy with intent for revascularisation during hospitalisation (2025 ACS Guideline §5.1)
- Unstable angina (NSTE-ACS at low ischaemic risk — selective invasive or routine invasive strategy per risk)
- Symptomatic severe AS (AVA < 1.0 cm², mean gradient ≥ 40 mmHg) — SAVR or TAVR evaluation per Heart Team (2020 VHD Guideline)
- Severe MR with symptoms, or LVEF 30–60%, or LVESD ≥ 40 mm
- HFrEF (LVEF ≤ 40%) newly identified — initiation of GDMT (ARNI/ACEi/ARB + BB + MRA + SGLT2i per 2022 HF Guideline)
- LVAD candidacy evaluation — refractory HF, LVEF ≤ 25%, elevated filling pressures
- CABG indication — three-vessel CAD or left main disease

**ELECTIVE (standard outpatient evaluation with non-invasive workup):**
- Stable CAD, preserved LV function, controlled symptoms on GDMT
- Moderate valve disease, asymptomatic, normal indices
- Risk stratification for known stable coronary disease

### 2.3 ACHD / Congenital Scope Overlay (congenital_achd)

Reference: ACC/AHA/HRS/ISACHD/SCAI 2025 Guideline for Adults with CHD (replaces 2018 guideline); ESC 2020 Guidelines on Adult Congenital Heart Disease (still current as of Mar 2026).

**Additional EMERGENCY signals:**
- Fontan failure / failing Fontan circulation — any evidence of declining cardiac output, protein-losing enteropathy (PLE), plastic bronchitis, hepatic dysfunction
- Eisenmenger syndrome / crisis — acute cyanotic decompensation
- Arrhythmia in single-ventricle physiology
- Conduit obstruction with haemodynamic compromise

**Additional URGENT signals:**
- Protein-losing enteropathy (Fontan) — albumin < 25 g/L, peripheral oedema
- Baffle leak or obstruction (post-Mustard/Senning)
- Exercise intolerance with desaturation (SpO₂ drop > 5% on exercise)
- Pulmonary hypertension in ACHD
- Endocarditis on prosthetic material

**Complexity classification** (ACC/AHA 2025 ACHD):
- **Simple** (every 3–5 years): isolated small ASD, repaired VSD without residua, mild PS
- **Moderate** (every 1–2 years): repaired TOF, coarctation, Ebstein (mild-moderate), partial AV canal
- **Severe** (every 6–12 months): Fontan circulation, Eisenmenger, TGA (post-arterial/atrial switch), single-ventricle, pulmonary atresia

---

## 3. Clinical Content Rules

### 3.1 Red Flag Accuracy
- Every term in the `red_flags` and `surgical_indicators` arrays in framework JSON configs must correspond to a recognised clinical entity documented in the referenced guidelines.
- Do not invent symptom descriptors — use exact terminology from NICE, AHA/ACC, or ESC guideline text.
- Before adding any new red flag, verify it appears in a guideline published within the last 5 years (2021–2026).

### 3.2 Guideline Citation Integrity
- All guideline references in config files must include:
  - Full official short title (e.g., "NICE NG185")
  - Publication year and last review/update year
  - Current status (active / replaced / under review)
- Do **not** cite guidelines that have been superseded without noting the replacement. For example:
  - The 2013 ACCF/AHA STEMI guideline and 2014 NSTE-ACS guideline are superseded by the **2025 ACC/AHA/ACEP/NAEMSP/SCAI ACS Guideline**.
  - The 2018 AHA/ACC ACHD guideline is superseded by the **2025 ACC/AHA/HRS/ISACHD/SCAI ACHD Guideline**.
- NICE NG196 is the **atrial fibrillation** guideline — it must never be cited as an ACHD or cardiovascular surgical reference.

### 3.3 Urgency Timeframe Wording
- NHS timeframes must reference the NHS Constitution 18-week RTT for non-urgent referrals.
- Emergency timeframes must use: *"Immediate escalation via local emergency protocol (ED/cardiology)."*
- Urgent timeframes must reference the relevant NICE pathway interval (e.g., "within 2 weeks, aligned to NICE NG185").
- US urgent timeframes must use: *"Urgent cardiology consultation within 72 hours per AHA/ACC pathway."*

### 3.4 Surgical Indicators
- Surgical indicators should reflect accepted indications for cardiac surgery as of current guidelines:
  - CABG: left main disease ≥ 50%, three-vessel CAD with LVEF < 50%, failed PCI
  - SAVR / TAVR: symptomatic severe AS (2020 VHD Guideline / NICE NG208)
  - Mitral valve surgery: symptomatic severe MR, or asymptomatic with LVEF < 60% / LVESD > 45 mm (NICE NG208 §1.5.3) / LVESD ≥ 40 mm (ACC/AHA 2020 VHD)
  - Cardiac transplant / LVAD: refractory HF, LVEF ≤ 25%, NYHA class III–IV on maximally tolerated GDMT

### 3.5 Scoring Weight Calibration
- The default `emergency_pattern_weight` of 5.0 is intentionally high to prevent under-triage of emergencies.
- Do not reduce emergency thresholds without clinical review and documented rationale.
- If adding new weights for new frameworks, document the clinical basis in the framework JSON `notes` field.

---

## 4. Code Quality Rules

### 4.1 PII Handling
- The `anonymize_text()` function must be called on **all** text before it is passed to any AI model.
- Never log, print, or store raw patient text. Only anonymised text and hashed patient IDs may appear in logs.
- When adding new framework PII patterns, test them against at least three representative examples (positive and negative).
- PII patterns must be validated with `re.compile()` before deployment — see `_validate_patterns()` in `config_loader.py`.

### 4.2 Model Loading
- ML models are expensive to load. Always check the lazy-load cache (`_model_cache`) before calling `AutoModelForCausalLM.from_pretrained()`.
- CUDA OOM must be caught and the system must fall back to CPU gracefully without raising an unhandled exception.
- Single-worker deployment (Gunicorn `--workers 1`) is mandatory when using CUDA — do not increase without architectural changes.

### 4.3 Audit Logging
- Every document processed must produce `log_access()` and `log_recommendation()` calls with the patient hash.
- `log_error()` must be called on any exception, with the component name and truncated error message.
- Audit logs must never be deleted programmatically. They are append-only by design.

### 4.4 Error Handling
- The `process_document()` and `process_text()` methods must never raise an unhandled exception to the caller.
- All exceptions must be caught, logged, and converted to a structured `{"status": "error", "error": "..."}` response.
- Error messages returned to the client must never include stack traces or internal paths.

### 4.5 Test Coverage Requirements
- Any change to urgency scoring logic must be accompanied by at least one new test in `test_risk_assessor.py` or `test_recommendation.py`.
- Any change to PII patterns must be accompanied by tests in `test_anonymizer.py`.
- Any new guideline reference added to a framework config must be validated in `test_guideline_accuracy.py`.
- The "no-ML" test suite (`test_config_loader.py`, `test_anonymizer.py`, `test_guideline_accuracy.py`, `test_kb_chroma.py`) must always pass in CI.

### 4.6 Dependency Pinning
- Keep `transformers`, `torch`, and `chromadb` pinned to tested versions.
- The `tokenizers` version must satisfy the constraint `>=0.21,<0.22` to maintain transformers compatibility.
- When upgrading ML dependencies, rerun all 248 tests before merging.

---

## 5. Prompt Engineering Rules

### 5.1 System Prompt Requirements
Every framework's `prompts.system_context` must include all of the following:
1. The system's role (decision-support, not autonomous clinical authority)
2. The applicable clinical guideline set
3. A prohibition against fabricating clinical facts
4. An instruction to flag insufficient information
5. An instruction to use the knowledge base for evidence references
6. A formatting directive (executive-style, neatly formatted)

### 5.2 Urgency Level Consistency
- The urgency levels used in the system prompt (`schema_hint_suffix`) must exactly match the `urgency_levels` array in the same framework config.
- If `urgency_levels` = `["EMERGENT", "URGENT", "ELECTIVE"]` (US), the prompt must not say "EMERGENCY" or "ROUTINE".

### 5.3 Phi-3 / Ollama Prompt Structure
- Temperature must be kept at or near 0.1 for clinical reasoning (low randomness).
- `repeat_penalty` ≥ 1.2 to suppress model hallucination loops.
- `num_predict` should be capped at 512 tokens to prevent excessively long unstructured outputs.
- Prompts must be structured with explicit section markers: (1) clinical assessment, (2) urgency level, (3) red flags, (4) next steps.

---

## 6. DTAC and Regulatory Rules

### 6.1 DTAC Compliance (updated Feb 2026)
- The system must be assessed against the **updated DTAC form (Feb 2026)** before any NHS deployment. The previous form is retired as of 6 April 2026.
- Clinical safety must be documented per **DCB0129** (manufacturer clinical risk management).
- Deploying organisations must complete **DCB0160** assessments.
- A named **Clinical Safety Officer (CSO)** is required.
- A **Data Protection Impact Assessment (DPIA)** must be completed before handling any real patient data.

### 6.2 Data Protection
- All processing must be UK-GDPR compliant.
- Patient data must be processed under a lawful basis — in a clinical context, this is likely Article 9(2)(h) (medical diagnosis / healthcare treatment).
- Files must be deleted after processing (see `frontend/app.py` upload cleanup).
- No patient data may be transmitted to external APIs. Local inference only.

### 6.3 NHS Records Management
- Audit logs must be retained per the NHS Records Management Code of Practice.
- Logs must be timestamped and append-only; no retroactive modification.
- Patient ID hashing (SHA-256) ensures identifiers in logs cannot be reversed to re-identify patients without the original key.

### 6.4 This System is NOT a Medical Device
- In its current state, this system is a **research demonstration** and is not registered as a medical device with the MHRA.
- Before clinical deployment, MHRA classification must be sought. AI-driven clinical decision support may fall under Software as a Medical Device (SaMD) regulations.
- The system must not be marketed or described as CE/UKCA-marked.

---

## 7. Scope Boundary Rules

### 7.1 Cardiovascular and Cardiothoracic Only
- This system is scoped to **adult cardiovascular and cardiothoracic** referrals.
- It must not be used to triage paediatric cardiac, general surgical, orthopaedic, or other non-cardiac referrals.
- If non-cardiovascular content is detected in a referral letter, the output should note: *"This triage system is calibrated for cardiovascular/cardiothoracic referrals only. Non-cardiac content detected — manual review recommended."*

### 7.2 Adult Patients Only
- All frameworks are calibrated for adult patients (≥ 18 years).
- Paediatric congenital heart disease presentations may appear in ACHD scope, but only for adult patients who have transitioned from paediatric services.
- Reference values (e.g., LVESD thresholds, LVEF cut-offs) are validated for adult populations.

### 7.3 GP Referral Letters
- The system is designed to process **GP-to-specialist referral letters**, not discharge summaries, operative notes, or lab reports.
- Processing non-referral document types may produce unreliable triage outputs.

---

## 8. Guideline Version Control

When updating guideline references, always check:

| Framework | Key Guidelines to Verify |
|-----------|--------------------------|
| NHS UK    | NICE NG185 (ACS) — reviewed Dec 2024, active |
| NHS UK    | NICE NG208 (VHD) — reviewed Oct 2025, TAVI update in progress |
| NHS UK    | NICE NG106 (CHF) — updated Sep 2025 (SGLT2i added) |
| NHS UK    | NICE CG95 (Chest Pain) — confirmed current via 2019 surveillance |
| NHS UK    | NICE NG238 (CVD Risk) — published Dec 2023, reviewed Sep 2025 |
| NHS UK    | NHS England Adult Cardiac Surgery Service Specification — Jul 2024 |
| US AHA    | 2025 ACC/AHA/ACEP/NAEMSP/SCAI ACS Guideline — Feb 2025 (replaces 2013 STEMI + 2014 NSTE-ACS) |
| US AHA    | ACC/AHA 2020 VHD Guideline — still current |
| US AHA    | AHA/ACC/HFSA 2022 HF Guideline (with 2023 corrections) — still current |
| US AHA    | AHA/ACC/ASE/CHEST 2021 Chest Pain Evaluation Guideline (with 2023 corrections) — still current |
| ACHD      | ACC/AHA/HRS/ISACHD/SCAI 2025 ACHD Guideline — Dec 2025 (replaces 2018) |
| ACHD      | ESC 2020 ACHD Guidelines — still current as of Mar 2026 |

> Guideline check frequency: review this table **at least every 6 months** or when NICE/AHA/ACC publish updates.

---

## 9. Prohibited Actions

The following actions are **prohibited** in this codebase:

- ❌ Sending patient text (even anonymised) to any external API (OpenAI, Anthropic, Google, etc.)
- ❌ Reducing the `conservative safety bias` without documented clinical review
- ❌ Generating outputs that could be interpreted as a definitive clinical diagnosis
- ❌ Removing the clinician-review disclaimer from any output
- ❌ Lowering the `emergency_threshold` below 5.0 without documented justification
- ❌ Using guidelines published before 2021 as primary references (unless no newer guideline exists)
- ❌ Storing raw patient data in logs, databases, or any persistent storage
- ❌ Bypassing PII anonymisation for any reason, including testing
- ❌ Running with more than one Gunicorn worker when CUDA is active
- ❌ Citing NICE NG196 (AF) as a cardiovascular surgical reference
- ❌ Citing the 2013 STEMI or 2014 NSTE-ACS guidelines without noting they are superseded by the 2025 ACS guideline
