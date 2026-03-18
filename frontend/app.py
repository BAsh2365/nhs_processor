# frontend/app.py

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
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
            return redirect(url_for('login_page'))

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

    @app.route('/login', methods=['GET'])
    def login_page():
        if not AUTH_ENABLED:
            return redirect(url_for('index'))
        return render_template('login.html')

    @app.route('/login', methods=['POST'])
    def login_submit():
        if not AUTH_ENABLED:
            return redirect(url_for('index'))

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
            if request.is_json:
                return jsonify({'status': 'ok'})
            return redirect(url_for('index'))

        _audit_logger.log_access(
            action="LOGIN_FAILED",
            patient_id_hash="N/A",
            user_id=request.remote_addr,
        )
        if request.is_json:
            return jsonify({'status': 'error', 'error': 'Invalid credentials'}), 401
        return render_template('login.html', error='Invalid API key'), 401

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login_page'))

    # ── Application routes ─────────────────────────────────────────────

    @app.route('/')
    @require_auth
    def index():
        """Home page"""
        return render_template('index.html')

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
            "style-src 'self' 'unsafe-inline'; "
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
