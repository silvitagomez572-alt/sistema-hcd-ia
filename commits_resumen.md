# Commits Resumen — Sistema HCD IA

> Documento de memoria técnica. Actualizado el 2026-05-25.
> Cubre los 31 commits del proyecto desde el origen hasta HEAD.

---

## Auditoría / Trazabilidad

---

## Commit

**ID:** (pendiente — próximo commit)
**Título:** feat: agrega auditoría clínica y trazabilidad del pipeline
**Fecha:** 2026-05-25

**Qué cambió:**
- Nuevo módulo "Auditoría" en la sidebar de Streamlit
- Expander "Información del pipeline": versión (1.0.0), commit activo (git rev-parse --short HEAD), fecha último procesamiento, modelo NLP y accuracy
- Métricas de auditoría en una fila: pacientes válidos, candidatos iniciales, descartados, intervenciones finales, ICs detectadas, stale excluidos
- Semáforo de calidad por HC: 🔴 stale/inconsistente, 🟡 con alertas, 🟢 OK
- Criterios de semáforo: `enfermería > 65%`, `psiquiatría = 0`, `internación > 365 días`, `HC corta (< 10 días) con tasa > 2.5 int/día`
- Alertas metodológicas automáticas: lista de warnings con paciente, indicador y valor

**Impacto:**
- Trazabilidad completa del pipeline visible desde la UI sin acceder a la BD ni al código
- Detección automática de HCs que requieren revisión manual antes de usar en análisis

**Problema que resolvió:**
- No había forma de ver en la UI si un HC procesado era stale, tenía inconsistencias o presentaba patrones atípicos

**No se modificó:**
- parser, clasificador híbrido, REGLAS_CONTEO, RAG, LLM, esquema de BD

**Estado:** Activo

---

## NLP / Clasificación Híbrida

---

## Commit

**ID:** cbf51ad
**Título:** feat: modelo NLP integrado, SQLite, procesamiento HCs reales VADIGU
**Fecha:** 2026-05-17

**Qué cambió:**
- Integra modelo TF-IDF + Logistic Regression (`modelo_area_intervenciones.pkl`, 407 KB)
- Endpoint `/hcd/procesar-modelo` — procesa XLS/HTML de VADIGU con clasificador NLP
- Inicia base de datos SQLite (`hcs.db`)
- Agrega `parsear_intervenciones()` para segmentar texto cronológico en bloques

**Impacto:**
- Primer pipeline completo: texto crudo → registros → área → SQLite

**Problema que resolvió:**
- El sistema solo tenía LLM (Gemma); sin capacidad de clasificar intervenciones sin conectividad a Ollama

**Estado:** Activo (base del pipeline NLP)

---

## Commit

**ID:** a0ac00d
**Título:** fix: clasificador híbrido + fix regex profesional línea 343
**Fecha:** 2026-05-19

**Qué cambió:**
- Implementa `clasificar_area_hibrido()` con 4 capas: diccionario profesional → reglas texto → modelo NLP → fallback
- Corrige regex para capturar nombre de profesional desde cabecera VADIGU
- Agrega `PROFESIONALES_SALUD_MENTAL` (diccionario de nombres por área)
- Agrega `REGLAS_AREA_TEXTO` (keywords por área, ~70 entradas)

**Impacto:**
- Reduce dependencia del modelo NLP para casos con firma de profesional
- La capa 1 (diccionario) es determinista y no falla; el modelo actúa solo como fallback

**Problema que resolvió:**
- Clasificaciones erróneas por texto ambiguo cuando el profesional era identificable por nombre

**Estado:** Activo

---

## Commit

**ID:** b2006a2
**Título:** fix: ampliar keywords de psiquiatría en clasificador híbrido (capa 2)
**Fecha:** 2026-05-19

**Qué cambió:**
- Agrega formas adjetivales con y sin tilde: `psiquiátrica/o/s`, `psiquiatrica/o/s`
- Agrega frases compuestas: evaluación, medicación, guardia, interconsulta, conducta psiquiátrica
- Agrega abreviaturas: `psiq.`, `psiq `, `psiq:`

**Impacto:**
- Frases clínicas como "evaluación psiquiátrica" antes caían en `otros` por diferencia Unicode entre í (sustantivo) y á (adjetivo)

**Problema que resolvió:**
- `psiquiatría` (acento en í) no matcheaba `psiquiátrica` (acento en á) — caracteres Unicode distintos

**Estado:** Activo

---

## Commit

**ID:** 9ad1714
**Título:** fix: clasificador de áreas — prioridad psiquiatría y keywords contextuales
**Fecha:** 2026-05-19

**Qué cambió:**
- Reordena `REGLAS_AREA_TEXTO` (dict iterado en orden): psiquiatria > psicologia > terapia_ocupacional > trabajo_social > acompanante_terapeutico > enfermeria > psicopedagogia
- Agrega antipsicóticos (haloperidol, risperidona, olanzapina, etc.) como keywords de psiquiatría
- Agrega estabilizadores (valproato, litio) y benzodiacepinas (clonazepam, lorazepam)

**Impacto:**
- psiquiatría: 1 → 4 (+3); psicología: +8; enfermería: -1; TO: -9; total sin cambio (1231)

**Problema que resolvió:**
- AT y TO tenían prioridad sobre psiquiatría; medicación psiquiátrica era clasificada como `otros`

**Estado:** Activo

---

## Commit

**ID:** a21be01
**Título:** feat: clasificador híbrido interconsultas con score y estado clínico
**Fecha:** 2026-05-17

**Qué cambió:**
- `REGLAS_IC`: cuatro estados con frases clave (pendiente, inicial, efectiva, seguimiento)
- `clasificar_estado_ic()`: retorna estado + score numérico
- `detectar_ics()`: itera registros buscando `SERVICIOS_EXTERNOS`; lógica de ventana local para bloques con múltiples servicios
- Combina ICs detectadas por texto con ICs detectadas por nombre de profesional externo

**Impacto:**
- Primera versión funcional de detección de interconsultas con estado clínico

**Problema que resolvió:**
- Detección binaria anterior (menciona servicio externo = interconsulta) producía falsos positivos

**Estado:** Activo

---

## Conteo / Deduplicación

---

## Commit

**ID:** ccc6170
**Título:** feat: capa de control de conteo — generar_id_intervencion, REGLAS_CONTEO, criterio_conteo por registro
**Fecha:** 2026-05-19

**Qué cambió:**
- `generar_id_intervencion()`: ID determinístico `{pac}_{fecha}_{hora}_{area}_{tipo[:12]}_{md5[:6]}`
- `REGLAS_CONTEO`: dict con lista `CUENTA` (15 marcadores clínicos) y `MIN_CHARS=30`
- `_criterio_conteo()`: aplica reglas en orden — min chars → duplicado exacto → marcador → sin marcador
- Cada registro en `parsear_intervenciones()` recibe su `id_intervencion` y `criterio_conteo`

**Impacto:**
- Permite distinguir registros clínicamente válidos de ruido estructural dentro del mismo HC
- Eliminación de duplicados exactos dentro de un archivo (set `textos_vistos`)

**Problema que resolvió:**
- Sin criterio de conteo, bloques de cabecera, líneas vacías y entradas repetidas inflaban el total

**Estado:** Activo

---

## Commit

**ID:** 5117855
**Título:** fix: intervenciones_por_tipo unificado sin duplicados con/sin tilde
**Fecha:** 2026-05-18

**Qué cambió:**
- Normaliza claves de `intervenciones_por_tipo`: `enfermeria → enfermería`, `evolucion → evolución`, `diagnostico → diagnóstico`, `indicacion → indicación`, `clinica → clínica`
- Reemplaza comparación directa por normalización antes del Counter

**Impacto:**
- Sin esta corrección, "nota de enfermeria" y "nota de enfermería" generaban dos claves distintas

**Problema que resolvió:**
- Tipos duplicados con/sin tilde en el desglose del frontend

**Estado:** Activo

---

## Commit

**ID:** ad3c1fa
**Título:** data: reprocesamiento HCs con criterio_conteo vigente, deduplicación BD, 1231 intervenciones válidas en 4 pacientes
**Fecha:** 2026-05-19

**Qué cambió:**
- Reprocesa los 4 archivos XLS con el pipeline actualizado (criterio_conteo + clasificador corregido)
- Deduplicación de la BD: elimina filas antiguas de los mismos archivos
- `hcs.db` queda con 5 filas (PAC-015 stale + 4 válidos)

**Impacto:**
- Estado canónico de la BD: 1231 intervenciones válidas en PAC-046, PAC-047, PAC-048, PAC-049

**Problema que resolvió:**
- Datos de versiones anteriores del pipeline convivían con datos del pipeline nuevo

**Estado:** Activo (commit de datos, no de código)

---

## Commit

**ID:** 1a76d50
**Título:** fix: reporte-total con deduplicación y filtro de registros stale
**Fecha:** 2026-05-20

**Qué cambió:**
- `GET /hcd/reporte-total`: aplica `MAX(id) GROUP BY archivo` antes de agregar
- Filtra stale: excluye registros donde `total_pac == 0` o `sum(areas) != total_pac`
- Agrega campo `archivo` y `fecha_procesamiento` por caso para trazabilidad

**Impacto:**
- Enfermería en el consolidado: 1432 (inflado por PAC-015) → 854 (correcto)
- 4 pacientes válidos en el reporte ejecutivo

**Problema que resolvió:**
- PAC-015 (JSON de esquema anterior) inflaba las áreas del reporte global sin aportar intervenciones válidas

**Estado:** Activo

---

## Interconsultas

---

## Commit

**ID:** d33e766
**Título:** feat: interconsulta_pendiente + multi-event extraction + score por estado
**Fecha:** 2026-05-18

**Qué cambió:**
- Agrega estado `interconsulta_pendiente` a `REGLAS_IC`
- Lógica multi-evento: si un bloque menciona ≥2 servicios externos, detecta estado por ventana local (±120 chars) y usa estado global del bloque como fallback
- `contar = True` solo para `interconsulta_efectiva` y `seguimiento`

**Impacto:**
- Evita contar como efectiva una IC mencionada sin evidencia de que ocurrió

**Problema que resolvió:**
- Bloque con "nutrición y traumatología" clasificaba ambas como efectivas aunque solo fuera una mención

**Estado:** Activo

---

## Commit

**ID:** e8caf62
**Título:** feat: interconsultas con nombre paciente y estados coloreados, deduplicación por contenido
**Fecha:** 2026-05-19

**Qué cambió:**
- Frontend: muestra código paciente junto a cada IC, estados con color semántico
- Deduplicación por contenido en la vista de interconsultas (evita mostrar duplicados visuales)

**Impacto:**
- Mejora trazabilidad: cada IC se puede vincular a su HC de origen

**Problema que resolvió:**
- La vista previa mostraba ICs sin saber a qué paciente correspondían

**Estado:** Activo

---

## Commits anteriores de interconsultas (UI/UX)

**IDs:** 4dc8af3, 0aa5ad6, 79180b9
**Fechas:** 2026-05-19

**Qué cambiaron:**
- `4dc8af3`: reemplaza score numérico por etiqueta "confirmada/no confirmada"; agrega expander explicativo
- `0aa5ad6`: reemplaza badges dinámicos por `st.container+columns` (fix error DOM removeChild en Streamlit)
- `79180b9`: expander con explicación del criterio de confianza para el usuario clínico

**Estado:** Activo (presentación final del módulo)

---

## RAG

---

## Commit

**ID:** 81b185c
**Título:** feat: módulo RAG con gestión documental
**Fecha:** 2026-05-20

**Qué cambió:**
- `GET /rag/documentos`: lista archivos en `rag/protocolos/` con estado indexado/pendiente desde ChromaDB
- `POST /rag/subir`: guarda archivo sin indexar
- Frontend: dos tabs — Documentos (listado + carga) y Búsqueda semántica (query + fuentes expandibles)

**Impacto:**
- El usuario puede gestionar la base de conocimiento desde la UI sin acceso a la terminal

**Problema que resolvió:**
- Documentos solo se podían indexar manualmente vía scripts

**Estado:** Activo

---

## Commit

**ID:** 265a57a
**Título:** feat: indexación automática de PDFs al subir en /rag/subir
**Fecha:** 2026-05-20

**Qué cambió:**
- `POST /rag/subir` extrae texto con `pypdf` (chunks de 500 chars) e indexa en ChromaDB vía `upsert`
- Soporta PDF y TXT; devuelve `chunks` indexados o error con detalle
- Documentos reales indexados: `9789243548067_spa.pdf` (154 chunks), `Ley 26657.pdf` (64 chunks)

**Impacto:**
- Flujo completo: subir PDF → indexar → consultar semánticamente, sin intervención manual

**Problema que resolvió:**
- `/rag/subir` solo guardaba el archivo; la indexación en ChromaDB era manual

**Estado:** Activo

---

## Commit

**ID:** b3624d5
**Título:** fix: imports FastAPI en encabezado, ruta RAG_PROTOCOLOS_DIR corregida
**Fecha:** 2026-05-20

**Qué cambió:**
- Mueve imports de `BeautifulSoup`, `xlrd`, `openpyxl` al encabezado del archivo
- Corrige `RAG_PROTOCOLOS_DIR` para resolverse relativo a `BASE_DIR` (no al CWD)

**Impacto:**
- Sin esta corrección, el directorio de protocolos no se encontraba si la API se iniciaba desde otro directorio

**Problema que resolvió:**
- Error 500 al listar documentos RAG en algunos entornos de ejecución

**Estado:** Activo

---

## Métricas HCD

---

## Commit

**ID:** a997864
**Título:** feat: variables clínicas detectadas automáticamente, métricas completas
**Fecha:** 2026-05-17

**Qué cambió:**
- `variables_dict`: 16 variables clínicas con listas de palabras clave (ideación autolítica, alucinaciones, delirio, etc.)
- Detección booleana por presencia de cualquier palabra clave en el texto completo del HC
- Frontend: métricas con gráficos de barras por área, variables clínicas presentes

**Impacto:**
- Primera versión de detección automática de variables clínicas relevantes para salud mental

**Problema que resolvió:**
- La carga asistencial solo mostraba conteos; sin información sobre complejidad clínica del caso

**Estado:** Activo

---

## Commit

**ID:** 80ebb5c
**Título:** fix: dias_totales usa fechas clínicas reales, saltea header VADIGU
**Fecha:** 2026-05-19

**Qué cambió:**
- `fechas_clinicas = fechas[2:]` — salta las 2 primeras fechas del reporte VADIGU (rango del reporte = 6 meses)
- Calcula `dias_internacion` como diferencia entre min y max de fechas clínicas reales

**Impacto:**
- Antes: todos los HC mostraban ~181 días (el rango del reporte). Ahora refleja la internación real

**Problema que resolvió:**
- VADIGU inserta en el encabezado las fechas de inicio y fin del reporte; no son fechas de internación

**Estado:** Activo

---

## Commits de métricas (UI/metodología)

**IDs:** 23d7560, 94224ae, e87c4ac, a4ee0c7
**Fechas:** 2026-05-19 / 2026-05-20

**Qué cambiaron:**
- `23d7560`: reorganización metodológica — separación de gráficos por área/tipo en módulo Métricas HCD
- `94224ae`: claridad metodológica — nota explicativa sobre qué cuenta y qué no cuenta
- `e87c4ac`: KPIs recalculados desde `casos[]` individuales; estadísticas de días (promedio, mediana, min, max)
- `a4ee0c7`: consolidado excluye PAC-015 de las áreas (stale); nota metodológica en el gráfico

**Estado:** Activo

---

## Base de Datos

---

## Commit

**ID:** cbf51ad (ver NLP)
**Nota:** La BD SQLite (`hcs.db`) se inicializa en este commit con `CREATE TABLE IF NOT EXISTS hcs_procesadas`.

**Esquema vigente:**
```sql
CREATE TABLE hcs_procesadas (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo  TEXT,
    resumen  TEXT,   -- JSON completo del pipeline
    texto_extraido TEXT,
    fecha    TEXT
)
```

**Estado:** Activo

---

## Commit

**ID:** ad3c1fa (ver Conteo)
**Nota:** Estado canónico de la BD post-reprocesamiento. 5 filas, 5 archivos distintos, 0 duplicados.

---

## Seguridad / Pseudonimización

---

## Commit

**ID:** 19861c4
**Título:** fix: pseudonimización urgente — reemplaza nombres reales por PAC-NNN, elimina texto_extraido de respuestas API
**Fecha:** 2026-05-19

**Qué cambió:**
- El código de paciente se genera como `PAC-{id:03d}` (nunca expone el nombre del archivo)
- `texto_extraido` se elimina de todas las respuestas de la API (se sigue guardando en BD, no se devuelve)
- El campo `codigo_paciente` en reportes usa el ID de la BD, no el nombre del archivo

**Impacto:**
- Ninguna respuesta de la API devuelve texto clínico crudo ni nombres de pacientes
- `texto_extraido` en BD se guarda truncado a 500 chars para auditoría interna; no es accesible vía endpoint

**Problema que resolvió:**
- Respuestas de API exponían fragmentos de texto clínico real y nombre de archivo con datos del paciente

**Estado:** Activo — crítico para cumplimiento

---

## Reportes

---

## Commit

**ID:** 58fb6f6
**Título:** feat: módulo Resumen HCs y endpoint /hcd/reporte-total para reporte ejecutivo
**Fecha:** 2026-05-19

**Qué cambió:**
- `GET /hcd/reporte-total`: agrega datos de todos los pacientes válidos en un resumen ejecutivo
- Campos: `resumen_ejecutivo`, `variables_clinicas_por_frecuencia`, `interconsultas_por_estado`, `casos[]`
- Frontend: módulo "Resumen HCs" con KPIs, tabla de casos, variables clínicas frecuentes

**Impacto:**
- Primer reporte multi-paciente real; base del módulo de análisis poblacional

**Problema que resolvió:**
- No había forma de ver todos los pacientes procesados en conjunto; solo vista individual

**Estado:** Activo

---

## Commits de reportes (UI)

**IDs:** 53130c6, 42c2262, a4ba92a
**Fechas:** 2026-05-19

**Qué cambiaron:**
- `53130c6`: título institucional y disclaimer de uso en módulo Resumen HCs
- `42c2262`: etiquetas neutrales en variables clínicas (no diagnósticas); fix título duplicado en módulo IC
- `a4ba92a`: advertencia explícita de que las interconsultas son estimaciones, no registros definitivos

**Estado:** Activo

---

## Frontend / Arquitectura de módulos

---

## Commit

**ID:** df4a0b2
**Título:** refactor: reorganización de módulos en sidebar y separación NLP/RAG/LLM
**Fecha:** 2026-05-20

**Qué cambió:**
- Sidebar: 10 módulos ordenados — Ingresar HC → OCR → Pseudonimización → Procesamiento NLP → RAG → LLM local → Interconsultas HCD → Métricas HCD → Resumen HCs → Informe
- Nuevo módulo "LLM local": interfaz Gemma activa, Mistral placeholder
- "Procesamiento NLP": describe el pipeline sin interfaz Gemma (movida a LLM local)

**Estado:** Activo

---

---

## Arquitectura actual

```
HC (XLS/HTML VADIGU)
  │
  ▼
BeautifulSoup → texto crudo
  │
  ▼
parsear_intervenciones()
  ├── detecta patrón: dd/mm/yyyy - HH:MM hs
  ├── segmenta en bloques por marcadores de tipo
  ├── por cada bloque:
  │     ├── generar_id_intervencion()
  │     │     formato: {pac}_{fecha}_{hora}_{area}_{tipo[:12]}_{md5[:6]}
  │     └── _criterio_conteo()
  │           reglas: MIN_CHARS(30) → duplicado_exacto → marcador_CUENTA → sin_marcador
  │
  ▼
clasificar_area_hibrido()  [por cada registro]
  ├── Capa 1: PROFESIONALES_SALUD_MENTAL (diccionario por nombre de firma)
  ├── Capa 2: REGLAS_AREA_TEXTO (keywords por área, ~70 entradas)
  ├── Capa 3: modelo NLP (TF-IDF + LogisticRegression, accuracy=0.9298)
  └── Capa 4: fallback → "otros"
  │
  ▼
detectar_ics()  [sobre todos los registros]
  ├── busca SERVICIOS_EXTERNOS en cada bloque
  ├── bloque con ≥2 servicios: ventana local ±120 chars + estado global
  ├── clasificar_estado_ic(): pendiente / inicial / efectiva / seguimiento
  ├── contar = True solo si efectiva o seguimiento
  └── + detección por regex "Profesional: [externo]"
  │
  ▼
SQLite: INSERT INTO hcs_procesadas (archivo, resumen_json, texto[:500], fecha)
  │
  ▼
GET /hcd/reporte-total
  ├── deduplicación: MAX(id) GROUP BY archivo
  ├── filtro stale: total_pac > 0 AND sum(areas) == total_pac
  └── agrega: intervenciones, días, áreas, variables clínicas, ICs
```

---

## Reglas activas actuales

### Deduplicación

- **Dentro de un HC** (`_criterio_conteo`): el set `textos_vistos` acumula textos normalizados durante el parseo. Si el mismo bloque de texto aparece dos veces en el mismo archivo, el segundo recibe `NO_CUENTA:duplicado`.
- **Entre HCs en BD** (`/hcd/reporte-total`): `MAX(id) GROUP BY archivo` — si un mismo archivo fue procesado varias veces, solo se usa el registro más reciente.
- **Vista frontend** (Interconsultas HCD): deduplicación visual por contenido de la IC.

### Registros stale

Un registro de la BD es stale cuando su JSON no tiene `total_intervenciones > 0` **o** cuando `sum(intervenciones_por_area) != total_intervenciones`. Condición en `reporte-total` línea 229:
```python
datos_validos = total_pac > 0 and sum(areas.values()) == total_pac
```
Registros stale se excluyen de todos los agregados. No se eliminan de la BD. Actualmente: PAC-015 (id=15), procesado con endpoint anterior de esquema distinto.

### Criterios de conteo

Un bloque cuenta como intervención si:
1. `len(texto) >= 30`
2. No es duplicado exacto dentro del mismo HC
3. El tipo de bloque o los primeros 150 chars contienen al menos un marcador de `REGLAS_CONTEO["CUENTA"]`

Marcadores vigentes (15): evolución clínica, nota de enfermería, seguimiento, interconsulta inicial, reevaluación, evaluación psicológica, evaluación psiquiátrica, trabajo social, acompañamiento terapéutico, terapia ocupacional (y variantes con/sin tilde).

### Clasificación híbrida

Cuatro capas en orden estricto de prioridad:
1. Diccionario de profesionales por nombre (determinista, ~50 entradas)
2. Keywords por texto (`REGLAS_AREA_TEXTO`, ~70 entradas, 7 áreas)
3. Modelo NLP TF-IDF + LR (accuracy 92.98%, 5 clases)
4. Fallback → `"otros"`

Prioridad de áreas en capa 2 (orden de iteración del dict): psiquiatria > psicologia > terapia_ocupacional > trabajo_social > acompanante_terapeutico > enfermeria > psicopedagogia.

### Interconsultas

- Solo se marcan `contar=True` las IC con estado `interconsulta_efectiva` o `seguimiento`
- Estados posibles: `interconsulta_pendiente` (score 3), `interconsulta_inicial` (4), `interconsulta_efectiva` (5), `seguimiento` (2), `mencion_servicio` (0)
- El módulo muestra advertencia explícita: son estimaciones, no registros definitivos
- ICs del endpoint `/hcd/reporte-total` se limitan a las primeras 10 por HC (`ics[:10]`)
