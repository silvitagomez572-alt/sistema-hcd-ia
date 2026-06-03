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


# ── Tests de pseudonimización ─────────────────────────────────────────────────

def test_pseudonimizacion_nombre_etiquetado_no_greedy():
    """El patrón 'nombre' NO debe capturar texto más allá del primer label PII."""
    from pipeline.pseudonimizacion.modulo_pseudonimizacion import _extraer_matches, crear_registro, pseudonimizar_texto_clinico

    texto = "Paciente: Juan Pérez DNI: 30111222. Evolución: Juan Pérez refiere ansiedad."
    matches = _extraer_matches(texto)

    nombres = [(tipo, valor) for ms, me, vs, ve, tipo, valor in matches if tipo == "nombre"]
    assert len(nombres) == 1, f"Se esperaba 1 match de nombre, se encontraron {len(nombres)}: {nombres}"
    assert nombres[0][1] == "Juan Pérez", f"Captura incorrecta: {nombres[0][1]!r}"

    dnis = [(tipo, valor) for ms, me, vs, ve, tipo, valor in matches if tipo in ("dni", "dni_standalone")]
    assert any(v == "30111222" for _, v in dnis), f"DNI no detectado: {dnis}"


def test_pseudonimizacion_nombre_para_antes_de_punto():
    """El patrón 'nombre' debe detenerse ante un punto."""
    from pipeline.pseudonimizacion.modulo_pseudonimizacion import _extraer_matches

    texto = "Paciente: Maria Lopez. Servicio: Salud Mental."
    matches = _extraer_matches(texto)
    nombres = [valor for ms, me, vs, ve, tipo, valor in matches if tipo == "nombre"]
    assert len(nombres) == 1
    assert "Servicio" not in nombres[0], f"Captura demasiado: {nombres[0]!r}"


def test_pseudonimizacion_nombre_para_antes_de_evolucion():
    """El patrón 'nombre' debe detenerse ante la keyword 'Evolución'."""
    from pipeline.pseudonimizacion.modulo_pseudonimizacion import _extraer_matches

    texto = "Nombre: GARCIA PABLO Evolución: estable y colaborador"
    matches = _extraer_matches(texto)
    nombres = [valor for ms, me, vs, ve, tipo, valor in matches if tipo == "nombre"]
    assert len(nombres) == 1
    assert "Evolución" not in nombres[0] and "estable" not in nombres[0], f"Captura demasiado: {nombres[0]!r}"


def test_pseudonimizacion_nombre_solo_no_afecta():
    """Un nombre corto sin texto posterior sigue funcionando."""
    from pipeline.pseudonimizacion.modulo_pseudonimizacion import _extraer_matches

    texto = "Paciente: Ana Torres\nFecha: 01/01/2024"
    matches = _extraer_matches(texto)
    nombres = [valor for ms, me, vs, ve, tipo, valor in matches if tipo == "nombre"]
    assert len(nombres) == 1
    assert nombres[0] == "Ana Torres"
