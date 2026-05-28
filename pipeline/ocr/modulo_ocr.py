"""
Módulo OCR — extrae texto de PDFs escaneados e imágenes (JPG/PNG)
usando pytesseract + pdf2image. Idioma por defecto: español (spa).
"""

import io
import pathlib

try:
    import pytesseract
    _PYTESSERACT_OK = True
except ImportError:
    _PYTESSERACT_OK = False

try:
    from pdf2image import convert_from_bytes
    _PDF2IMAGE_OK = True
except ImportError:
    _PDF2IMAGE_OK = False

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


LANG_DEFAULT = "spa"
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
EXTENSIONES_PDF = {".pdf"}

# OEM 3 = LSTM engine; PSM 6 = bloque uniforme de texto (adecuado para documentos clínicos)
_TESSERACT_CONFIG = r"--oem 3 --psm 6"


def _verificar_dependencias() -> None:
    faltantes = []
    if not _PYTESSERACT_OK:
        faltantes.append("pytesseract")
    if not _PDF2IMAGE_OK:
        faltantes.append("pdf2image")
    if not _PIL_OK:
        faltantes.append("Pillow")
    if faltantes:
        raise ImportError(
            f"Dependencias OCR faltantes: {', '.join(faltantes)}. "
            "Instalá con: pip install pytesseract pdf2image Pillow"
        )


def extraer_texto_imagen(imagen, lang: str = LANG_DEFAULT) -> str:
    """Extrae texto de una imagen PIL con Tesseract."""
    return pytesseract.image_to_string(imagen, lang=lang, config=_TESSERACT_CONFIG)


def procesar_pdf(contenido: bytes, lang: str = LANG_DEFAULT, dpi: int = 300) -> list[dict]:
    """
    Convierte cada página del PDF a imagen (dpi=300) y aplica OCR.
    Devuelve lista de {'pagina': int, 'texto': str}.
    """
    _verificar_dependencias()
    try:
        imagenes = convert_from_bytes(contenido, dpi=dpi)
    except Exception as e:
        raise RuntimeError(f"No se pudo convertir el PDF a imágenes: {e}") from e

    resultados = []
    for i, img in enumerate(imagenes, start=1):
        texto = extraer_texto_imagen(img, lang=lang).strip()
        resultados.append({"pagina": i, "texto": texto})
    return resultados


def procesar_imagen(contenido: bytes, lang: str = LANG_DEFAULT) -> list[dict]:
    """
    Extrae texto de una imagen (JPG/PNG/etc.).
    Devuelve lista con un único elemento {'pagina': 1, 'texto': str}.
    """
    _verificar_dependencias()
    try:
        imagen = Image.open(io.BytesIO(contenido))
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir la imagen: {e}") from e

    texto = extraer_texto_imagen(imagen, lang=lang).strip()
    return [{"pagina": 1, "texto": texto}]


def procesar_archivo(contenido: bytes, nombre: str, lang: str = LANG_DEFAULT) -> list[dict]:
    """
    Dispatcher: detecta el tipo por extensión y delega a procesar_pdf o procesar_imagen.
    Devuelve lista de {'pagina': int, 'texto': str}.
    """
    sufijo = pathlib.Path(nombre).suffix.lower()
    if sufijo in EXTENSIONES_PDF:
        return procesar_pdf(contenido, lang=lang)
    if sufijo in EXTENSIONES_IMAGEN:
        return procesar_imagen(contenido, lang=lang)
    raise ValueError(
        f"Formato no soportado para OCR: '{sufijo}'. Usá PDF, JPG o PNG."
    )


def texto_completo(paginas: list[dict]) -> str:
    """Une el texto de todas las páginas en un string continuo."""
    if len(paginas) == 1:
        return paginas[0]["texto"]
    partes = [f"--- Página {p['pagina']} ---\n{p['texto']}" for p in paginas]
    return "\n\n".join(partes)
