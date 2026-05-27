"""
Tests de humo para la API HCD IA.
Verifican que los endpoints principales respondan correctamente.
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_reporte_total_responde():
    response = client.get("/hcd/reporte-total")
    assert response.status_code == 200
    data = response.json()
    assert "total_intervenciones" in data.get("resumen_ejecutivo", {})


def test_reportes_lista():
    response = client.get("/hcd/reportes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
