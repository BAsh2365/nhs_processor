NHS Medical Document Processor Framework for Cardiovascular Issues (NHS Personal Project/Framework  - DPCI) - Modularized Demo (MVP) 

**Note: I am NOT affiliated with the NHS. This is just a project I have made using online, open-source PDFs and Guidelines from the NHS and NICE. It is a framework for my thought process in how to use AI within Medical systems (considering ethical implications, technology guidelines, and other confounding factors). Results still need to be fine-tuned; it is NOT COMPLETE, it is NOT completely foolproof/tested, it is an unfinished idea/framework.**

This workspace contains an MVP version of the NHS medical document processor demo. AI-code assisted project with Github Copilot (By Bhargav Ashok, used GPT-5 mini and Claude 4.5 Sonnet in VS Code IDE + Claude Website for creation of project with iteration done by the codeowner). Still a Work in Progress. It is NOT a full-fledged finished Product. It is a Personal Interest Project/Framework as stated above. **There is no actual patient data used; only dummy data is used for testing**.


This AI tool is designed to assist cardiovascular surgeons within the NHS in the triage of referral letters received from GPs. These letters contain detailed patient histories and descriptions of current medical concerns. Traditionally, reviewing and prioritizing these referrals is a time-consuming task, often rotated among surgical teams. The NHS has to maintain a strict code of record management and practices when it comes to patients' data (records management guidelines found here: https://transform.england.nhs.uk/information-governance/guidance/records-management-code/records-management-code-of-practice/).

The AI model streamlines this process by summarizing key patient information and highlighting critical issues and a suggested plan of action (with three levels currently: Routine, Urgent, Emergency), enabling surgeons to quickly identify cases that require urgent attention or further investigation, including potential surgery. While a surgeon reviewing the information remains essential and is required for final decision-making, this tool shoudl hopefully reduce the time spent reviewing referrals and enhances clinical efficiency by focusing attention on the most relevant data.

## Updated app structure
 3. Directory Structure (full tree)

 nhs_processor/
 ├── backend/
 │   ├── config/
 │   │   ├── frameworks/
 │   │   │   ├── nhs_uk.json          # NHS UK framework (urgency, clinical terms, PII, branding, models)
 │   │   │   └── us_aha.json          # US AHA/ACC framework
 │   │   └── scopes/
 │   │       └── congenital_achd.json # ACHD scope overlay
 │   ├── config_loader.py             # load_framework(), list_frameworks(), list_scopes()
 │   ├── anonymizer.py                # Config-driven PII redaction
 │   ├── kb_chroma.py                 # Multi-collection ChromaDB interface
 │   ├── ingest_kb.py                 # CLI: python -m backend.ingest_kb --collection X --folder Y
 │   ├── risk_assessor.py             # Config-driven triage scoring
 │   ├── recommendation.py            # Config-driven recommendation engine
 │   └── processor.py                 # Orchestrator (MedicalDocumentProcessor)
 ├── frontend/
 │   ├── app.py                       # Flask app with /frameworks, /framework-config, /process
 │   ├── templates/index.html          # Dynamic theming via CSS custom properties
 │   ├── knowledge_pdfs/
 │   │   ├── nhs/                     # NHS/NICE guidelines (6 PDFs)
 │   │   ├── us_aha/                  # AHA/ACC guidelines (README with sources)
 │   │   └── congenital_achd/         # ESC 2020 + ACC/AHA 2025 ACHD guidelines
 │   └── test_pdfs/                   # Dummy referral files for testing
 │       ├── patient_referral_[1-5].txt
 │       ├── patient_referral_achd_[1-2].txt
 │       └── patient_referral_us_1.txt
 ├── tests/
 │   ├── test_config_loader.py        # 54 tests (no ML deps required)
 │   ├── test_anonymizer.py           # 26 tests (no ML deps required)
 │   ├── test_guideline_accuracy.py   # 46 tests verifying guideline currency
 │   ├── test_kb_chroma.py            # 16 tests (no ML deps required)
 │   ├── test_risk_assessor.py        # 27 tests (requires spacy)
 │   ├── test_recommendation.py       # 31 tests (requires torch + transformers)
 │   ├── test_processor.py            # 10 tests (requires ML deps)
 │   └── test_flask_app.py            # 33 tests (Flask tests skip without ML)
 ├── requirements.txt
 └── README.md

 4. Supported Frameworks & Scopes

 NHS UK (nhs_uk):
 - Urgency levels: EMERGENCY / URGENT / ROUTINE
 - 26 red flags, 12 surgical indicators
 - PII: NHS Number, UK postcodes redacted
 - Guidelines: NICE CG95, NG185, NG208, NG106, NG238; NHS England Cardiac Surgery Specification (Jul 2024); DTAC (updated Feb 2026)
 - Branding: NHS blue (#005EB8)

 US AHA/ACC (us_aha):
 - Urgency levels: EMERGENT / URGENT / ELECTIVE
 - 32 red flags (adds tamponade, flash pulmonary edema, LVAD, CABG, MCS)
 - PII: SSN, MRN, ZIP codes redacted
 - Guidelines: AHA/ACC 2025 ACS, 2020 VHD, 2022 HF, 2021 Chest Pain
 - Branding: AHA red (#C8102E)

 ACHD Scope (congenital_achd) — overlays any framework:
 - Adds 14 red flags: Eisenmenger syndrome, Fontan failure, protein-losing enteropathy, plastic bronchitis, single-ventricle arrhythmia, conduit obstruction, etc.
 - Adds 13 surgical indicators: Fontan revision, pulmonary valve replacement, Ebstein repair, etc.
 - Based on: ESC 2020 Adult CHD Guidelines + ACC/AHA 2025 ACHD Guidelines

 5. API Endpoints

 ┌────────┬────────────────────────┬─────────────────────────────────────────────────────────────────┐
 │ Method │        Endpoint        │                           Description                           │
 ├────────┼────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ GET    │ /                      │ Frontend UI                                                     │
 ├────────┼────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ GET    │ /health                │ Health check with framework + scope list                        │
 ├────────┼────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ GET    │ /frameworks            │ List available frameworks and scopes                            │
 ├────────┼────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ GET    │ /framework-config/<id> │ Branding/display config for a framework                         │
 ├────────┼────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ POST   │ /process               │ Upload PDF/TXT for triage (accepts framework and scopes fields) │
 └────────┴────────────────────────┴─────────────────────────────────────────────────────────────────┘

 6. Setup & Running

 # Create venv (Python 3.11 recommended for ML deps)
 python -m venv .venv
 .venv/Scripts/activate  # Windows

 pip install -r requirements.txt

 # Install spacy model
 python -m spacy download en_core_web_sm

 # Ingest knowledge base (per collection)
 python -m backend.ingest_kb --collection nhs_kb --folder frontend/knowledge_pdfs/nhs
 python -m backend.ingest_kb --collection us_aha_kb --folder frontend/knowledge_pdfs/us_aha
 python -m backend.ingest_kb --collection congenital_achd_kb --folder frontend/knowledge_pdfs/congenital_achd

 # Run the Flask app
 python frontend/app.py

 7. Running Tests

 # Run all tests (ML tests auto-skip if deps not available)
 pytest tests/ -v

 # Run only no-ML-required tests
 pytest tests/test_config_loader.py tests/test_anonymizer.py tests/test_guideline_accuracy.py tests/test_kb_chroma.py -v

 248 total tests; 164 pass without ML deps, 84 skip gracefully.

 8. Adding a New Framework

 1. Create backend/config/frameworks/<new_id>.json following the NHS/US schema
 2. Add guidelines PDFs to frontend/knowledge_pdfs/<new_id>/
 3. Ingest: python -m backend.ingest_kb --collection <new_id>_kb --folder ...
 4. Select in UI or pass framework=<new_id> in the POST request

 9. Privacy & Compliance

 - PII redacted before analysis (region-specific patterns from framework config)
 - Patient IDs SHA-256 hashed; only hash logged
 - Files deleted after processing
 - Local ML models only — no external API calls during document processing
 - DTAC (updated Feb 2026), NHS Records Management Code, HIPAA (US framework)
 - GitHub CodeQL security workflow active

 10. Tech Stack

 - BioGPT-Large (Microsoft) — medical reasoning
 - BART-large-cnn (Facebook) — summarization
 - all-MiniLM-L6-v2 — sentence embeddings
 - ChromaDB — multi-collection vector database
 - spaCy (en_core_web_sm) — NLP/NER
 - Flask — REST API
 - Tesseract/pytesseract — OCR PDF parsing

# Future Improvements

- Graph/SQL Database usage (for flexible storage and debugging)

- Larger Context Window, Temperature adjustment (randomness/creativity/nuance), for more accurate information

- Accuracy in recommendation with more specified guidelines instead of three simple levels

- Human-in-the-loop frameworks, more tests, etc.

# Ideal setup

- Scaling deployment aspects (following DTAC rules with a Cloud setup on AWS, GC, or Azure).

- Data Engineering Pipeline with large-scale data and tools like Databricks, Spark, etc. (potentially from an NHS NLP dataset: https://github.com/nhsx/language-corpus-tools)

- Needs to be containerized and scaled with Docker so that each user has their own instance. 

- System design flushed out with a GitHub CI/CD pipeline, tests, etc.


# Guidelines and extra Resources

https://nhsdigital.github.io/rap-community-of-practice/introduction_to_RAP/levels_of_RAP/

https://github.com/nhsx/open-source-policy/blob/main/open-source-policy.md#b-readmes

https://www.england.nhs.uk/long-read/artificial-intelligence-ai-and-machine-learning/

More info about NHS technology guidelines can be found online. This project adheres to those guidelines.

- Estimated RAP Level: Around Baseline (Hobby Project with public data/PDFs available on the internet).

- Completion date for a "finished product" is undecided, as it is a hobby project.


**If you have any questions about this framework project, let me know! (Email: Bhargav.ashok2023@gmail.com)**

**If you use this project, please build upon it for the greater good of its original intent (used as a tool, cardiovascular surgeons are required to review the information. It is a tool and should be used as such). Feel free to work on this project, clone it, understand it, improve it, etc. Please cite the author of this Repo when doing so (Bhargav Ashok)**

Last edit: 3/17/2026




