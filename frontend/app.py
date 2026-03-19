# frontend/app.py

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from functools import wraps
import os
import sys
import uuid
import json
import hmac
import secrets

# Fix path to find backend module
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.processor import MedicalDocumentProcessor  # noqa: E402
from backend.config_loader import load_framework, list_frameworks, list_scopes  # noqa: E402
from backend.logger import NHSComplianceLogger  # noqa: E402


def create_app():
    """Application factory for WSGI servers (gunicorn, waitress)."""
    app = Flask(__name__)

    # CORS: allow localhost origins for Next.js dev server
    CORS(app, supports_credentials=True, origins=[
        "http://127.0.0.1:*",
        "http://localhost:*",
    ])

    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

    # Secret key for session signing — generate once, store in .env for persistence
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

    # ── Authentication configuration ──────────────────────────────────
    #
    # Two modes supported (checked in order):
    #
    # 1. API key (header):  X-API-Key: <key>
    #    - For programmatic/API access
    #    - Set via NHS_API_KEYS env var (comma-separated list of valid keys)
    #
    # 2. Session login (browser):  POST /login with {"password": "<key>"}
    #    - For the web UI
    #    - Uses the same API keys list as valid passwords
    #
    # If NHS_API_KEYS is unset or empty, auth is DISABLED (dev mode).
    # In production you MUST set this.
    _raw_keys = os.environ.get('NHS_API_KEYS', '').strip()
    API_KEYS = [k.strip() for k in _raw_keys.split(',') if k.strip()] if _raw_keys else []
    AUTH_ENABLED = len(API_KEYS) > 0

    if AUTH_ENABLED:
        print(f"[Auth] API key authentication ENABLED ({len(API_KEYS)} key(s) configured)")
    else:
        print("[Auth] WARNING: Authentication DISABLED — set NHS_API_KEYS env var for production")

    # ── Rate limiting ─────────────────────────────────────────────────
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=["200 per hour"],
            storage_uri="memory://",
        )
        print("[RateLimit] Rate limiting ENABLED")
    except ImportError:
        limiter = None
        print("[RateLimit] flask-limiter not installed — rate limiting DISABLED")

    # ── Upload folder ─────────────────────────────────────────────────
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    ALLOWED_EXTENSIONS = {'pdf', 'txt'}

    # Cache processors by (framework_id, scopes) key — bounded to prevent memory exhaustion
    _processor_cache = {}
    _MAX_CACHED_PROCESSORS = 4

    # Audit logger
    _audit_logger = NHSComplianceLogger()

    # ── Helpers ────────────────────────────────────────────────────────

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def _check_api_key(key):
        """Constant-time comparison against all valid keys."""
        return any(hmac.compare_digest(key, valid) for valid in API_KEYS)

    def require_auth(f):
        """Decorator: require valid API key or authenticated session."""
        @wraps(f)
        def decorated(*args, **kwargs):
            if not AUTH_ENABLED:
                return f(*args, **kwargs)

            # Check X-API-Key header first (programmatic access)
            api_key = request.headers.get('X-API-Key', '').strip()
            if api_key and _check_api_key(api_key):
                return f(*args, **kwargs)

            # Check session (browser login)
            if session.get('authenticated'):
                return f(*args, **kwargs)

            # Not authenticated
            if request.is_json or request.headers.get('X-API-Key'):
                return jsonify({'status': 'error', 'error': 'Unauthorized — provide a valid X-API-Key header'}), 401
            return jsonify({'status': 'error', 'error': 'Unauthorized'}), 401

        return decorated

    def _get_processor(framework_id: str = "nhs_uk", scopes: list = None) -> MedicalDocumentProcessor:
        """Get or create a processor for the given framework+scopes combo (bounded cache)."""
        known = set(list_frameworks())
        if framework_id not in known:
            raise ValueError(f"Unknown framework: {framework_id}")

        known_scopes = set(list_scopes())
        for s in (scopes or []):
            if s not in known_scopes:
                raise ValueError(f"Unknown scope: {s}")

        cache_key = (framework_id, tuple(scopes or []))
        if cache_key not in _processor_cache:
            if len(_processor_cache) >= _MAX_CACHED_PROCESSORS:
                oldest_key = next(iter(_processor_cache))
                del _processor_cache[oldest_key]
                print(f"[App] Evicted processor cache entry: {oldest_key}")

            print(f"[App] Creating processor for {framework_id} + scopes={scopes or []}")
            _processor_cache[cache_key] = MedicalDocumentProcessor(
                user_id="WEBAPP",
                framework_id=framework_id,
                scopes=scopes
            )
        return _processor_cache[cache_key]

    # ── Auth routes ────────────────────────────────────────────────────

    @app.route('/login', methods=['POST'])
    def login_submit():
        if not AUTH_ENABLED:
            return jsonify({'status': 'ok', 'message': 'Auth disabled'})

        password = ''
        if request.is_json:
            password = (request.json or {}).get('password', '')
        else:
            password = request.form.get('password', '')

        if _check_api_key(password):
            session['authenticated'] = True
            session.permanent = True
            _audit_logger.log_access(
                action="LOGIN_SUCCESS",
                patient_id_hash="N/A",
                user_id=request.remote_addr,
            )
            return jsonify({'status': 'ok'})

        _audit_logger.log_access(
            action="LOGIN_FAILED",
            patient_id_hash="N/A",
            user_id=request.remote_addr,
        )
        return jsonify({'status': 'error', 'error': 'Invalid credentials'}), 401

    @app.route('/logout', methods=['POST'])
    def logout():
        session.clear()
        return jsonify({'status': 'ok'})

    # ── Application routes ─────────────────────────────────────────────

    @app.route('/')
    def index():
        """API Root"""
        return jsonify({
            "name": "NHS Medical Document Processor API",
            "version": "1.0.0",
            "status": "online",
            "endpoints": [
                "/health",
                "/frameworks",
                "/framework-config/<id>",
                "/process",
                "/login"
            ]
        })

    @app.route('/frameworks', methods=['GET'])
    @require_auth
    def get_frameworks():
        """Return available frameworks and scopes"""
        frameworks = []
        for fid in list_frameworks():
            try:
                cfg = load_framework(fid)
                frameworks.append({
                    "id": fid,
                    "name": cfg.get("name", fid),
                    "description": cfg.get("description", "")
                })
            except Exception:
                frameworks.append({"id": fid, "name": fid, "description": ""})

        scopes = []
        for sid in list_scopes():
            try:
                scope_path = os.path.join(PROJECT_ROOT, "backend", "config", "scopes", f"{sid}.json")
                with open(scope_path, "r", encoding="utf-8") as f:
                    scope_cfg = json.load(f)
                scopes.append({
                    "id": sid,
                    "name": scope_cfg.get("name", sid),
                    "description": scope_cfg.get("description", "")
                })
            except Exception:
                scopes.append({"id": sid, "name": sid, "description": ""})

        return jsonify({"frameworks": frameworks, "scopes": scopes})

    @app.route('/framework-config/<framework_id>', methods=['GET'])
    @require_auth
    def get_framework_config(framework_id):
        """Return branding/display info for a framework"""
        try:
            cfg = load_framework(framework_id)
            return jsonify({
                "id": cfg.get("id", framework_id),
                "name": cfg.get("name", framework_id),
                "branding": cfg.get("branding", {}),
                "urgency_levels": cfg.get("urgency_levels", ["EMERGENCY", "URGENT", "ROUTINE"])
            })
        except FileNotFoundError:
            return jsonify({"error": f"Framework '{framework_id}' not found"}), 404

    @app.route('/process', methods=['POST'])
    @require_auth
    def process_document():
        """Process uploaded medical document"""

        # Resolve framework and scopes from form data
        framework_id = request.form.get('framework', 'nhs_uk')
        scopes_str = request.form.get('scopes', '')
        scopes = [s.strip() for s in scopes_str.split(',') if s.strip()] if scopes_str else []

        try:
            processor = _get_processor(framework_id, scopes)
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 400
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': f'Failed to load framework: {e}'
            }), 500

        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'error': 'No file uploaded'
            }), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({
                'status': 'error',
                'error': 'No file selected'
            }), 400

        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'error': 'File type not allowed. Please upload PDF or TXT files.'
            }), 400

        filepath = None
        try:
            ext = secure_filename(file.filename).rsplit('.', 1)[-1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, unique_name)
            file.save(filepath)

            print()
            print("=" * 60)
            print(f"Processing: {file.filename} (framework={framework_id}, scopes={scopes})")
            print("=" * 60)

            _audit_logger.log_access(
                action="DOCUMENT_UPLOAD",
                patient_id_hash="pending",
                user_id=request.remote_addr or "WEBAPP",
                details=f"framework={framework_id}, scopes={scopes}"
            )

            result = processor.process_document(filepath)

            if result.get('status') == 'success':
                _audit_logger.log_recommendation(
                    patient_id_hash=result.get('patient_id_hash', 'unknown'),
                    recommendation=result.get('recommendation', {})
                )
                print("=" * 60)
                print("Processing completed successfully")
                print("=" * 60)
                print()

            return jsonify(result)

        except Exception as e:
            print(f"Error processing document: {e}")
            import traceback
            traceback.print_exc()
            _audit_logger.log_error(
                where="process_document",
                patient_id_hash="unknown",
                error=str(e)
            )

            return jsonify({
                'status': 'error',
                'error': 'An internal error has occurred. Please try again later.'
            }), 500

        finally:
            if filepath:
                try:
                    os.remove(filepath)
                except Exception:
                    pass

    # Apply rate limit to /process if limiter is available
    if limiter:
        # 10 documents per minute per IP, 60 per hour
        process_document = limiter.limit("10 per minute;60 per hour")(process_document)

    # ── Guidelines reference data ────────────────────────────────────

    _SHARED_EQUATIONS = [
        {
            "id": "egfr_ckd_epi",
            "name": "eGFR (CKD-EPI 2021)",
            "category": "renal",
            "formula": "142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^(-1.200) × 0.9938^Age × (1.012 if female)",
            "reference": "Inker LA, et al. N Engl J Med. 2021;385(19):1737-1749",
            "use_case": "Renal function assessment for pre-operative risk and drug dosing"
        },
        {
            "id": "cha2ds2vasc",
            "name": "CHA₂DS₂-VASc Score",
            "category": "stroke_risk",
            "formula": "CHF(1) + Hypertension(1) + Age≥75(2) + Diabetes(1) + Stroke/TIA(2) + Vascular disease(1) + Age 65-74(1) + Sex(female=1)",
            "reference": "Lip GYH, et al. Chest. 2010;137(2):263-272",
            "use_case": "Stroke risk stratification in atrial fibrillation to guide anticoagulation"
        },
        {
            "id": "hasbled",
            "name": "HAS-BLED Score",
            "category": "bleeding_risk",
            "formula": "Hypertension(1) + Abnormal renal/liver(1-2) + Stroke(1) + Bleeding(1) + Labile INR(1) + Elderly(1) + Drugs/alcohol(1-2)",
            "reference": "Pisters R, et al. Chest. 2010;138(5):1093-1100",
            "use_case": "Bleeding risk assessment in patients on anticoagulation"
        },
        {
            "id": "qtc_bazett",
            "name": "QTc (Bazett's Formula)",
            "category": "ecg",
            "formula": "QTc = QT / √(RR interval)",
            "reference": "Bazett HC. Heart. 1920;7:353-370",
            "use_case": "Corrected QT interval for heart rate, used in drug safety monitoring and arrhythmia risk"
        },
        {
            "id": "bmi",
            "name": "Body Mass Index",
            "category": "anthropometry",
            "formula": "BMI = weight(kg) / height(m)²",
            "reference": "WHO Expert Consultation. Lancet. 2004;363(9403):157-163",
            "use_case": "Nutritional status and surgical risk stratification"
        },
        {
            "id": "bsa_dubois",
            "name": "Body Surface Area (Du Bois)",
            "category": "anthropometry",
            "formula": "BSA = 0.007184 × height(cm)^0.725 × weight(kg)^0.425",
            "reference": "Du Bois D, Du Bois EF. Arch Intern Med. 1916;17:863-871",
            "use_case": "Drug dosing, cardiac index calculation, valve area indexing"
        },
        {
            "id": "map",
            "name": "Mean Arterial Pressure",
            "category": "haemodynamics",
            "formula": "MAP = DBP + (SBP - DBP) / 3",
            "reference": "Standard haemodynamic formula",
            "use_case": "Organ perfusion assessment and haemodynamic monitoring"
        }
    ]

    _GUIDELINES_DATA = {
        "nhs_uk": {
            "framework": "nhs_uk",
            "guidelines": [
                {
                    "id": "nice_cg95",
                    "title": "Chest Pain of Recent Onset: Assessment and Diagnosis",
                    "organization": "NICE",
                    "code": "CG95",
                    "year": 2010,
                    "last_updated": "2016 (confirmed 2019)",
                    "category": "chest_pain",
                    "url": "https://www.nice.org.uk/guidance/cg95",
                    "summary": "Guidance on assessing and diagnosing recent-onset chest pain. Covers initial assessment, diagnosis of ACS, and stable angina evaluation pathways.",
                    "key_recommendations": [
                        "Use clinical assessment to estimate likelihood of CAD",
                        "Offer CT coronary angiography as first-line investigation for stable chest pain",
                        "Use HEART score or clinical judgement for ACS risk stratification"
                    ]
                },
                {
                    "id": "nice_ng185",
                    "title": "Acute Coronary Syndromes",
                    "organization": "NICE",
                    "code": "NG185",
                    "year": 2020,
                    "last_updated": "2024",
                    "category": "acs",
                    "url": "https://www.nice.org.uk/guidance/ng185",
                    "summary": "Management of acute coronary syndromes including NSTEMI and unstable angina. Covers diagnosis, risk assessment, and treatment pathways.",
                    "key_recommendations": [
                        "Use high-sensitivity troponin testing for diagnosis",
                        "Offer coronary angiography within 72 hours for intermediate-high risk NSTEMI",
                        "Dual antiplatelet therapy for 12 months post-ACS"
                    ]
                },
                {
                    "id": "nice_ng208",
                    "title": "Heart Valve Disease Presenting in Adults",
                    "organization": "NICE",
                    "code": "NG208",
                    "year": 2021,
                    "last_updated": "2025",
                    "category": "valve_disease",
                    "url": "https://www.nice.org.uk/guidance/ng208",
                    "summary": "Investigation, management and monitoring of heart valve disease in adults. Includes guidance on timing of intervention.",
                    "key_recommendations": [
                        "Echocardiography as first-line investigation for suspected valve disease",
                        "Refer for surgical assessment when symptoms develop or LV dysfunction occurs",
                        "Annual follow-up for moderate or severe asymptomatic valve disease"
                    ]
                },
                {
                    "id": "nice_ng106",
                    "title": "Chronic Heart Failure in Adults",
                    "organization": "NICE",
                    "code": "NG106",
                    "year": 2018,
                    "last_updated": "Sep 2025",
                    "category": "heart_failure",
                    "url": "https://www.nice.org.uk/guidance/ng106",
                    "summary": "Diagnosis and management of chronic heart failure. Updated 2025 to include SGLT2 inhibitor recommendations.",
                    "key_recommendations": [
                        "NT-proBNP as first-line diagnostic test (refer if >400 ng/L)",
                        "ACEi/ARB + beta-blocker + MRA as foundation therapy for HFrEF",
                        "SGLT2 inhibitors recommended for HFrEF regardless of diabetes status",
                        "Consider CRT or ICD based on ejection fraction and QRS duration"
                    ]
                },
                {
                    "id": "nice_ng238",
                    "title": "Cardiovascular Disease: Risk Assessment and Reduction",
                    "organization": "NICE",
                    "code": "NG238",
                    "year": 2023,
                    "last_updated": "Sep 2025",
                    "category": "risk_assessment",
                    "url": "https://www.nice.org.uk/guidance/ng238",
                    "summary": "Risk assessment and lipid modification for primary and secondary prevention of cardiovascular disease.",
                    "key_recommendations": [
                        "Use QRISK3 for 10-year CVD risk assessment",
                        "Offer statin therapy if 10-year risk ≥10%",
                        "Consider PCSK9 inhibitors for familial hypercholesterolaemia or high-risk patients"
                    ]
                },
                {
                    "id": "nhs_cardiac_spec",
                    "title": "Adult Cardiac Surgery Service Specification",
                    "organization": "NHS England",
                    "code": "E05/S/a",
                    "year": 2024,
                    "last_updated": "Jul 2024",
                    "category": "surgical",
                    "url": "https://www.england.nhs.uk/commissioning/spec-services/npc-crg/group-a/a05/",
                    "summary": "Service specification for adult cardiac surgical services including referral pathways, waiting times, and quality standards.",
                    "key_recommendations": [
                        "18-week referral-to-treatment standard for routine cases",
                        "Urgent cases assessed within 2 weeks",
                        "Emergency cases immediate escalation to cardiac surgical team"
                    ]
                }
            ],
            "equations": _SHARED_EQUATIONS
        },
        "us_aha": {
            "framework": "us_aha",
            "guidelines": [
                {
                    "id": "aha_chest_pain_2021",
                    "title": "2021 AHA/ACC Guideline for the Evaluation and Diagnosis of Chest Pain",
                    "organization": "AHA/ACC",
                    "code": "2021 Chest Pain",
                    "year": 2021,
                    "last_updated": "2021",
                    "category": "chest_pain",
                    "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001029",
                    "summary": "Evidence-based guideline for evaluating and diagnosing chest pain. Covers initial assessment, risk stratification, and diagnostic testing pathways for acute and stable chest pain presentations.",
                    "key_recommendations": [
                        "Use structured risk assessment tools (HEART, TIMI, GRACE) for ACS evaluation",
                        "CCTA recommended as first-line for low-to-intermediate risk stable chest pain",
                        "High-sensitivity troponin preferred for acute chest pain evaluation",
                        "Shared decision-making for diagnostic testing in stable chest pain"
                    ]
                },
                {
                    "id": "aha_vhd_2020",
                    "title": "2020 ACC/AHA Guideline for the Management of Patients With Valvular Heart Disease",
                    "organization": "ACC/AHA",
                    "code": "2020 VHD",
                    "year": 2020,
                    "last_updated": "2021 (focused update)",
                    "category": "valve_disease",
                    "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000000923",
                    "summary": "Comprehensive guideline for valvular heart disease management including diagnosis, monitoring, and intervention timing for all major valve lesions.",
                    "key_recommendations": [
                        "Transthoracic echocardiography as primary diagnostic tool for VHD",
                        "Intervention recommended when symptoms develop or LV dysfunction criteria met",
                        "TAVR or SAVR decision based on patient risk, anatomy, and shared decision-making",
                        "Surveillance intervals based on disease severity (annual for severe, 3-5 years for mild)"
                    ]
                },
                {
                    "id": "aha_hf_2022",
                    "title": "2022 AHA/ACC/HFSA Guideline for the Management of Heart Failure",
                    "organization": "AHA/ACC/HFSA",
                    "code": "2022 HF",
                    "year": 2022,
                    "last_updated": "2023 (focused update)",
                    "category": "heart_failure",
                    "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001063",
                    "summary": "Updated guideline for heart failure management with revised classification (HFrEF, HFmrEF, HFpEF, HFimpEF) and new therapy recommendations including SGLT2 inhibitors.",
                    "key_recommendations": [
                        "GDMT with ARNi/ACEi/ARB + beta-blocker + MRA + SGLT2i for HFrEF",
                        "SGLT2 inhibitors recommended for HFrEF, HFmrEF, and HFpEF (Class 2a)",
                        "BNP/NT-proBNP for diagnosis and prognosis",
                        "Consider CRT for LVEF ≤35%, LBBB, QRS ≥150 ms"
                    ]
                },
                {
                    "id": "aha_acs_2025",
                    "title": "2025 ACC/AHA Guideline for the Management of Acute Coronary Syndromes",
                    "organization": "ACC/AHA",
                    "code": "2025 ACS",
                    "year": 2025,
                    "last_updated": "2025",
                    "category": "acs",
                    "url": "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001309",
                    "summary": "Updated guideline for ACS management covering STEMI, NSTEMI, and unstable angina. Includes revised revascularization strategies and updated antithrombotic therapy recommendations.",
                    "key_recommendations": [
                        "High-sensitivity troponin with rapid rule-out protocols (0/1h or 0/3h)",
                        "Early invasive strategy within 24 hours for high-risk NSTEMI",
                        "DAPT duration individualized based on ischemic and bleeding risk",
                        "Routine pre-treatment with P2Y12 inhibitors no longer recommended for NSTEMI"
                    ]
                }
            ],
            "equations": _SHARED_EQUATIONS
        }
    }

    @app.route('/guidelines/<framework_id>')
    def get_guidelines(framework_id):
        """Return structured guideline reference data — unauthenticated."""
        if framework_id not in _GUIDELINES_DATA:
            return jsonify({"error": f"Unknown framework: {framework_id}"}), 404
        return jsonify(_GUIDELINES_DATA[framework_id])

    @app.route('/health')
    def health():
        """Health check endpoint — unauthenticated so load balancers can probe."""
        import torch
        cuda_available = torch.cuda.is_available()
        gpu_info = {}
        if cuda_available:
            gpu_info = {
                "device_name": torch.cuda.get_device_name(0),
                "memory_allocated_mb": round(torch.cuda.memory_allocated(0) / 1024 / 1024, 1),
                "memory_reserved_mb": round(torch.cuda.memory_reserved(0) / 1024 / 1024, 1),
            }

        processors_loaded = list(str(k) for k in _processor_cache.keys())

        return jsonify({
            'status': 'healthy',
            'auth_enabled': AUTH_ENABLED,
            'rate_limiting': limiter is not None,
            'processors_loaded': processors_loaded,
            'processor_count': len(_processor_cache),
            'using_local_models': True,
            'cuda_available': cuda_available,
            'gpu_info': gpu_info,
            'frameworks': list_frameworks(),
            'scopes': list_scopes()
        })

    # ── Security headers ──────────────────────────────────────────────

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        )
        # HSTS — only effective behind TLS, harmless otherwise
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # ── Startup banner ────────────────────────────────────────────────
    print("=" * 60)
    print("Medical Document Processor - Starting")
    print("=" * 60)
    print("Using LOCAL AI models (compliant, no external APIs)")
    print("Models will be loaded on first request (lazy initialization)")
    print()

    return app


# For direct `python frontend/app.py` usage (dev only)
if __name__ == '__main__':
    app = create_app()
    print()
    print("=" * 60)
    print("Starting Flask development server...")
    print("For production, use: gunicorn -w 1 -b 0.0.0.0:5000 'wsgi:app'")
    print("=" * 60)
    print("Open your browser to: http://localhost:5000")
    print("=" * 60)
    print()

    app.run(host='127.0.0.1', port=5000, debug=False)
