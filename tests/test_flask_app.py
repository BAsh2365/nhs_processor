"""
Tests for frontend/app.py — Flask endpoints and multi-framework routing.
Tests the HTTP interface. Requires flask and ML dependencies for full test.
"""

import os
import sys
import json
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Check if flask and ML deps are available
try:
    import flask
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

try:
    import spacy
    import torch
    import transformers
    HAS_ML_DEPS = True
except ImportError:
    HAS_ML_DEPS = False

pytestmark = pytest.mark.skipif(
    not (HAS_FLASK and HAS_ML_DEPS),
    reason="Flask and/or ML dependencies not installed"
)


@pytest.fixture(scope="module")
def client():
    from frontend.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Basic endpoints
# ---------------------------------------------------------------------------

class TestBasicEndpoints:
    def test_index_returns_200(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_index_contains_framework_selector(self, client):
        html = resp = client.get('/').data.decode()
        assert 'framework-select' in html
        assert 'scopes-container' in html

    def test_index_contains_css_variables(self, client):
        html = client.get('/').data.decode()
        assert '--primary-color' in html

    def test_health_endpoint(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] == 'healthy'
        assert 'frameworks' in data
        assert 'scopes' in data


# ---------------------------------------------------------------------------
# 2. Framework endpoints
# ---------------------------------------------------------------------------

class TestFrameworkEndpoints:
    def test_frameworks_endpoint(self, client):
        resp = client.get('/frameworks')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        fw_ids = [f['id'] for f in data['frameworks']]
        assert 'nhs_uk' in fw_ids
        assert 'us_aha' in fw_ids

    def test_scopes_listed(self, client):
        resp = client.get('/frameworks')
        data = json.loads(resp.data)
        scope_ids = [s['id'] for s in data['scopes']]
        assert 'congenital_achd' in scope_ids

    def test_framework_config_nhs(self, client):
        resp = client.get('/framework-config/nhs_uk')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['branding']['logo_text'] == 'NHS'
        assert data['urgency_levels'] == ['EMERGENCY', 'URGENT', 'ROUTINE']

    def test_framework_config_us(self, client):
        resp = client.get('/framework-config/us_aha')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['branding']['logo_text'] == 'AHA'
        assert data['urgency_levels'] == ['EMERGENT', 'URGENT', 'ELECTIVE']

    def test_framework_config_nonexistent_returns_404(self, client):
        resp = client.get('/framework-config/nonexistent')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Process endpoint validation
# ---------------------------------------------------------------------------

class TestProcessEndpoint:
    def test_process_no_file_returns_400(self, client):
        resp = client.post('/process')
        assert resp.status_code == 400

    def test_process_wrong_extension_returns_400(self, client):
        from io import BytesIO
        resp = client.post('/process', data={
            'file': (BytesIO(b'test content'), 'test.docx')
        }, content_type='multipart/form-data')
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 4. Frontend HTML structure (read-only, no Flask needed)
# ---------------------------------------------------------------------------

class TestFrontendHTML:
    """These tests read the HTML template directly — no Flask required."""

    @pytest.fixture
    def html(self):
        path = os.path.join(ROOT, "frontend", "templates", "index.html")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_has_css_variables(self, html):
        assert '--primary-color' in html
        assert '--secondary-color' in html
        assert '--success-color' in html

    def test_has_framework_selector(self, html):
        assert '<select id="framework-select">' in html

    def test_has_scopes_container(self, html):
        assert 'id="scopes-container"' in html

    def test_has_logo_text_element(self, html):
        assert 'id="logo-text"' in html

    def test_has_subtitle_element(self, html):
        assert 'id="subtitle-text"' in html

    def test_has_framework_badge(self, html):
        assert 'result-framework-badge' in html

    def test_has_emergent_class(self, html):
        assert 'urgency-emergent' in html

    def test_has_elective_class(self, html):
        assert 'urgency-elective' in html

    def test_js_loads_frameworks(self, html):
        assert 'loadFrameworkOptions' in html
        assert "'/frameworks'" in html

    def test_js_updates_branding(self, html):
        assert 'updateBranding' in html

    def test_js_sends_framework_in_form(self, html):
        assert "formData.append('framework'" in html
        assert "formData.append('scopes'" in html
