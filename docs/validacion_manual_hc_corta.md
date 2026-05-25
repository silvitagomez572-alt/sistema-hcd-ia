# Validación manual — HC corta (PAC-048)

**Fecha de validación:** 2026-05-25
**HC usada:** `Cronológico del paciente (7).xls` (id=48)
**Criterio de selección:** HC más corta del dataset, 🟢 Consistente, sin artefacto temporal.
**Período de internación:** 12/05/2026 – 15/05/2026 (5 días)
**Contexto clínico conocido:** internación por intento de suicidio, egreso con alta médica al 5º día.

---

## 1. Confirmación de estado estable antes de la validación

| Métrica | Valor confirmado |
|---------|-----------------|
| Pacientes válidos en BD | 4 |
| Total intervenciones | 1.231 |
| PAC-050 | Eliminado (duplicado real confirmado) |
| PAC-015 | Mantenido como stale por trazabilidad |
| Semáforo: criterios congelados | ✅ psiquiatría=0 y enfermería>65% NO son inconsistencia |

---

## 2. Resumen de procesamiento del HC

| Métrica | Valor |
|---------|-------|
| Total candidatos raw (bloques parseados) | 17 |
| Descartados | 1 |
| **Intervenciones válidas** | **16** |
| Días de internación | 5 |
| Tasa intervenciones / día | 3.20 |
| Reingresos | 0 |
| Cambios de cama | 1 |
| ICs detectadas | 0 |

**Distribución por área:**

| Área | N | % |
|------|---|---|
| Enfermería | 9 | 56.2% |
| Psicología | 6 | 37.5% |
| Terapia Ocupacional | 1 | 6.2% |
| Psiquiatría | 0 | 0.0% |

**Variables clínicas detectadas:** ideación autolítica · estado estable · crisis

---

## 3. Tabla de validación bloque por bloque

| Nro | Fecha | Hora | Tipo de bloque | Texto resumido | Área | Regla | Cuenta | IC | Variable clínica | Observación |
|-----|-------|------|----------------|----------------|------|-------|--------|-----|-----------------|-------------|
| 1 | 12-05-2026 | 18:58 | Motivo de consulta | INTENTO DE SUICIDIO AMB SAME | terapia_ocupacional | regla_texto:to | **no** | no | crisis | Motivo de consulta: no es marcador CUENTA. Texto contiene "to" → clasificado TO, pero es la entrada del ingreso |
| 2 | 12-05-2026 | 21:40 | Nota de enfermería | Paciente tranquila ingresa DEM con DX ideación | enfermeria | diccionario_profesional:AYOSA | sí | no | ideación autolítica, estado estable | Primera nota de turno post-ingreso |
| 3 | 12-05-2026 | 23:26 | Nota de enfermería | HORA T/A Tº FC FR SAT02 22.30 100/60 | psicologia | diccionario_profesional:BARRIONUEVO CABUR | sí | no | — | Texto es nota con SVN — clasificado psicología por firma del profesional. Texto no indica atención psicológica |
| 4 | 13-05-2026 | 05:59 | Nota de enfermería | Paciente vigil, lucida, tranquila. Fue controlada | psicologia | diccionario_profesional:BARRIONUEVO CABUR | sí | no | estado estable | Ídem anterior: firma BARRIONUEVO → psicología, pero el texto es control de turno |
| 5 | 13-05-2026 | 09:31 | Nota de enfermería | HORA T/A Tº FC FR SAT02 09:00 100/60 | psicologia | diccionario_profesional:ROMERO, CLELIA | sí | no | — | Signos vitales escritos por ROMERO (psicología según diccionario) |
| 6 | 13-05-2026 | 14:05 | Nota de enfermería | pte que se encuentra en crisis pide abordaje | psicologia | diccionario_profesional:ROMERO, CLELIA | sí | no | crisis | Abordaje psicológico real — texto y firma coinciden |
| 7 | 13-05-2026 | 20:09 | Nota de enfermería | HORA T/A Tº FC FR SAT02 16:00 110/80 | enfermeria | regla_texto:nota de enfermería | sí | no | — | Control de SVN nocturno de enfermería |
| 8 | 13-05-2026 | 21:04 | Nota de enfermería | PTE TRANQUILA CONTROLADA MEDICADA VIA ORAL | terapia_ocupacional | regla_texto:to | sí | no | estado estable | Clasificado TO por keyword "to " — probable abreviatura de "turno" o "toda la noche", no intervención de TO real |
| 9 | 14-05-2026 | 01:21 | Nota de enfermería | HORA T/A Tº FC FR SAT02 23.00 110/60 | enfermeria | regla_texto:nota de enfermería | sí | no | — | SVN madrugada |
| 10 | 14-05-2026 | 05:46 | Nota de enfermería | PACIENTE TRANQUILA MEDICADA ATB MAS ANALGESICO | enfermeria | regla_texto:nota de enfermería | sí | no | — | Medicación + antibiótico + analgésico — indica manejo de heridas |
| 11 | 14-05-2026 | 06:39 | Evolución clínica | Pte vigil, otep, animo depresivo, se... | psicologia | diccionario_profesional:CARRIZO, SONIA | sí | no | — | Primera evolución psicológica explícita (ánimo depresivo) |
| 12 | 14-05-2026 | 12:28 | Nota de enfermería | Se realizo curacion plana y oclusion de heridas | enfermeria | regla_texto:nota de enfermería | sí | no | — | Curación de heridas por intento de suicidio — intervención técnica de enfermería |
| 13 | 14-05-2026 | 21:38 | Nota de enfermería | Paciente tranquila con medicacion vo realizada | enfermeria | diccionario_profesional:AYOSA | sí | no | estado estable | Medicación VO — turno noche |
| 14 | 14-05-2026 | 23:43 | Nota de enfermería | HORA T/A Tº FC FR SAT02 23.00 110/60 | enfermeria | regla_texto:nota de enfermería | sí | no | — | SVN noche |
| 15 | 15-05-2026 | 05:20 | Nota de enfermería | PTE TRANQUILA, CONTROLADA SVN, MEDICADA CON ATB | enfermeria | regla_texto:nota de enfermería | sí | no | estado estable | Mantenimiento ATB — madrugada antes del alta |
| 16 | 15-05-2026 | 11:10 | Evolución clínica | Pte vigil, otep, animo estable. En co... | psicologia | diccionario_profesional:CARRIZO, SONIA | sí | no | estado estable | Evolución psicológica de alta: ánimo estable, continuidad ambulatoria |
| 17 | 15-05-2026 | 13:04 | Nota de enfermería | De alta medica. Profesional: BARRIOS, JORGE | enfermeria | regla_texto:nota de enfermería | sí | no | — | Registro de alta médica al día 5 |

---

## 4. Análisis del único bloque descartado

**Bloque 1 — Motivo de consulta (18:58 hs. del día 1)**

- Texto: `INTENTO DE SUICIDIO AMB SAME Internación - Hospital...`
- Por qué no cuenta: `"Motivo de consulta"` no está en `REGLAS_CONTEO["CUENTA"]`
- Observación clínica: este bloque documenta el motivo de ingreso, no una intervención terapéutica. El criterio es correcto: el motivo de consulta es el evento que origina la internación, no una intervención del equipo.
- Clasificado como `terapia_ocupacional` por keyword `"to "` en el texto ("internación" contiene "to"). **Falso positivo del clasificador de área** — aunque el bloque no cuenta, la clasificación es incorrecta.

---

## 5. Observaciones manuales por categoría

### Clasificaciones correctas (sin objeción)

- Bloques 2, 7, 9, 10, 12, 13, 14, 15, 17: enfermería por regla de texto o diccionario. Texto consistente con notas de turno y procedimientos.
- Bloques 11 y 16: psicología por firma CARRIZO. Texto explícitamente psicológico (ánimo, evolución clínica). ✅ Correcto.
- Bloque 6: psicología por firma ROMERO. Texto documenta crisis y pedido de abordaje. ✅ Correcto.

### Clasificaciones que requieren revisión metodológica

| Bloque | Área asignada | Observación |
|--------|---------------|-------------|
| 3 | psicología | Texto es registro de SVN (100/60 36 FC FR SAT02). El profesional firmante (BARRIONUEVO CABUR) está en el diccionario como psicología. El texto NO refleja una intervención psicológica. |
| 4 | psicología | Ídem bloque 3. Texto: "Paciente vigil, lucida, tranquila. Fue controlada." Control de turno de enfermería. |
| 5 | psicología | Texto: signos vitales. Firma ROMERO → psicología. No hay contenido psicológico. |
| 8 | terapia_ocupacional | Texto: "PTE TRANQUILA CONTROLADA MEDICADA VIA ORAL, SE LA CONTROLA TODO". La keyword "to " aparece en "todo". **Falso positivo** de la capa 2 del clasificador. |

**Implicancia:** de las 6 intervenciones clasificadas como psicología, al menos 3 (bloques 3, 4, 5) son notas de control firmadas por un profesional del área pero con contenido de enfermería. La clasificación está técnicamente justificada (diccionario de profesionales) pero sobreestima la actividad psicológica visible en el texto.

### Ausencia de psiquiatría — análisis

El alta médica la registra "BARRIOS, JORGE ANTONIO" (bloque 17). No está en `PROFESIONALES_SALUD_MENTAL["psiquiatria"]`. El texto de alta no contiene keywords de psiquiatría. El médico psiquiatra que firmó el alta no es reconocido por el clasificador.

---

## 6. Alertas (criterios congelados)

| Criterio | Resultado | Semáforo |
|----------|-----------|----------|
| Stale o duplicado real | No | — |
| Tasa < 0.3/día con días > 30 | No aplica (tasa=3.2, días=5) | — |
| Internación > 365 días | No | — |
| **Estado final** | Sin alertas | 🟢 Consistente |

---

## 7. Limitaciones identificadas en este HC

**L1 — Keyword "to " genera falso positivo en TO**
El bloque 8 se clasifica como `terapia_ocupacional` por la substring "to " en "todo". La 'keyword es demasiado corta y captura abreviaturas genéricas del español ("todo", "turno", etc.). Presente también en bloque 1 (no cuenta).

**L2 — Profesionales con múltiples roles**
BARRIONUEVO CABUR y ROMERO están registrados como `psicologia` en el diccionario, pero en este HC escriben notas con contenido de control clínico (SVN, estado general). El diccionario asigna el área por firma, no por contenido: es correcto metodológicamente pero genera una imagen de carga psicológica mayor a la real en el texto.

**L3 — Alta médica sin clasificación psiquiátrica**
El médico firmante del alta no está en el diccionario. Su bloque se clasifica por texto (contiene "nota de enfermería") → enfermería. La actividad psiquiátrica de cierre no queda registrada en el conteo.

**L4 — ICs ausentes pese a tratamiento con ATB**
Los bloques 10 y 15 mencionan "ATB MAS ANALGESICO". El tratamiento antibiótico en un ingreso por intento de suicidio puede indicar una IC con infectología o clínica médica, pero no está documentado con las frases de `REGLAS_IC` ni los servicios de `SERVICIOS_EXTERNOS`.

---

## 8. Tabla resumen para entrega

| Campo | Valor |
|-------|-------|
| HC | PAC-048 (`Cronológico del paciente (7).xls`) |
| Período | 12/05/2026 – 15/05/2026 (5 días) |
| Contexto clínico | Internación por intento de suicidio; alta médica al 5º día |
| Candidatos raw | 17 |
| Descartados | 1 |
| Intervenciones válidas | 16 |
| Tasa | 3.20 int/día |
| Distribución | Enf 56.2% · Psic 37.5% · TO 6.2% · Psiq 0% |
| ICs | 0 detectadas |
| Variables clínicas | ideación autolítica · estado estable · crisis |
| Semáforo | 🟢 Consistente |
| Alertas activas | ninguna |
| Clasificaciones a revisar | 3 bloques (3, 4, 5): psicología por firma con contenido de enfermería |
| Falsos positivos confirmados | 1 (bloque 8: TO por keyword "to " en "todo") |

---

*Tabla detallada exportada en `outputs/validacion_manual_hc_corta.csv`*
*Documento de validación — sin datos de identificación de pacientes.*
