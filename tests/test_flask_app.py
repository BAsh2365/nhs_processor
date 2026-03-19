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

    def test_index_returns_json_api_info(self, client):
        data = json.loads(client.get('/').data)
        assert data['name'] == 'NHS Medical Document Processor API'
        assert 'endpoints' in data
        assert '/health' in data['endpoints']
        assert '/process' in data['endpoints']

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

# ---------------------------------------------------------------------------
# 2b. Guidelines endpoint
# ---------------------------------------------------------------------------

class TestGuidelinesEndpoint:
    def test_guidelines_nhs_returns_200(self, client):
        resp = client.get('/guidelines/nhs_uk')
        assert resp.status_code == 200

    def test_guidelines_nhs_has_guidelines_list(self, client):
        resp = client.get('/guidelines/nhs_uk')
        data = json.loads(resp.data)
        assert 'guidelines' in data
        assert isinstance(data['guidelines'], list)
        assert len(data['guidelines']) > 0
        assert data['framework'] == 'nhs_uk'
        # Verify each guideline has required fields
        for g in data['guidelines']:
            assert 'id' in g
            assert 'title' in g
            assert 'organization' in g
            assert 'key_recommendations' in g

    def test_guidelines_nhs_has_equations_list(self, client):
        resp = client.get('/guidelines/nhs_uk')
        data = json.loads(resp.data)
        assert 'equations' in data
        assert isinstance(data['equations'], list)
        assert len(data['equations']) > 0
        # Verify each equation has required fields
        for eq in data['equations']:
            assert 'id' in eq
            assert 'name' in eq
            assert 'formula' in eq
            assert 'use_case' in eq

    def test_guidelines_us_returns_200(self, client):
        resp = client.get('/guidelines/us_aha')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['framework'] == 'us_aha'
        assert len(data['guidelines']) > 0
        assert len(data['equations']) > 0

    def test_guidelines_unknown_returns_404(self, client):
        resp = client.get('/guidelines/nonexistent')
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

