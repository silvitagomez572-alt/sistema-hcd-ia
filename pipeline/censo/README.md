# Módulo Censo Mensual

Lee archivos de censo diario exportados desde **VADIGU** (CSV, Excel, HTML, PDF), filtra las camas ocupadas del servicio de Salud Mental y consolida un DataFrame único por paciente (`codigoHC`).

## Estructura esperada

El archivo de censo debe contener estas columnas (con tolerancia a variantes de mayúsculas):

| Columna    | Descripción                          |
|------------|--------------------------------------|
| Cama       | Número o identificador de cama       |
| Estado     | `Ocupada` / `Libre`                  |
| Area       | Servicio (ej. `Salud Mental`)        |
| Paciente   | Nombre del paciente                  |
| Edad       | Edad en años                         |
| Documento  | DNI u otro documento                 |
| codigoHC   | Código de historia clínica (clave)   |
| Ingreso    | Fecha de ingreso (`dd/mm/yyyy`)      |
| Estada     | Días de internación                  |

## Formatos soportados

| Formato | Notas |
|---------|-------|
| `.csv`  | Separador `,` `;` o `\t`; encodings UTF-8 y latin-1 |
| `.xlsx` | Excel estándar |
| `.xls`  | VADIGU exporta HTML disfrazado de XLS — se parsea con BeautifulSoup |
| `.html` | Tabla HTML directa |
| `.pdf`  | Extracción de texto con pypdf; requiere que el PDF no sea imagen |

## Uso básico

```python
from pipeline.censo.modulo_censo_mensual import consolidar_mes, resumen_mensual

# Consolidar todos los censos de mayo
df = consolidar_mes("data/censos/mayo_2025/")

# Ver métricas
print(resumen_mensual(df))
# {'total_pacientes': 18, 'camas_ocupadas': 18, 'edad_promedio': 42.3, 'archivos_procesados': 22}

# Exportar
df.to_csv("censo_salud_mental_mayo.csv", index=False)
```

## Funciones principales

### `leer_archivo_censo(ruta)`
Lee un único archivo y devuelve un DataFrame crudo con columnas normalizadas.

### `filtrar_salud_mental(df)`
Filtra filas donde `Estado == "Ocupada"` y `Area == "Salud Mental"` (insensible a mayúsculas).

### `consolidar_mes(directorio, patron="*")`
Procesa todos los archivos del directorio, descarta duplicados y devuelve un DataFrame con **una fila por `codigoHC`** (el registro más reciente del mes).

### `resumen_mensual(df)`
Devuelve un dict con métricas básicas: total de pacientes, camas ocupadas, edad promedio y cantidad de archivos procesados.

## Dependencias

```
pandas
beautifulsoup4
pypdf
openpyxl
xlrd
lxml
```
