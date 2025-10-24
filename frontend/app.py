# frontend/app.py - UPDATED with fixed imports

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import sys

# Fix path to find backend module
# Get the parent directory (project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Now import backend modules
from backend.processor import MedicalDocumentProcessor

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Setup upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize processor (NO API KEY NEEDED - uses local models)
print("=" * 60)
print("NHS Medical Document Processor - Starting")
print("=" * 60)
print("Using LOCAL AI models (NHS compliant, no external APIs)")
print()

try:
    PROCESSOR = MedicalDocumentProcessor(user_id="WEBAPP")
    print("✅ Processor initialized successfully")
except Exception as e:
    print(f"❌ ERROR initializing processor: {e}")
    import traceback
    traceback.print_exc()
    PROCESSOR = None

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_document():
    """Process uploaded medical document"""
    
    if PROCESSOR is None:
        return jsonify({
            'status': 'error',
            'error': 'Processor not initialized. Check server logs.'
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
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        print()
        print("=" * 60)
        print(f"Processing: {filename}")
        print("=" * 60)
        
        # Process document
        result = PROCESSOR.process_document(filepath)
        
        # Clean up
        try:
            os.remove(filepath)
        except:
            pass
        
        if result['status'] == 'success':
            print("=" * 60)
            print("✅ Processing completed successfully")
            print("=" * 60)
            print()
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error processing document: {e}")
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
        'processor': 'initialized' if PROCESSOR else 'not initialized',
        'using_local_models': True
    })

if __name__ == '__main__':
    if PROCESSOR is None:
        print()
        print("=" * 60)
        print("⚠️  WARNING: Processor failed to initialize")
        print("=" * 60)
        print("The application will start but may not work correctly.")
        print("Please check the error messages above.")
        print("=" * 60)
        print()
    
    print()
    print("=" * 60)
    print("🚀 Starting Flask server...")
    print("=" * 60)
    print("Open your browser to: http://localhost:5000")
    print("=" * 60)
    print()
    
    app.run(host='0.0.0.0', port=5000)