# frontend/app.py

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import sys

# Fix path to find backend module
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.processor import MedicalDocumentProcessor
from backend.config_loader import load_framework, list_frameworks, list_scopes

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Setup upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'txt'}

# Cache processors by (framework_id, scopes) key
_processor_cache = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_processor(framework_id: str = "nhs_uk", scopes: list = None) -> MedicalDocumentProcessor:
    """Get or create a processor for the given framework+scopes combo."""
    cache_key = (framework_id, tuple(scopes or []))
    if cache_key not in _processor_cache:
        print(f"[App] Creating processor for {framework_id} + scopes={scopes or []}")
        _processor_cache[cache_key] = MedicalDocumentProcessor(
            user_id="WEBAPP",
            framework_id=framework_id,
            scopes=scopes
        )
    return _processor_cache[cache_key]


# Initialize default processor on startup
print("=" * 60)
print("Medical Document Processor - Starting")
print("=" * 60)
print("Using LOCAL AI models (compliant, no external APIs)")
print()

try:
    DEFAULT_PROCESSOR = _get_processor("nhs_uk")
    print("Processor initialized successfully")
except Exception as e:
    print(f"ERROR initializing processor: {e}")
    import traceback
    traceback.print_exc()
    DEFAULT_PROCESSOR = None


@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')


@app.route('/frameworks', methods=['GET'])
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
            import json
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
def process_document():
    """Process uploaded medical document"""

    # Resolve framework and scopes from form data
    framework_id = request.form.get('framework', 'nhs_uk')
    scopes_str = request.form.get('scopes', '')
    scopes = [s.strip() for s in scopes_str.split(',') if s.strip()] if scopes_str else []

    try:
        processor = _get_processor(framework_id, scopes)
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

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        print()
        print("=" * 60)
        print(f"Processing: {filename} (framework={framework_id}, scopes={scopes})")
        print("=" * 60)

        result = processor.process_document(filepath)

        try:
            os.remove(filepath)
        except Exception:
            pass

        if result['status'] == 'success':
            print("=" * 60)
            print("Processing completed successfully")
            print("=" * 60)
            print()

        return jsonify(result)

    except Exception as e:
        print(f"Error processing document: {e}")
        import traceback
        traceback.print_exc()

        return jsonify({
            'status': 'error',
            'error': 'An internal error has occurred. Please try again later.'
        }), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'processor': 'initialized' if DEFAULT_PROCESSOR else 'not initialized',
        'using_local_models': True,
        'frameworks': list_frameworks(),
        'scopes': list_scopes()
    })


if __name__ == '__main__':
    if DEFAULT_PROCESSOR is None:
        print()
        print("=" * 60)
        print("WARNING: Processor failed to initialize")
        print("=" * 60)
        print("The application will start but may not work correctly.")
        print("Please check the error messages above.")
        print("=" * 60)
        print()

    print()
    print("=" * 60)
    print("Starting Flask server...")
    print("=" * 60)
    print("Open your browser to: http://localhost:5000")
    print("=" * 60)
    print()

    app.run(host='0.0.0.0', port=5000)
