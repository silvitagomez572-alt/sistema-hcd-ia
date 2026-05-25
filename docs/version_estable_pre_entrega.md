# Versión estable pre-entrega — Sistema HCD IA

**Fecha de congelamiento:** 2026-05-25
**Pipeline:** v1.0.0
**Commit:** ver `git log --oneline -1`
**Estado:** criterios clínicos y metodológicos congelados para validación institucional

---

## 1. Dataset final

### Inventario de archivos

| Archivo | id BD | Estado | Motivo |
|---------|-------|--------|--------|
| `Cronológico del paciente (5).xls` | 46 | ✅ Válido | PAC-046 |
| `Cronológico del paciente (6).xls` | 47 | ✅ Válido | PAC-047 |
| `Cronológico del paciente (7).xls` | 48 | ✅ Válido | PAC-048 |
| `Cronológico del paciente (8).xls` | 49 | ✅ Válido | PAC-049 |
| `HC_001_SaludMental.json` | 15 | ⚠️ Stale | Esquema anterior al pipeline NLP; mantenido en BD por trazabilidad |
| `Cronológico del paciente (7)(1).xls` | — | 🗑️ Eliminado | Duplicado exacto de PAC-048 (MD5/SHA1 idénticos, eliminado el 2026-05-25) |
| `Cronológico_paciente_5.xls` | — | ❌ No procesable | Archivo corrupto: página de login de Google Drive (descarga fallida) |

### Números finales verificados

| Métrica | Valor |
|---------|-------|
| **Pacientes únicos válidos** | **4** |
| Total candidatos raw (bloques parseados) | 1.444 |
| Descartados por criterio de conteo | 213 (14.8%) |
| **Intervenciones válidas finales** | **1.231** |
| Días totales de internación | 905 |
| Tasa global intervenciones / día | 1.36 |
| Promedio intervenciones / paciente | 307.8 |
| ICs detectadas | 13 |
| ICs que cuentan (efectivas o seguimiento) | 3 |
| Registros stale en BD | 1 (PAC-015) |
| Duplicados eliminados | 1 (PAC-050) |

---

## 2. Detalle por HC

| HC | Días | Int. | Raw | Tasa/día | Enf | Psiq | Psic | TO | TS | AT | ICs | ICs ef. |
|----|------|------|-----|----------|-----|------|------|----|----|----|-----|---------|
| PAC-046 | 206 | 588 | 680 | 2.854 | 391 (66.5%) | 3 | 114 | 63 | 12 | 1 | 10 | 3 |
| PAC-047 | 73* | 18 | 23 | 0.247* | 13 (72.2%) | 1 | 2 | 1 | 0 | 0 | 3 | 0 |
| PAC-048 | 5 | 16 | 17 | 3.200 | 9 (56.2%) | 0 | 6 | 1 | 0 | 0 | 0 | 0 |
| PAC-049 | 621 | 609 | 724 | 0.981 | 441 (72.4%) | 0 | 83 | 73 | 7 | 3 | 0 | 0 |

*PAC-047: los 73 días y la tasa 0.247 son artefactos del cálculo temporal — ver sección de limitaciones.

**Variables clínicas presentes por HC:**

| HC | Variables detectadas |
|----|---------------------|
| PAC-046 | alucinaciones · delirio/psicosis · agresividad · ansiedad/insomnio · sin red vincular · adherencia problemática · internación prolongada · ideas persecutorias · estado estable · bradipsiquia · crisis |
| PAC-047 | ideación autolítica · delirio/psicosis · sin red vincular · consumo sustancias · estado estable · riesgo de fuga |
| PAC-048 | ideación autolítica · estado estable · crisis |
| PAC-049 | delirio/psicosis · agresividad · sin red vincular · adherencia problemática · internación prolongada · estado estable · bradipsiquia |

---

## 3. Semáforo de calidad — estado final

| HC | Semáforo | Estado | Alerta |
|----|----------|--------|--------|
| PAC-046 | 🟢 | Consistente | — |
| PAC-047 | 🟡 | Revisar cálculo | Artefacto temporal VADIGU — los 73 días calculados incluyen el período del reporte, no la internación continua |
| PAC-048 | 🟢 | Consistente | — |
| PAC-049 | 🟡 | Revisar cálculo | Internación prolongada (621 días, 1.7 años) — verificar completitud del registro |
| PAC-015 | 🔴 | Inconsistente real | Stale: esquema anterior al pipeline NLP, mantenido en BD por trazabilidad |

**Criterios activos del semáforo:**

| Semáforo | Criterio |
|----------|----------|
| 🔴 Inconsistente real | Stale (JSON inválido o `sum(áreas) ≠ total_intervenciones`) |
| 🔴 Inconsistente real | Duplicado real confirmado (contenido del pipeline idéntico: total + áreas + días) |
| 🟡 Revisar cálculo | Tasa aparente < 0.3 int/día con período > 30 días: probable artefacto del rango de fechas VADIGU |
| 🟡 Revisar cálculo | Período > 365 días: outlier de duración, requiere verificación de completitud |
| 🟢 Consistente | Ninguna condición anterior |

**Criterios explícitamente NO incluidos:**
- Psiquiatría = 0 intervenciones (puede reflejar limitación del clasificador, no ausencia real de actividad)
- Enfermería > 65% (patrón estructural del formato VADIGU, presente en todos los HCs)
- HC corta con tasa alta (normal en internación aguda breve)

---

## 4. Criterios activos del pipeline

### Criterio de conteo (`REGLAS_CONTEO`)

Un bloque se cuenta como intervención si cumple las tres condiciones en orden:

1. `len(texto) ≥ 30` caracteres
2. No es texto duplicado exacto dentro del mismo HC (set `textos_vistos`)
3. El tipo de bloque o los primeros 150 caracteres contienen al menos un marcador de la lista `CUENTA`

**Marcadores `CUENTA` vigentes (15):**
evolucion clinica · nota de enfermeria · seguimiento · interconsulta inicial · reevaluacion · evaluacion psicologica · evaluacion psiquiatrica · trabajo social · acompañamiento terapeutico · terapia ocupacional (y variantes con/sin tilde)

### Clasificador híbrido (4 capas)

| Capa | Mecanismo | Prioridad |
|------|-----------|-----------|
| 1 | Diccionario por nombre de profesional | Máxima — determinista |
| 2 | Keywords por texto (`REGLAS_AREA_TEXTO`, ~70 entradas) | Alta |
| 3 | Modelo NLP: TF-IDF + Logistic Regression (accuracy 92.98%) | Media |
| 4 | Fallback → `otros` | Mínima |

**Prioridad de áreas en capa 2:**
psiquiatria > psicologia > terapia_ocupacional > trabajo_social > acompanante_terapeutico > enfermeria > psicopedagogia

### Deduplicación de la BD

`GET /hcd/reporte-total` aplica `MAX(id) GROUP BY archivo` antes de agregar. Registros stale (inconsistencia aritmética) se excluyen del conteo pero no se eliminan de la BD.

### Detección de interconsultas

`contar = True` solo para estados `interconsulta_efectiva` (score 5) y `seguimiento` (score 2).
Las ICs con estado `interconsulta_inicial`, `interconsulta_pendiente` y `mencion_servicio` se detectan pero no cuentan como intervenciones.

---

## 5. Limitaciones conocidas

### L1 — Artefacto temporal en PAC-047

El pipeline calcula `dias_internacion = max(fechas_clínicas) - min(fechas_clínicas)`. Para PAC-047, el texto exportado por VADIGU cubre el período completo del reporte (181 días con múltiples episodios), no una única internación continua. Los 73 días calculados son la diferencia entre la primera fecha clínica del texto y la última, que incluye reingresos y controles ambulatorios. La tasa resultante (0.247 int/día) es un artefacto.

**Impacto:** el conteo de intervenciones (18) y la clasificación por áreas son correctos. Solo el cálculo de días y tasa están afectados para este HC.

### L2 — Psiquiatría subestimada sistémicamente

El clasificador asigna `psiquiatria` cuando el texto contiene keywords del área o el nombre del profesional está en `PROFESIONALES_SALUD_MENTAL`. Las evoluciones escritas por psiquiatras que no usan esas keywords (o cuyo nombre no está en el diccionario) se clasifican como `otros` o según otra área que coincida primero. Este sesgo afecta a PAC-048 (0 int.) y PAC-049 (0 int. en 621 días).

**Impacto:** el total de intervenciones es correcto. La distribución por área subestima psiquiatría y sobreestima `otros`.

### L3 — Dominancia de enfermería (patrón estructural)

Las notas de enfermería en VADIGU tienen cabecera estándar (`Nota de enfermería`) que el parser segmenta con alta fidelidad. Las evoluciones de otros profesionales son más heterogéneas. El resultado es que enfermería representa 56–72% en todos los HCs independientemente del equipo real.

**Impacto:** la distribución por área es un reflejo del registro, no necesariamente de la carga asistencial real de cada disciplina.

### L4 — ICs ausentes en PAC-049 (621 días)

El HC más largo no tiene interconsultas detectadas. Posibles causas: los servicios externos mencionados no coinciden con `SERVICIOS_EXTERNOS`, o las frases de derivación no coinciden con `REGLAS_IC`. Requiere revisión manual del texto original.

### L5 — Solo 4 tipos de intervención clasificados

`intervenciones_por_tipo` captura solo los bloques con marcador explícito en la cabecera. La mayoría de los bloques que sí cuentan lo hacen por el tipo `nota de enfermería` (88.1% del total) o `evolución clínica` (11.1%). Los marcadores restantes de `REGLAS_CONTEO` (reevaluación, evaluación psicológica, etc.) no aparecen en los tipos porque el parser los detecta en el texto del bloque, no en la cabecera de tipo.

---

## 6. Módulos del sistema

| Módulo | Estado |
|--------|--------|
| Ingresar HC (XLS/HTML VADIGU) | ✅ Activo |
| Procesamiento NLP (parser + clasificador híbrido) | ✅ Activo |
| RAG — Protocolos clínicos (ChromaDB + SentenceTransformer) | ✅ Activo |
| LLM local (Gemma 2B vía Ollama) | ✅ Activo (requiere Ollama en localhost:11434) |
| Interconsultas HCD | ✅ Activo |
| Métricas HCD (gráficos Altair) | ✅ Activo |
| Resumen HCs (reporte ejecutivo multi-paciente) | ✅ Activo |
| Auditoría clínica y trazabilidad | ✅ Activo |
| Pseudonimización | ⚠️ Parcial (nombres en texto_extraido de BD no expuestos vía API) |
| OCR | 🔄 En desarrollo |

---

*Documento generado manualmente sobre datos reales de `hcs.db`. Sin datos de identificación de pacientes.*
*No modificar hasta confirmación de entrega.*
