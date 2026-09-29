# Procedencia de cambios

La sesión comenzó en `hardening-final`, HEAD `4508f53`, con modificaciones locales previas de la autora. Se conservaron antes del trabajo en una copia privada ignorada por Git; no se publica esa copia porque contiene el diccionario institucional anterior.

| Archivo | Cambio preexistente observado | Trabajo de cierre |
|---|---|---|
| api/main.py | 56 líneas agregadas, 35 retiradas | Límites/privacidad, rutas/configuración, errores, diccionario externo, RAG/LLM |
| api/tests/test_api.py | 41 líneas agregadas | Archivo previo conservado; tests nuevos en archivos separados |
| frontend/app.py | 310 líneas agregadas, 11 retiradas | Configuración API, manejo de caída/vacíos y eliminación de mapas identificatorios |
| pipeline/censo/modulo_censo_mensual.py | 74 líneas agregadas | Se conserva el trabajo previo; se retira el detalle identificable de un mensaje de diagnóstico |

El informe `docs/auditoria_tecnica_integral_2026-07-07.md` y el archivo `12.1.0` ya estaban sin versionar. Se preservan localmente y no se incorporan a esta entrega. Las reglas clínicas y fórmulas previas no se atribuyen al trabajo de hardening.

El diccionario institucional se externalizó con autorización expresa. Se compararon valores exactos y el comportamiento de todas sus entradas sin imprimir nombres. Las reglas de conteo, clasificación e interconsultas seleccionadas se compararon por AST. No se reescribe el historial: la eliminación de nombres del árbol actual no los elimina de commits anteriores.
