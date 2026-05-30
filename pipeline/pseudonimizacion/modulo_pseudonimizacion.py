"""
Utilities for deterministic pseudonymization and public-output redaction.

The functions in this module are intentionally conservative: they preserve
counts, dates and clinical categories, while removing direct identifiers from
strings and replacing stable identifiers with salted hashes.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

try:
    import pandas as pd
except ImportError:  # pragma: no cover - pandas is present in the app env
    pd = None


PSEUDONYM_SALT = os.getenv("PSEUDONYM_SALT", "sistema-hcd-ia-local-salt")

SENSITIVE_KEYS = {
    "documento",
    "dni",
    "nro_documento",
    "numero_documento",
    "nombre",
    "apellido",
    "nombre_paciente",
    "archivo",
    "filename",
    "nombre_archivo",
    "paciente_id",
    "texto_extraido",
    "profesional",
}


def pseudonymize_identifier(identifier: Any, prefix: str = "PAC") -> str:
    """Return a deterministic pseudonym for a non-public identifier."""
    value = re.sub(r"\s+", " ", str(identifier or "")).strip().upper()
    if not value:
        value = "SIN_IDENTIFICADOR"
    digest = hashlib.sha256(f"{PSEUDONYM_SALT}|{value}".encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:8].upper()}"


def generar_paciente_id(identificador: Any, prefijo: str = "PAC") -> str:
    """Genera un ID de paciente estable sin exponer el identificador real."""
    return pseudonymize_identifier(identificador, prefix=prefijo)


def _replace_labeled_identifier(match: re.Match) -> str:
    label = match.group(1)
    return f"{label}: [IDENTIFICADOR_ELIMINADO]"


def redact_text(text: Any) -> str:
    """Redact likely patient identifiers from a free-text string."""
    value = "" if text is None else str(text)
    if not value:
        return value

    # Labelled patient identity fields.
    value = re.sub(
        r"\b(Paciente|Nombre y apellido|Nombre|Apellido)\s*[:=]\s*[^|\n\r;]+",
        _replace_labeled_identifier,
        value,
        flags=re.IGNORECASE,
    )

    # Labelled professional names and classifier rules can be present in
    # historical reports saved before this privacy layer existed.
    value = re.sub(
        r"\bdiccionario_profesional\s*:\s*[^|\n\r;}\"]+",
        "diccionario_profesional:[PROFESIONAL_ELIMINADO]",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\bProfesional\s*:\s*[^|\n\r;]+",
        "Profesional: [PROFESIONAL_ELIMINADO]",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b[A-ZÁÉÍÓÚÑÜ]{2,}(?:\s+[A-ZÁÉÍÓÚÑÜ]{2,}){0,3},\s*[A-ZÁÉÍÓÚÑÜ]{2,}(?:\s+[A-ZÁÉÍÓÚÑÜ]{2,}){0,3}\s*\((?:Psic[oó]logo|Enfermer[oa]|M[eé]dic[oa]|Trabajador[oa]\s+Social|Psiquiatra)[^)]+\)",
        "[PROFESIONAL_ELIMINADO]",
        value,
        flags=re.IGNORECASE,
    )

    # Labelled document fields.
    value = re.sub(
        r"\b(DNI|Documento|Doc\.?|Nro\.?\s*Documento|Número\s*Documento)\s*[:=]?\s*[A-Z]*\s*\d{6,9}\b",
        _replace_labeled_identifier,
        value,
        flags=re.IGNORECASE,
    )

    # Common VADIGU codigoHC pattern can embed DNI.
    value = re.sub(r"\b\d{1,5}-\d{6,9}-\d{1,3}\b", "[CODIGO_HC_ELIMINADO]", value)

    # Administrative identifiers in historical notes/reports.
    value = re.sub(
        r"\b(Expediente|Nro\.?\s*Expediente|Número\s*Expediente)\s*(?:N[°ºro.]*|[:=])?\s*[A-Z0-9./_-]+",
        r"\1 [IDENTIFICADOR_ELIMINADO]",
        value,
        flags=re.IGNORECASE,
    )

    # Standalone DNI-like numbers.
    value = re.sub(r"\b\d{7,8}\b", "[DNI_ELIMINADO]", value)
    return value


def redactar_dni(texto: Any) -> str:
    """Elimina DNI/documentos de un texto conservando el resto del contenido."""
    value = "" if texto is None else str(texto)
    value = re.sub(
        r"\b(DNI|Documento|Doc\.?|Nro\.?\s*Documento|Número\s*Documento)\s*[:=]?\s*[A-Z]*\s*\d{6,9}\b",
        _replace_labeled_identifier,
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b\d{1,5}-\d{6,9}-\d{1,3}\b", "[CODIGO_HC_ELIMINADO]", value)
    return re.sub(r"\b\d{7,8}\b", "[DNI_ELIMINADO]", value)


def redactar_nombre(texto: Any) -> str:
    """Elimina nombres declarados en campos etiquetados de paciente/persona."""
    value = "" if texto is None else str(texto)
    return re.sub(
        r"\b(Paciente|Nombre y apellido|Nombre|Apellido)\s*[:=]\s*[^|\n\r;]+",
        _replace_labeled_identifier,
        value,
        flags=re.IGNORECASE,
    )


def pseudonimizar_texto(texto: Any) -> str:
    """Aplica redacción de nombres, DNI y códigos identificatorios al texto."""
    return redact_text(texto)


def _sanitize_key_value(key: str, value: Any) -> Any:
    key_norm = key.lower()
    if key_norm in SENSITIVE_KEYS:
        if key_norm == "texto_extraido":
            return "[TEXTO_EXTRAIDO_NO_EXPORTADO]"
        if key_norm in {"archivo", "filename", "nombre_archivo"}:
            return pseudonymize_identifier(value, prefix="DOC")
        if key_norm == "paciente_id":
            current = str(value or "").strip()
            if re.fullmatch(r"PAC-[A-F0-9]{8}", current):
                return current
            return pseudonymize_identifier(current, prefix="PAC")
        if key_norm in {"documento", "dni", "nro_documento", "numero_documento"}:
            return "[DNI_ELIMINADO]"
        if key_norm == "profesional":
            return "[PROFESIONAL_ELIMINADO]"
        return "[PACIENTE_PSEUDONIMIZADO]"
    if key_norm == "paciente" and not isinstance(value, (dict, list, tuple)):
        return "[PACIENTE_PSEUDONIMIZADO]"
    if isinstance(value, str):
        return redact_text(value)
    return sanitize_public_payload(value)


def sanitize_public_payload(payload: Any) -> Any:
    """Recursively redact sensitive fields and strings in public JSON payloads."""
    if isinstance(payload, dict):
        return {key: _sanitize_key_value(str(key), value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [sanitize_public_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(sanitize_public_payload(item) for item in payload)
    if isinstance(payload, str):
        return redact_text(payload)
    return payload


def redact_dataframe_identifiers(df: Any, id_prefix: str = "PAC"):
    """
    Return a copy of a DataFrame with direct identifiers removed from display/export.

    Documento is replaced by a deterministic pseudonym. Paciente is dropped to avoid
    accidental display or CSV export of real names.
    """
    if pd is None or df is None:
        return df
    result = df.copy()
    if "Documento" in result.columns:
        result["paciente_id"] = result["Documento"].map(
            lambda value: pseudonymize_identifier(value, prefix=id_prefix)
        )
        result = result.drop(columns=["Documento"])
    elif "codigoHC" in result.columns:
        result["paciente_id"] = result["codigoHC"].map(
            lambda value: pseudonymize_identifier(value, prefix=id_prefix)
        )
    if "Paciente" in result.columns:
        result = result.drop(columns=["Paciente"])
    return result
