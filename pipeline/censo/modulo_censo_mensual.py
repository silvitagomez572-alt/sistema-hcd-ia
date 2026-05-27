"""
Módulo censo mensual — lee archivos de censo diario de VADIGU (CSV, Excel, HTML, PDF),
filtra camas ocupadas en Salud Mental y consolida un DataFrame único por codigoHC.
"""

import io
import pathlib
import re
from typing import Union

import pandas as pd

try:
    import pypdf
    _PYPDF_OK = True
except ImportError:
    _PYPDF_OK = False

try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False

try:
    from bs4 import BeautifulSoup
    _BS4_OK = True
except ImportError:
    _BS4_OK = False

COLUMNAS_ESPERADAS = ["Cama", "Estado", "Area", "Paciente", "Edad", "Documento", "codigoHC", "Ingreso", "Estada"]

ESTADO_OCUPADA = "ocupada"
AREA_SALUD_MENTAL = "salud mental"


def _normalizar(valor: str) -> str:
    return str(valor).strip().lower()


def _leer_csv(ruta: pathlib.Path) -> pd.DataFrame:
    for sep in (",", ";", "\t"):
        try:
            df = pd.read_csv(ruta, sep=sep, dtype=str, encoding="utf-8")
            if len(df.columns) >= 5:
                return df
        except Exception:
            continue
    return pd.read_csv(ruta, dtype=str, encoding="latin-1")


def _leer_excel(ruta: pathlib.Path) -> pd.DataFrame:
    sufijo = ruta.suffix.lower()
    if sufijo == ".xls":
        # VADIGU exporta .xls como HTML disfrazado
        if not _BS4_OK:
            raise ImportError("beautifulsoup4 requerido para leer .xls de VADIGU")
        contenido = ruta.read_bytes()
        soup = BeautifulSoup(contenido, "html.parser")
        tabla = soup.find("table")
        if tabla:
            return pd.read_html(str(tabla), dtype=str)[0]
        raise ValueError(f"No se encontró tabla HTML en {ruta.name}")
    return pd.read_excel(ruta, dtype=str)


def _leer_html(ruta: pathlib.Path) -> pd.DataFrame:
    if not _BS4_OK:
        raise ImportError("beautifulsoup4 requerido para leer HTML")
    contenido = ruta.read_bytes()
    soup = BeautifulSoup(contenido, "html.parser")
    tabla = soup.find("table")
    if tabla:
        return pd.read_html(str(tabla), dtype=str)[0]
    tablas = pd.read_html(str(contenido, "utf-8", errors="replace"))
    if not tablas:
        raise ValueError(f"No se encontró tabla en {ruta.name}")
    return tablas[0]


def _texto_pdf_a_df(texto: str) -> pd.DataFrame:
    """
    Reconstruye un DataFrame a partir del texto extraído de un PDF de VADIGU.
    Detecta la línea de cabecera y parsea cada fila separando por dos o más espacios.
    Devuelve un DataFrame vacío (no lanza) si no hay filas válidas — permite que
    el caller decida si reintentar con pdfplumber.
    """
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    cabecera_idx = None
    for i, linea in enumerate(lineas):
        if re.search(r'\bCama\b', linea, re.IGNORECASE) and re.search(r'\bEstado\b', linea, re.IGNORECASE):
            cabecera_idx = i
            break

    if cabecera_idx is None:
        return pd.DataFrame()

    filas = []
    for linea in lineas[cabecera_idx + 1:]:
        partes = re.split(r'\s{2,}|\t', linea)
        if len(partes) >= len(COLUMNAS_ESPERADAS):
            filas.append(partes[:len(COLUMNAS_ESPERADAS)])

    if not filas:
        return pd.DataFrame()
    return pd.DataFrame(filas, columns=COLUMNAS_ESPERADAS)


def _limpiar_filas_pdf(df: pd.DataFrame) -> pd.DataFrame:
    """
    Corrige los artefactos de extracción que produce pdfplumber con el PDF de VADIGU,
    donde las columnas son demasiado estrechas y el texto desborda hacia celdas adyacentes.

    Correcciones aplicadas:
    - Paciente: el nombre largo desborda hacia Edad; se reconstruye tomando todos los
      caracteres alfabéticos antes del primer dígito del string concatenado.
    - Edad: los dígitos del nombre overflow quedan mezclados; se extraen solo los dígitos
      del campo Edad original y se concatenan para obtener la edad numérica.
    - Ingreso: la hora queda truncada y sangra en Estada; se extrae solo DD/MM/YYYY.
    - Estada: contiene fragmento de hora de Ingreso; se extrae el último entero (días).
    - Documento: texto mezclado con el DNI; se extrae preferentemente desde codigoHC
      (formato NNN-DNINUMBER-N) y como fallback desde el campo raw.
    """
    df = df.copy()

    # Paciente + Edad: reconstruir nombre y edad
    if "Paciente" in df.columns and "Edad" in df.columns:
        nombres, edades = [], []
        for _, fila in df.iterrows():
            pac_raw = str(fila.get("Paciente") or "").strip()
            edad_raw = str(fila.get("Edad") or "").strip()
            combinado = pac_raw + edad_raw
            # Nombre: parte alfabética (letras, espacios, comas, tildes, guiones)
            m = re.match(r'^([A-ZÁÉÍÓÚÑÜA-Záéíóúñüa-z,\s\.\-]+?)(?=\d)', combinado)
            nombre = m.group(1).strip().rstrip(",").strip() if m else combinado.strip()
            # Edad: concatenar todos los dígitos del campo Edad original
            edad = "".join(re.findall(r'\d', edad_raw)) or ""
            nombres.append(nombre)
            edades.append(edad)
        df["Paciente"] = nombres
        df["Edad"] = edades

    # Ingreso: extraer DD/MM/YYYY
    if "Ingreso" in df.columns:
        def _limpiar_ingreso(raw: str) -> str:
            m = re.search(r'(\d{1,2}/\d{2}/\d{4})', str(raw or ""))
            return m.group(1) if m else str(raw or "").strip()
        df["Ingreso"] = df["Ingreso"].map(_limpiar_ingreso)

    # Estada: extraer el último entero (días de internación)
    if "Estada" in df.columns:
        def _limpiar_estada(raw: str) -> str:
            nums = re.findall(r'\d+', str(raw or ""))
            return nums[-1] if nums else str(raw or "").strip()
        df["Estada"] = df["Estada"].map(_limpiar_estada)

    # Documento: extraer DNI preferentemente desde codigoHC
    if "Documento" in df.columns:
        def _limpiar_documento(doc_raw: str, codigo_hc: str) -> str:
            # codigoHC tiene formato NNN-DNINUMBER-N, es la fuente más confiable
            m_hc = re.search(r'-(\d{6,9})-', str(codigo_hc or ""))
            if m_hc:
                return f"DNI {m_hc.group(1)}"
            # Fallback: primer número de 7-8 dígitos en el campo raw
            m_doc = re.search(r'\b(\d{7,8})\b', str(doc_raw or ""))
            if m_doc:
                return f"DNI {m_doc.group(1)}"
            return str(doc_raw or "").strip()
        hc_col = df["codigoHC"] if "codigoHC" in df.columns else pd.Series([""] * len(df))
        df["Documento"] = [
            _limpiar_documento(d, h) for d, h in zip(df["Documento"], hc_col)
        ]

    return df


def _leer_pdf_pdfplumber(ruta: pathlib.Path) -> pd.DataFrame:
    """
    Parser para el censo VADIGU donde la tabla está dividida verticalmente en dos
    grupos de páginas:
      - Páginas "izquierda": Cama, Estado, Area, Paciente, Edad, Documento
      - Páginas "derecha":   codigoHC, Ingreso, Estada, ObraSocial

    Las páginas se identifican automáticamente por sus cabeceras y se unen por
    índice de fila (mismo orden de pacientes en ambos grupos).
    Aplica _limpiar_filas_pdf para corregir artefactos de columnas truncadas.
    """
    _FIRMAS_IZQ = {"cama", "estado", "area", "paciente"}
    _FIRMAS_DER = {"codigohc", "codigo hc", "ingreso", "estada"}

    def _extraer_pagina(pagina) -> tuple[list[str] | None, list[list[str]]]:
        for tabla in pagina.extract_tables():
            if not tabla:
                continue
            for idx, fila in enumerate(tabla):
                celdas = [str(c or "").strip() for c in fila]
                cab_lower = {c.lower() for c in celdas if c}
                if cab_lower & _FIRMAS_IZQ or cab_lower & _FIRMAS_DER:
                    filas_datos = [
                        [str(c or "").strip() for c in f]
                        for f in tabla[idx + 1:]
                        if any(c for c in f)
                    ]
                    return celdas, filas_datos
        return None, []

    filas_izq: list[list[str]] = []
    cols_izq: list[str] | None = None
    filas_der: list[list[str]] = []
    cols_der: list[str] | None = None

    with pdfplumber.open(str(ruta)) as pdf:
        for pagina in pdf.pages:
            cabeceras, filas = _extraer_pagina(pagina)
            if not cabeceras:
                continue
            cab_lower = {c.lower() for c in cabeceras if c}
            if cab_lower & _FIRMAS_IZQ:
                cols_izq = cols_izq or cabeceras
                filas_izq.extend(filas)
            elif cab_lower & _FIRMAS_DER:
                cols_der = cols_der or cabeceras
                filas_der.extend(filas)

    if cols_izq is None and cols_der is None:
        return pd.DataFrame()

    def _a_df(cols: list[str] | None, filas: list[list[str]]) -> pd.DataFrame:
        if not cols or not filas:
            return pd.DataFrame()
        n = len(cols)
        alineadas = [f[:n] + [""] * max(0, n - len(f)) for f in filas]
        return pd.DataFrame(alineadas, columns=cols)

    df_izq = _a_df(cols_izq, filas_izq)
    df_der = _a_df(cols_der, filas_der)

    if df_izq.empty and df_der.empty:
        return pd.DataFrame()
    if df_izq.empty:
        df = df_der
    elif df_der.empty:
        df = df_izq
    else:
        n_filas = min(len(df_izq), len(df_der))
        df = pd.concat(
            [df_izq.iloc[:n_filas].reset_index(drop=True),
             df_der.iloc[:n_filas].reset_index(drop=True)],
            axis=1,
        )

    _alias = {
        **{c.lower(): c for c in COLUMNAS_ESPERADAS},
        "codigohc": "codigoHC",
        "codigo hc": "codigoHC",
        "área": "Area",
        "obrasocial": "ObraSocial",
        "obra social": "ObraSocial",
    }
    df = df.rename(columns={c: _alias.get(c.lower(), c) for c in df.columns})
    return _limpiar_filas_pdf(df)


def _leer_pdf(ruta: pathlib.Path) -> pd.DataFrame:
    """
    Estrategia de dos pasos:
    1. pypdf — rápido; funciona bien cuando el PDF tiene texto extraíble con columnas separadas.
    2. pdfplumber — fallback; analiza la geometría de la tabla y recupera columnas aunque
       el texto esté compacto o mal espaciado.
    """
    if not _PYPDF_OK and not _PDFPLUMBER_OK:
        raise ImportError("Se necesita pypdf o pdfplumber para leer PDFs")

    # Paso 1: pypdf
    if _PYPDF_OK:
        try:
            reader = pypdf.PdfReader(str(ruta))
            texto = "".join(page.extract_text() or "" for page in reader.pages)
            df = _texto_pdf_a_df(texto)
            if not df.empty:
                return df
        except Exception:
            pass  # degradar a pdfplumber

    # Paso 2: pdfplumber
    if _PDFPLUMBER_OK:
        df = _leer_pdf_pdfplumber(ruta)
        if not df.empty:
            return df
        raise ValueError(f"pdfplumber no encontró tabla de censo en {ruta.name}")

    raise ValueError(f"pypdf no pudo extraer tabla de {ruta.name} y pdfplumber no está instalado")


def leer_archivo_censo(ruta: Union[str, pathlib.Path]) -> pd.DataFrame:
    """Lee un archivo de censo VADIGU y devuelve un DataFrame crudo con columnas normalizadas."""
    ruta = pathlib.Path(ruta)
    sufijo = ruta.suffix.lower()

    if sufijo == ".csv":
        df = _leer_csv(ruta)
    elif sufijo in (".xlsx", ".xls"):
        df = _leer_excel(ruta)
    elif sufijo in (".html", ".htm"):
        df = _leer_html(ruta)
    elif sufijo == ".pdf":
        df = _leer_pdf(ruta)
    else:
        raise ValueError(f"Formato no soportado: {sufijo}")

    # Normalizar nombres de columnas: strip + título
    df.columns = [str(c).strip() for c in df.columns]

    # Intentar mapear columnas si difieren (tolerancia a variantes de VADIGU)
    _alias = {
        "cama": "Cama", "estado": "Estado", "area": "Area", "área": "Area",
        "paciente": "Paciente", "edad": "Edad", "documento": "Documento",
        "codigohc": "codigoHC", "codigo hc": "codigoHC", "hc": "codigoHC",
        "ingreso": "Ingreso", "estada": "Estada",
    }
    df = df.rename(columns={c: _alias[c.lower()] for c in df.columns if c.lower() in _alias})
    df["_archivo"] = ruta.name
    return df


def filtrar_salud_mental(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra filas con Estado=Ocupada y Area=Salud Mental."""
    if "Estado" not in df.columns or "Area" not in df.columns:
        raise KeyError("El DataFrame no tiene columnas 'Estado' y/o 'Area'")
    mask = (
        df["Estado"].map(_normalizar) == ESTADO_OCUPADA
    ) & (
        df["Area"].map(_normalizar) == AREA_SALUD_MENTAL
    )
    return df[mask].copy()


def consolidar_mes(
    directorio: Union[str, pathlib.Path],
    patron: str = "*",
) -> pd.DataFrame:
    """
    Lee todos los archivos de censo del directorio, filtra Salud Mental/Ocupada
    y devuelve un DataFrame único deduplicado por codigoHC (último registro por fecha).

    Args:
        directorio: carpeta con los archivos del mes.
        patron: glob para filtrar archivos (default: todos).

    Returns:
        DataFrame consolidado con una fila por codigoHC.
    """
    directorio = pathlib.Path(directorio)
    extensiones = {".csv", ".xlsx", ".xls", ".html", ".htm", ".pdf"}
    archivos = sorted(
        f for f in directorio.glob(patron)
        if f.is_file() and f.suffix.lower() in extensiones
    )
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos de censo en {directorio}")

    fragmentos = []
    errores = []
    for arch in archivos:
        try:
            df = leer_archivo_censo(arch)
            df_sm = filtrar_salud_mental(df)
            if not df_sm.empty:
                fragmentos.append(df_sm)
        except Exception as exc:
            errores.append((arch.name, str(exc)))

    if errores:
        for nombre, msg in errores:
            print(f"[censo] ADVERTENCIA — {nombre}: {msg}")

    if not fragmentos:
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS)

    consolidado = pd.concat(fragmentos, ignore_index=True)

    if "codigoHC" not in consolidado.columns:
        return consolidado

    # Ordenar por Ingreso si existe para quedarse con el registro más reciente
    if "Ingreso" in consolidado.columns:
        consolidado["Ingreso"] = pd.to_datetime(
            consolidado["Ingreso"], dayfirst=True, errors="coerce"
        )
        consolidado = consolidado.sort_values("Ingreso", na_position="first")

    # Un registro por codigoHC (el último en el mes)
    consolidado = consolidado.drop_duplicates(subset=["codigoHC"], keep="last")
    consolidado = consolidado.reset_index(drop=True)
    return consolidado


def resumen_mensual(df: pd.DataFrame) -> dict:
    """Devuelve métricas básicas del DataFrame consolidado."""
    return {
        "total_pacientes": len(df),
        "camas_ocupadas": df["Cama"].nunique() if "Cama" in df.columns else None,
        "edad_promedio": (
            pd.to_numeric(df["Edad"], errors="coerce").mean().__round__(1)
            if "Edad" in df.columns else None
        ),
        "archivos_procesados": df["_archivo"].nunique() if "_archivo" in df.columns else None,
    }
