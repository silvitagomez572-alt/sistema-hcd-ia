"""Local configuration and privacy-safe HTTP boundary; no clinical rules."""
import base64
import hmac
import json
import logging
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)
MAX_BYTES = int(os.getenv('HCD_MAX_UPLOAD_BYTES', str(10 * 1024 * 1024)))
DB_PATH = Path(os.getenv('HCD_DB_PATH', str(ROOT / 'hcs.db'))).expanduser().resolve()
MODEL_PATH = Path(os.getenv('HCD_MODEL_PATH', str(ROOT / 'modelo_area_intervenciones.pkl'))).expanduser().resolve()
PROFESSIONALS_PATH = Path(os.getenv('HCD_PROFESSIONALS_PATH', str(ROOT / '.local/profesionales.json'))).expanduser().resolve()
UPLOAD_DIR = Path(os.getenv('HCD_UPLOAD_DIR', str(ROOT / 'uploads/censos'))).expanduser().resolve()
logger = logging.getLogger('hcd.audit')
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


def load_professionals():
    try:
        data = json.loads(PROFESSIONALS_PATH.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not data or not all(
            isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) and x for x in v)
            for k, v in data.items()
        ):
            raise ValueError()
        return data
    except (OSError, ValueError):
        raise HTTPException(503, 'Diccionario profesional no configurado o inválido; procesamiento deshabilitado.') from None


async def read_upload(archivo):
    data = await archivo.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Archivo demasiado grande.')
    if not data:
        raise HTTPException(400, 'Archivo vacío.')
    return data


def validate_filename(name):
    if not name or name in {'.', '..'} or '/' in name or '\\' in name or '\x00' in name or ':' in name:
        raise HTTPException(400, 'Nombre de archivo inválido.')
    if len(name) > 200:
        raise HTTPException(400, 'Nombre de archivo demasiado largo.')
    return name


class SafetyBoundary:
    """Bound request size before multipart parsing; never log URLs or payloads."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        headers = dict(scope.get('headers', []))
        password = os.getenv('HCD_API_PASSWORD', '')
        public = scope.get('path') == '/health'
        authorized = False
        if password:
            try:
                kind, encoded = headers.get(b'authorization', b'').decode().split(' ', 1)
                user, supplied = base64.b64decode(encoded, validate=True).decode().split(':', 1)
                authorized = kind.lower() == 'basic' and hmac.compare_digest(user, os.getenv('HCD_API_USER', 'operador')) and hmac.compare_digest(supplied, password)
            except (ValueError, UnicodeError):
                pass
        else:
            authorized = (scope.get('client') or ('',))[0] in {'127.0.0.1', '::1', 'testclient'}
        if not public and not authorized:
            return await JSONResponse({'detail': 'Autenticación requerida.'}, 401, headers={'WWW-Authenticate': 'Basic realm="HCD local"'})(scope, receive, send)
        # Read at most the configured limit, including multipart overhead.
        messages = []
        size = 0
        while True:
            msg = await receive()
            if msg['type'] == 'http.disconnect':
                return
            size += len(msg.get('body', b''))
            if size > MAX_BYTES + 65536:
                return await JSONResponse({'detail': 'Solicitud demasiado grande.'}, 413)(scope, receive, send)
            messages.append(msg)
            if not msg.get('more_body', False):
                break
        iterator = iter(messages)
        async def replay():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()
        status = 500
        started = False
        async def safe_send(msg):
            nonlocal status, started
            if msg['type'] == 'http.response.start':
                started = True
                status = msg['status']
                msg['headers'] = list(msg.get('headers', [])) + [(b'x-request-id', request_id.encode()), (b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]
            await send(msg)
        try:
            await self.app(scope, replay, safe_send)
        except Exception:
            if not started:
                await JSONResponse({'detail': 'Error interno; consulte el identificador de solicitud.'}, 500)(scope, replay, safe_send)
        finally:
            route = scope.get('route')
            logger.info(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(), 'level': 'ERROR' if status >= 500 else 'INFO', 'module': 'api', 'operation': getattr(route, 'name', 'unmatched'), 'request_id': request_id, 'status': status}))


def configure_errors(app):
    import sqlite3
    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return JSONResponse({'detail': 'Base de datos no disponible.'}, 503)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic errors can contain the original sensitive input.
        return JSONResponse({'detail': 'Entrada inválida.'}, 422)
