# Fórmulas estadísticas — Módulo Censo Mensual

**Sistema HCD IA — Salud Mental**
Última actualización: 2026-05-28

Este documento describe las cuatro métricas estadísticas calculadas por el módulo Censo Mensual, con la fórmula matemática, la implementación exacta sobre los datos VADIGU y las limitaciones conocidas que requieren validación clínica.

---

## 1. Internados únicos del mes

### Fórmula

$$n = |\{p_i : p_i \in \text{SM}, \text{Estado} = \text{Ocupada}, \text{Cama} \notin \text{Transitorias}\}|$$

donde el conjunto se deduplica primero por `codigoHC` (manteniendo el registro más reciente) y luego por `Documento` (DNI), conservando el de mayor estada.

### Cálculo con datos VADIGU

1. Se leen todos los archivos del mes (CSV / Excel / HTML / PDF exportados de VADIGU).
2. Se filtran las filas con `Estado = "Ocupada"` y `Area = "Salud Mental"`.
3. Se excluyen las camas transitorias `53 A` y `53 B` (trasplantados), que no pertenecen al servicio.
4. Se deduplica por `codigoHC` conservando el último registro por `Ingreso` — un paciente puede aparecer en múltiples archivos diarios.
5. Se deduplica por `Documento` (DNI) conservando el registro con mayor `Estada` — VADIGU puede asignar dos `codigoHC` distintos al mismo paciente en reingresos del mismo mes.
6. El resultado `n` es la cantidad de filas del DataFrame consolidado final.

```python
# frontend/app.py — línea 99 / 152
_n_sm  = len(_df_cons2)   # vista Cargar Censos
_n_pac = len(_df_censo)   # vista Estadísticas (mismo DataFrame)
```

### Pendiente de validación

- **Reingresos dentro del mes:** si un paciente egresa y reingresa en el mismo mes con DNI distinto o DNI ausente en VADIGU, puede contarse dos veces. Verificar manualmente cuando `_n_pac` supere el número esperado de camas.
- **Camas prestadas de otro servicio:** los pacientes en camas `"Prestada de otro servicio"` se incluyen en el conteo. Confirmar con el servicio si deben contarse como internados propios.
- **Calidad del campo `Documento`:** si VADIGU exporta el DNI en blanco para algunos registros, la deduplicación cae a `codigoHC` únicamente, con riesgo de doble conteo.

---

## 2. Porcentaje de ocupación SM

### Fórmula

$$\%\text{Ocu} = \frac{\overline{C_{\text{fijas ocu}}}}{C_{\text{total}}} \times 100$$

donde $\overline{C_{\text{fijas ocu}}}$ es la media aritmética de camas fijas SM ocupadas en los días del mes, y $C_{\text{total}} = 18$ (constante institucional `TOTAL_CAMAS_FIJAS`).

### Cálculo con datos VADIGU

Para cada archivo (día) se calcula la cantidad de camas de `CAMAS_FIJAS_SM` con `Estado = "Ocupada"`. El porcentaje del mes es el promedio de esos valores diarios dividido por 18.

```python
# pipeline/censo/modulo_censo_mensual.py — stats_servicio_sm()
mask_fijas = df["Cama"].apply(lambda c: str(c).strip() in CAMAS_FIJAS_SM)
mask_ocu   = df["Estado"].map(_normalizar) == ESTADO_OCUPADA
ocupadas_fijas = int((mask_fijas & mask_ocu).sum())

# frontend/app.py — línea 156
_porc_ocu = round(100 * _df_st2["Ocupadas"].mean() / TOTAL_CAMAS_FIJAS, 1)
```

`CAMAS_FIJAS_SM` = 19 camas listadas (50 A, 51 A, 51 B, 52A, 52B, 63 A–B, 66 A–B, 68 A–B, 69 A–B, 70 A–B, 71 A–B, 72 A–B).
`TOTAL_CAMAS_FIJAS` = 18 (denominador institucional acordado).

### Pendiente de validación

- **Discrepancia lista vs. denominador:** `CAMAS_FIJAS_SM` contiene 19 identificadores pero `TOTAL_CAMAS_FIJAS = 18`. Confirmar con el servicio cuál es el total oficial y si alguna cama de la lista está temporalmente fuera de servicio.
- **Archivos faltantes:** si no se cargan todos los días del mes, la media diaria subestima la ocupación real. El denominador temporal correcto sería la cantidad de días con archivo, no el mes completo.
- **Sensibilidad al horario de exportación:** VADIGU toma la foto del estado en el momento de la exportación. Un censo de madrugada puede mostrar menos camas ocupadas que uno exportado al mediodía.

---

## 3. Promedio de estada

### Fórmula

$$\bar{E} = \frac{1}{n} \sum_{i=1}^{n} E_i$$

donde $E_i$ es la estada en días del paciente $i$ según el campo `Estada` de VADIGU, y $n$ es el número de pacientes únicos con estada numérica válida.

### Cálculo con datos VADIGU

```python
# frontend/app.py — líneas 159–162
_estada_num = pd.to_numeric(_df_censo["Estada"], errors="coerce").dropna()
_prom_estada = round(float(_estada_num.mean()), 1)
```

El campo `Estada` de VADIGU representa la cantidad de días transcurridos desde el ingreso hasta la fecha del archivo. En pacientes que aparecen en múltiples archivos, se conserva el valor más alto (el del día más reciente del mes en que ese paciente fue observado). Los valores no numéricos se descartan con `errors="coerce"`.

### Pendiente de validación

- **Estada ≠ internación del mes:** el campo refleja días totales desde el ingreso, no los días que el paciente estuvo internado durante el mes en cuestión. Un paciente con 200 días de internación previa infla el promedio sin representar una estadía mensual.
- **Pacientes con alta en el mes:** si el paciente egresa antes del último archivo del mes, su estada quedará congelada en el valor del último censo en que apareció, potencialmente subestimada.
- **Valores 0 o negativos:** pueden aparecer por errores de exportación en VADIGU. Validar que no haya estadas = 0 en el dataset antes de interpretar el promedio.

---

## 4. Giro de camas

### Fórmula

$$G = \frac{n}{C_{\text{pico}}}$$

donde $n$ es el total de pacientes únicos del mes y $C_{\text{pico}}$ es el valor máximo de camas fijas SM ocupadas registrado en cualquier día del mes.

### Cálculo con datos VADIGU

```python
# frontend/app.py — líneas 165–166
_giro = round(_n_pac / _df_st2["Ocupadas"].max(), 2)
```

`_df_st2["Ocupadas"].max()` es el pico de camas fijas SM ocupadas en el período cargado. `_n_pac` es el total de pacientes únicos (ver fórmula 1).

### Pendiente de validación

- **Definición epidemiológica estándar:** el giro de camas clásico se define como `egresos / camas disponibles`, no como `pacientes únicos / pico de ocupación`. La fórmula actual es una aproximación operativa que puede sobreestimar el giro si el pico no es representativo del mes.
- **Pico vs. promedio como denominador:** usar el pico diario como denominador es sensible a días atípicos (picos por traslados, feriados). Considerar usar el promedio de ocupación (fórmula 2) como denominador alternativo: $G' = n / \overline{C_{\text{fijas ocu}}}$.
- **Reingresos no capturados:** si la deduplicación por DNI unifica a un paciente que egresó y reingresó, el numerador subestima el número real de episodios de internación, lo que baja el giro artificialmente.

---

## Resumen comparativo

| Métrica | Fórmula resumida | Denominador | Fuente del dato |
|---|---|---|---|
| Internados únicos | $n$ = filas post-dedup | — | `codigoHC` + `Documento` VADIGU |
| % Ocupación SM | $\overline{C_{\text{ocu}}} / 18 \times 100$ | 18 (fijo institucional) | Columna `Cama` + `Estado` VADIGU |
| Promedio estada | $\sum E_i / n$ | $n$ pacientes válidos | Columna `Estada` VADIGU |
| Giro camas | $n / C_{\text{pico}}$ | Pico diario del mes | Columna `Ocupadas` (stats diarias) |

---

## Notas generales

- Todas las métricas se calculan sobre **camas fijas SM** (`CAMAS_FIJAS_SM`). Las camas `53 A` y `53 B` (trasplantados) se reportan por separado y no afectan ningún indicador.
- Los cálculos son automáticos y preliminares. Ninguna métrica reemplaza la auditoría manual del censo ni el informe estadístico oficial del servicio.
- El código fuente de referencia está en `frontend/app.py` (módulo Censo Mensual) y `pipeline/censo/modulo_censo_mensual.py`.
