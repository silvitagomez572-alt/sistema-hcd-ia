"""Local-only Ollama transport with bounded, non-identifying errors."""
import ipaddress
import os
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from pipeline.pseudonimizacion import crear_registro, pseudonimizar_texto_clinico, pseudonimizar_texto


def local_url():
    url = os.getenv('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
    parsed = urlsplit(url)
    allowed = parsed.hostname in {'localhost', 'ollama'}
    if not allowed:
        try:
            address = ipaddress.ip_address(parsed.hostname or '')
            allowed = address.is_loopback or address.is_private
        except ValueError:
            pass
    if not allowed or parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise HTTPException(503, 'OLLAMA_URL debe apuntar a un servidor local.')
    return url


async def generate(prompt):
    url = local_url()
    model = os.getenv('OLLAMA_MODEL', '').strip()
    if not model:
        raise HTTPException(503, 'Configure OLLAMA_MODEL con un modelo local ya instalado.')
    cleaned = pseudonimizar_texto_clinico(prompt, crear_registro())['texto_pseudonimizado']
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=3), trust_env=False) as client:
            response = await client.post(f'{url}/api/generate', json={'model': model, 'prompt': cleaned, 'stream': False})
            response.raise_for_status()
            data = response.json()
            result = data.get('response')
            if not isinstance(result, str) or not result.strip():
                raise ValueError()
    except httpx.TimeoutException:
        raise HTTPException(504, 'Ollama excedió el tiempo de espera.') from None
    except httpx.RequestError:
        raise HTTPException(503, 'Ollama no está disponible.') from None
    except (httpx.HTTPStatusError, ValueError, AttributeError):
        raise HTTPException(502, 'Ollama devolvió una respuesta inválida; verifique el modelo instalado.') from None
    return pseudonimizar_texto(result)
