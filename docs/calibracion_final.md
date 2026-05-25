# Calibración final — Auditoría clínica del pipeline HCD IA

**Fecha:** 2026-05-25
**Pipeline:** v1.0.0 · commit `f512aaa`
**Base:** resultado de `validacion_clinica.md` + análisis forense de duplicados

---

## 1. Verificación de duplicado: PAC-048 vs PAC-050

### Archivos comparados

| Campo | PAC-048 | PAC-050 |
|-------|---------|---------|
| Nombre de archivo | `Cronológico del paciente (7).xls` | `Cronológico del paciente (7)(1).xls` |
| Tamaño (bytes) | 55.685 | 55.685 |
| MD5 del archivo | `7292a173d097e9346ce270477fcdbf8f` | `7292a173d097e9346ce270477fcdbf8f` |
| SHA1 del archivo | `328b2352c020614aec12712062e4d8d71b8ba982` | `328b2352c020614aec12712062e4d8d71b8ba982` |
| Hash texto_extraido (MD5) | `4ad9dcd829c0a1dc2f3fceeec922f525` | `4ad9dcd829c0a1dc2f3fceeec922f525` |
| total_intervenciones | 16 | 16 |
| total_registros_raw | 17 | 17 |
| intervenciones_por_area | `{enf:9, psic:6, to:1}` | `{enf:9, psic:6, to:1}` |
| intervenciones_por_tipo | `{nota enf.:14, evol. clínica:2}` | `{nota enf.:14, evol. clínica:2}` |
| internacion | `{dias:5, reingresos:0, cambios_cama:1}` | `{dias:5, reingresos:0, cambios_cama:1}` |
| variables clínicas presentes | `[ideacion_autolitica, estado_estable, crisis]` | `[ideacion_autolitica, estado_estable, crisis]` |
| interconsultas detectadas | `[]` | `[]` |
| fecha_procesamiento BD | 2026-05-19 | 2026-05-25 |

### Veredicto

**Duplicado real confirmado.** MD5 y SHA1 del archivo fuente son idénticos. Texto crudo idéntico. Todos los resultados del pipeline idénticos. El archivo `(7)(1).xls` es una copia renombrada del mismo HC, descargado en una segunda ocasión desde VADIGU.

**Acción recomendada:** eliminar PAC-050 (id=50) de la BD con `DELETE /hcd/reportes/duplicados` cuando se confirme. No se elimina automáticamente en esta auditoría.

---

## 2. Calibración del semáforo de calidad

### Criterios anteriores (invalidados)

Los criterios anteriores incluían:
- `psiquiatría = 0` → 🟡 alerta
- `enfermería > 65%` → 🟡 alerta
- `HC corta con tasa alta` → 🟡 alerta

**Por qué se cambian:**
- La ausencia de intervenciones de psiquiatría **no indica inconsistencia del registro**: refleja cómo el profesional firmó el bloque, si su nombre está en el diccionario, o si el texto contiene keywords del clasificador. No es un error detectable sin revisar la HC manualmente.
- La dominancia de enfermería es un patrón estructural de VADIGU, no un outlier del caso.
- Una HC corta (5 días) con tasa alta (3.2/día) es clínicamente normal en una internación aguda breve.

### Criterios calibrados

| Semáforo | Criterio | Base |
|----------|----------|------|
| 🔴 Inconsistente | Stale (JSON inválido o `sum(áreas) ≠ total_intervenciones`) | Inconsistencia aritmética en el propio registro |
| 🔴 Inconsistente | Duplicado real (mismo contenido: total, áreas e internación idénticos a otro registro) | Hash idéntico confirmado |
| 🟡 Revisar | Tasa < 0.3 int/día con internación > 30 días | Densidad temporal anómala — posible exportación parcial |
| 🟡 Revisar | Internación > 365 días | Outlier de duración — requiere verificación clínica |
| 🟡 Revisar | Raw < 25 bloques con internación > 60 días | Volumen de registro inconsistente con el período |
| 🟢 Consistente | Ninguna condición anterior | |

**Psiquiatría = 0:** se registra como observación clínica en la tabla, no como criterio de semáforo. Puede indicar limitación del clasificador, no necesariamente ausencia de actividad psiquiátrica real.

---

## 3. Tabla calibrada final

| HC | id BD | Días | Int. | Raw | Tasa/día | Semáforo | Estado | Alerta |
|----|-------|------|------|-----|----------|----------|--------|--------|
| PAC-046 | 46 | 206 | 588 | 680 | 2.854 | 🟢 | Consistente | — |
| PAC-047 | 47 | 73 | 18 | 23 | 0.247 | 🟡 | Revisar | Tasa < 0.3/día en 73 días; raw=23 en 73 días |
| PAC-048 | 48 | 5 | 16 | 17 | 3.200 | 🟢 | Consistente | — |
| PAC-049 | 49 | 621 | 609 | 724 | 0.981 | 🟡 | Revisar | Internación prolongada (621 días, 1.7 años) |
| PAC-050 | 50 | 5 | 16 | 17 | 3.200 | 🔴 | Inconsistente | Duplicado real de PAC-048 — archivo idéntico |
| PAC-015 | 15 | — | — | — | — | 🔴 | Inconsistente | Stale: esquema anterior, sum(áreas)≠total |

---

## 4. Recalculo de alertas por tasa

### Distribución de tasas en el dataset (sin PAC-050 duplicado)

| HC | Tasa int/día | Clasificación |
|----|-------------|---------------|
| PAC-047 | 0.247 | ⬇ Baja — anomalía: 23 bloques raw en 73 días |
| PAC-049 | 0.981 | Normal — internación prolongada, ritmo sostenido |
| PAC-046 | 2.854 | Normal — internación activa con equipo completo |
| PAC-048 | 3.200 | Normal en contexto de HC corta (5 días) |

**Media del dataset:** 1.82 int/día (excluyendo PAC-050)
**Rango plausible para internación de salud mental:** 0.5 – 4.0 int/día según literatura de registros clínicos hospitalarios.

### Análisis de PAC-047 (tasa 0.247)

El `detalle_clasificacion` revela la causa:
- El archivo exportado cubre el período 17/11/2025 – 17/05/2026 (rango del reporte VADIGU = 181 días), pero la internación activa es mucho menor.
- Los 73 días se calculan como diferencia entre la primera y última fecha clínica del texto (05/03/2026 – 17/05/2026), pero el texto incluye múltiples episodios de urgencia y una re-internación breve, no una internación continua de 73 días.
- Los 23 bloques raw reflejan el total de entradas en ese período fragmentado, lo que es consistente con varios ingresos cortos.

**Conclusión:** La tasa 0.247 es un artefacto del cálculo de días, no una señal de registro incompleto. El pipeline calcula `dias = max(fechas) - min(fechas)` en el texto, que en este caso incluye el período completo del reporte VADIGU, no la duración de la internación.

---

## 5. Observaciones clínicas (no criterios de semáforo)

Estas condiciones se documentan por su relevancia clínica pero **no modifican el semáforo** porque no indican inconsistencia del registro.

| HC | Observación | Interpretación |
|----|-------------|----------------|
| PAC-046 | Psiquiatría: 3 int (0.5%) | Muy baja para 206 días. El clasificador puede no detectar las evoluciones psiquiátricas si la firma no está en el diccionario. |
| PAC-047 | Psiquiatría: 1 int (5.6%) | Marginal. Presente pero mínimo. |
| PAC-048 | Psiquiatría: 0 int | HC de 5 días. La internación aguda puede no incluir evolución psiquiátrica documentada en el período exportado. |
| PAC-049 | Psiquiatría: 0 int en 621 días | Improbable clínicamente. Probable limitación del clasificador: firma no reconocida o evoluciones sin keywords. Requiere revisión manual. |
| PAC-046 | ICs efectivas: 3 | Único HC con ICs confirmadas. Los otros 3 no tienen ICs o tienen solo menciones. |
| PAC-049 | ICs: 0 en 621 días | Estadísticamente improbable. Posible causa: los servicios externos mencionados no coinciden con `SERVICIOS_EXTERNOS` del clasificador. |

---

## 6. Estado del dataset — resumen ejecutivo calibrado

| Métrica | Valor |
|---------|-------|
| Archivos disponibles | 6 |
| Archivos procesables | 5 (1 era página de login de Google Drive) |
| Registros en BD | 6 |
| Stale excluidos | 1 (PAC-015) |
| Duplicados reales | 1 (PAC-050 = PAC-048) |
| **Pacientes únicos válidos** | **4** |
| Total candidatos raw | 1.444 |
| Total descartados | 213 (14.7%) |
| **Intervenciones válidas** | **1.231** |
| Días totales internación (4 únicos) | 905 |
| Tasa global int/día | 1.36 |
| HCs 🟢 Consistente | 2 (PAC-046, PAC-048) |
| HCs 🟡 Revisar | 2 (PAC-047, PAC-049) |
| HCs 🔴 Inconsistente | 2 (PAC-015, PAC-050) |

---

## 7. Cambios aplicados al sistema

### Frontend (`frontend/app.py` — módulo "Auditoría")

| Elemento | Antes | Después |
|----------|-------|---------|
| Criterio psiquiatría = 0 | 🟡 alerta | Eliminado del semáforo |
| Criterio enfermería > 65% | 🟡 alerta | Eliminado del semáforo |
| Criterio HC corta + tasa alta | 🟡 alerta | Eliminado del semáforo |
| Detección de duplicados | No existía | 🔴 por contenido idéntico (total + áreas + días) |
| Criterio tasa < 0.3 + días > 30 | No existía | 🟡 alerta |
| Criterio raw < 25 + días > 60 | No existía | 🟡 alerta |
| Etiqueta estado "OK" | "OK" | "Consistente" |
| Caption explicativo | No existía | Agrega descripción de criterios bajo la tabla |

No se modificaron: parser, clasificador híbrido, REGLAS_CONTEO, RAG, LLM, esquema de BD.

---

*Documento generado manualmente sobre datos reales de `hcs.db`. Sin datos de identificación de pacientes.*
