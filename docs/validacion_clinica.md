# Validación Clínica — Sistema HCD IA

**Fecha de auditoría:** 2026-05-25
**Pipeline:** v1.0.0 · commit `4bfdcb4`
**Auditor:** proceso automático sobre resultados del endpoint `/hcd/reporte-total`
**Objetivo:** Verificar plausibilidad clínica de los resultados. Sin modificar código ni reglas.

---

## 1. Inventario de archivos disponibles

| Archivo | Estado | Observación |
|---------|--------|-------------|
| `Cronológico del paciente (5).xls` | ✅ Procesado | PAC-046 |
| `Cronológico del paciente (6).xls` | ✅ Procesado | PAC-047 |
| `Cronológico del paciente (7).xls` | ✅ Procesado | PAC-048 |
| `Cronológico del paciente (7)(1).xls` | ✅ Procesado | PAC-050 — **duplicado exacto de PAC-048** |
| `Cronológico del paciente (8).xls` | ✅ Procesado | PAC-049 |
| `Cronológico_paciente_5.xls` | ❌ No procesable | Archivo corrupto: página de login de Google Drive (descarga fallida) |
| `HC_001_SaludMental.json` | ⚠️ Stale | PAC-015 — esquema anterior al pipeline NLP; excluido del conteo |

**Dataset real:** 4 pacientes únicos (PAC-046, PAC-047, PAC-048, PAC-049).
PAC-050 es una copia renombrada del mismo archivo que PAC-048 — resultados idénticos confirmados.

---

## 2. Detalle clínico por HC

### PAC-046 — `Cronológico del paciente (5).xls`

| Métrica | Valor |
|---------|-------|
| Días de internación | 206 |
| Candidatos raw | 680 |
| Descartados | 92 |
| **Intervenciones finales** | **588** |
| Tasa / día | 2.85 |
| Reingresos | 1 |
| Cambios de cama | 2 |
| ICs detectadas | 10 |
| ICs efectivas (contar=True) | 3 |

**Desglose por área profesional:**

| Área | N | % |
|------|---|---|
| Enfermería | 391 | 66.5% |
| Psicología | 114 | 19.4% |
| Terapia Ocupacional | 63 | 10.7% |
| Trabajo Social | 12 | 2.0% |
| Psiquiatría | 3 | 0.5% |
| Acomp. Terapéutico | 1 | 0.2% |
| Otros | 4 | 0.7% |

**Desglose por tipo de intervención:**

| Tipo | N | % |
|------|---|---|
| Nota de enfermería | 494 | 84.0% |
| Evolución clínica | 89 | 15.1% |
| Seguimiento | 4 | 0.7% |
| Indicación | 1 | 0.2% |

**Variables clínicas detectadas:**
alucinaciones · delirio/psicosis · agresividad · ansiedad/insomnio · sin red vincular · adherencia problemática · internación prolongada · ideas persecutorias · estado estable · bradipsiquia · crisis

**Alertas:**
- 🟡 Psiquiatría muy baja: 3 intervenciones (0.5%) en HC de internación de salud mental
- 🟡 Enfermería dominante: 66.5%

---

### PAC-047 — `Cronológico del paciente (6).xls`

| Métrica | Valor |
|---------|-------|
| Días de internación | 73 |
| Candidatos raw | 23 |
| Descartados | 5 |
| **Intervenciones finales** | **18** |
| Tasa / día | 0.25 |
| Reingresos | 0 |
| Cambios de cama | 1 |
| ICs detectadas | 3 |
| ICs efectivas (contar=True) | 0 |

**Desglose por área profesional:**

| Área | N | % |
|------|---|---|
| Enfermería | 13 | 72.2% |
| Psicología | 2 | 11.1% |
| Psiquiatría | 1 | 5.6% |
| Terapia Ocupacional | 1 | 5.6% |
| Otros | 1 | 5.6% |

**Desglose por tipo de intervención:**

| Tipo | N | % |
|------|---|---|
| Nota de enfermería | 14 | 77.8% |
| Evolución clínica | 4 | 22.2% |

**Variables clínicas detectadas:**
ideación autolítica · delirio/psicosis · sin red vincular · consumo de sustancias · estado estable · riesgo de fuga

**Alertas:**
- 🔴 Tasa muy baja: 0.25 int/día en 73 días. El HC tiene solo 23 registros raw — posible exportación parcial de VADIGU o período de baja actividad de registro.
- 🟡 Enfermería dominante: 72.2%
- 🟡 Solo 18 intervenciones en 73 días de internación

---

### PAC-048 — `Cronológico del paciente (7).xls`
### PAC-050 — `Cronológico del paciente (7)(1).xls` *(duplicado exacto de PAC-048)*

| Métrica | Valor |
|---------|-------|
| Días de internación | 5 |
| Candidatos raw | 17 |
| Descartados | 1 |
| **Intervenciones finales** | **16** |
| Tasa / día | 3.20 |
| Reingresos | 0 |
| Cambios de cama | 1 |
| ICs detectadas | 0 |
| ICs efectivas (contar=True) | 0 |

**Desglose por área profesional:**

| Área | N | % |
|------|---|---|
| Enfermería | 9 | 56.2% |
| Psicología | 6 | 37.5% |
| Terapia Ocupacional | 1 | 6.2% |
| Psiquiatría | 0 | 0.0% |

**Desglose por tipo de intervención:**

| Tipo | N | % |
|------|---|---|
| Nota de enfermería | 14 | 87.5% |
| Evolución clínica | 2 | 12.5% |

**Variables clínicas detectadas:**
ideación autolítica · estado estable · crisis

**Alertas:**
- 🟡 Psiquiatría ausente: 0 intervenciones registradas en HC de salud mental
- 🟡 HC muy corta: 5 días — posible internación breve, alta voluntaria o exportación parcial
- 🟡 Tasa alta en HC corta: 3.20 int/día (esperable en internación aguda corta)
- ⚠️ PAC-050 es duplicado exacto de PAC-048 (mismo nombre de paciente, misma HC, archivo renombrado). Se excluye PAC-050 del análisis poblacional.

---

### PAC-049 — `Cronológico del paciente (8).xls`

| Métrica | Valor |
|---------|-------|
| Días de internación | 621 |
| Candidatos raw | 724 |
| Descartados | 115 |
| **Intervenciones finales** | **609** |
| Tasa / día | 0.98 |
| Reingresos | 0 |
| Cambios de cama | 1 |
| ICs detectadas | 0 |
| ICs efectivas (contar=True) | 0 |

**Desglose por área profesional:**

| Área | N | % |
|------|---|---|
| Enfermería | 441 | 72.4% |
| Psicología | 83 | 13.6% |
| Terapia Ocupacional | 73 | 12.0% |
| Trabajo Social | 7 | 1.1% |
| Acomp. Terapéutico | 3 | 0.5% |
| Otros | 2 | 0.3% |
| Psiquiatría | 0 | 0.0% |

**Desglose por tipo de intervención:**

| Tipo | N | % |
|------|---|---|
| Nota de enfermería | 563 | 92.4% |
| Evolución clínica | 42 | 6.9% |
| Seguimiento | 4 | 0.7% |

**Variables clínicas detectadas:**
delirio/psicosis · agresividad · sin red vincular · adherencia problemática · internación prolongada · estado estable · bradipsiquia

**Alertas:**
- 🔴 Internación prolongada: 621 días (1.7 años). Fuera del rango habitual salvo casos de cronicidad declarada.
- 🔴 Psiquiatría ausente: 0 intervenciones en 621 días de internación de salud mental. Muy improbable clínicamente — indica que las evoluciones psiquiátricas no están siendo capturadas (firma no está en el diccionario, o no tiene keywords del clasificador).
- 🟡 0 interconsultas detectadas en 621 días
- 🟡 Nota de enfermería = 92.4% del total

---

## 3. Tabla final consolidada

| HC | Días | Int. finales | Raw | Desc. | Tasa/día | Psiquiatría | Enf. % | ICs ef. | Estado | Alertas principales |
|----|------|-------------|-----|-------|----------|-------------|--------|---------|--------|-------------------|
| PAC-046 | 206 | 588 | 680 | 92 | 2.85 | 3 (0.5%) | 66.5% | 3 | 🟡 Revisar | Psiq. baja, Enf. dominante |
| PAC-047 | 73 | 18 | 23 | 5 | 0.25 | 1 (5.6%) | 72.2% | 0 | 🔴 Alerta | Tasa muy baja, pocos registros |
| PAC-048 | 5 | 16 | 17 | 1 | 3.20 | 0 (0%) | 56.2% | 0 | 🟡 Revisar | Psiq. ausente, HC muy corta |
| PAC-049 | 621 | 609 | 724 | 115 | 0.98 | 0 (0%) | 72.4% | 0 | 🔴 Alerta | Internación prolongada, psiq. ausente |
| PAC-050 | 5 | 16 | 17 | 1 | 3.20 | 0 (0%) | 56.2% | 0 | ⚠️ Dup. | Duplicado exacto de PAC-048 |
| PAC-015 | — | — | — | — | — | — | — | — | ⚠️ Stale | Esquema anterior al pipeline NLP |
| `Cronológico_paciente_5.xls` | — | — | — | — | — | — | — | — | ❌ Error | Archivo no descargado (login Google) |

---

## 4. Outliers detectados

### 4.1 Internación prolongada

**PAC-049 — 621 días (1.7 años)**
- Clínicamente posible en internación crónica de salud mental, pero requiere confirmación.
- La tasa de 0.98 int/día es baja para una internación tan larga; puede indicar períodos sin cobertura de registro en el HC exportado.
- Ausencia total de psiquiatría en ese período es clínicamente improbable.

### 4.2 Psiquiatría ausente en HCs de salud mental

Tres de cuatro pacientes tienen psiquiatría = 0 (PAC-048, PAC-049) o casi 0 (PAC-046: 0.5%).

**Hipótesis técnicas:**
1. El médico psiquiatra firma con un nombre no listado en `PROFESIONALES_SALUD_MENTAL`
2. Las evoluciones psiquiátricas no contienen las keywords de `REGLAS_AREA_TEXTO["psiquiatria"]` (sustantivos, medicación, frases)
3. Las evoluciones psiquiátricas existen pero el parser no las segmenta como bloque separado (falta cabecera de fecha/hora o marcador de tipo)

**Implicancia:** El conteo de psiquiatría subestima la actividad real del área. No invalida las otras áreas.

### 4.3 Tasa/día anómala

| HC | Tasa | Interpretación |
|----|------|---------------|
| PAC-047 | 0.25/día | Muy baja: 18 int en 73 días. El raw tiene solo 23 bloques — posible exportación parcial de VADIGU o período de baja actividad documentada. |
| PAC-048/050 | 3.20/día | Alta pero HC corta (5 días): esperable en internación aguda con registro diario. |
| PAC-046 | 2.85/día | Alta pero internación activa con equipo completo (206 días): plausible. |

### 4.4 Dominancia de enfermería

Todos los HC tienen enfermería entre 56% y 72%. Es un patrón sistemático del formato VADIGU: las notas de turno de enfermería tienen cabecera explícita y se segmentan bien. Las evoluciones de otros profesionales a veces carecen de cabecera, quedando sin marcador de tipo y siendo descartadas por `NO_CUENTA:sin_marcador`.

**Este es el principal factor de sesgo del sistema actual.**

### 4.5 HC con pocos registros

**PAC-047** es la HC con menor densidad absoluta: 18 intervenciones en 73 días (23 bloques raw). Para comparación, PAC-046 tiene 680 raw en 206 días. La diferencia de 29x en densidad no se explica solo por diferencia de días — sugiere que el archivo exportado de VADIGU para PAC-047 puede estar incompleto.

### 4.6 Duplicado en dataset

PAC-050 (`Cronológico del paciente (7)(1).xls`) es copia renombrada del mismo archivo de PAC-048. Resultados idénticos en áreas, tipos, días, variables clínicas y texto crudo. Debe excluirse del análisis poblacional para no contar al mismo paciente dos veces.

---

## 5. Resumen cuantitativo del dataset válido (4 pacientes únicos)

| Métrica | Valor |
|---------|-------|
| Pacientes únicos | 4 |
| Total candidatos raw | 1.444 |
| Total descartados | 213 (14.7%) |
| **Total intervenciones válidas** | **1.231** |
| Días totales de internación | 905 |
| Intervenciones / día (global) | 1.36 |
| Intervenciones / paciente (promedio) | 307.8 |
| ICs efectivas totales | 3 |
| Registros stale excluidos | 1 (PAC-015) |
| Archivos no procesables | 1 (`Cronológico_paciente_5.xls`) |
| Duplicados en BD | 1 (PAC-050 = PAC-048) |

**Desglose global por área (4 pacientes únicos):**

| Área | N | % |
|------|---|---|
| Enfermería | 854 | 69.4% |
| Psicología | 205 | 16.7% |
| Terapia Ocupacional | 138 | 11.2% |
| Trabajo Social | 19 | 1.5% |
| Psiquiatría | 4 | 0.3% |
| Acomp. Terapéutico | 4 | 0.3% |
| Otros | 7 | 0.6% |

---

## 6. Conclusiones de validación

### Lo que funciona correctamente

- El parser segmenta bloques de notas de enfermería con alta fidelidad (cabecera `dd/mm/yyyy - HH:MM hs` + marcador de tipo).
- El criterio de conteo elimina duplicados exactos y bloques cortos de forma fiable.
- La deduplicación de BD y el filtro stale funcionan como se espera.
- La detección de variables clínicas es coherente con la complejidad documentada de los casos.

### Limitaciones identificadas

1. **Psiquiatría sistémicamente subestimada.** El clasificador híbrido no captura evoluciones psiquiátricas sin firma explícita del médico. El diccionario de profesionales (`PROFESIONALES_SALUD_MENTAL["psiquiatria"]`) puede estar incompleto para estos archivos.

2. **PAC-047 con densidad muy baja.** 18 intervenciones en 73 días es inconsistente con el volumen de los otros HC. Verificar si el archivo exportado de VADIGU está completo.

3. **Dominancia de enfermería (patrón estructural).** No es un error del clasificador sino un reflejo de cómo VADIGU estructura el HC: las notas de enfermería tienen formato estándar mientras que las evoluciones de otros profesionales varían. El 69.4% de enfermería refleja el registro, no necesariamente la carga asistencial real.

4. **PAC-049 sin interconsultas en 621 días.** Clínicamente improbable. Las ICs pueden estar en el texto pero sin las frases clave de `REGLAS_IC` o `SERVICIOS_EXTERNOS`, o el archivo puede estar incompleto para ese período.

5. **Tipos de intervención reducidos a 4.** El sistema detecta solo los tipos con marcador explícito en cabecera. Bloques sin marcador (ej. evolución psiquiátrica sin título) se clasifican por área pero no tienen tipo asignado.

### Recomendaciones para próxima iteración (sin modificar código ahora)

- Verificar con el equipo clínico si los profesionales psiquiatras de PAC-048 y PAC-049 están en el diccionario.
- Confirmar si el archivo de PAC-047 está completo o si falta parte del período de internación.
- Solicitar re-exportación de PAC-049 desde VADIGU para confirmar completitud del período.
- Eliminar PAC-050 de la BD con `/hcd/reportes/duplicados` si se confirma que es copia de PAC-048.

---

*Documento generado automáticamente a partir de los datos de `hcs.db`. No contiene datos de identificación de pacientes.*
