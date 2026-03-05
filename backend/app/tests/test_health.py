from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_request_id_is_attached_to_response():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.headers.get('x-request-id')


def test_metrics_exposes_prometheus_text():
    client.get('/health')
    response = client.get('/metrics')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/plain')
    body = response.text
    assert 'orion_http_requests_total' in body
    assert 'orion_http_requests_by_status_total' in body
