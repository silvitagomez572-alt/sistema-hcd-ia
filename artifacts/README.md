# artifacts/

Artefactos del pipeline: modelos serializados, métricas de entrenamiento y salidas validadas.

## Contenido actual

| Artefacto | Ubicación real | Descripción |
|-----------|---------------|-------------|
| `modelo_area_intervenciones.pkl` | `/` (raíz del proyecto) | Clasificador NLP entrenado — TF-IDF + Logistic Regression (accuracy 92.98%) |
| `validacion_manual_hc_corta.csv` | `outputs/` | Validación manual bloque a bloque de PAC-048 |

> Los archivos se mantienen en su ubicación original para no romper los imports del pipeline.
> En una refactorización futura, `modelo_area_intervenciones.pkl` puede moverse aquí y actualizar la ruta en `api/main.py`.

## Métricas del clasificador

- Algoritmo: Logistic Regression sobre TF-IDF (unigrams + bigrams)
- Accuracy en test: 92.98%
- Clases: enfermeria, psicologia, psiquiatria, terapia_ocupacional, trabajo_social, acompanante_terapeutico, otros
- Entrenado con bloques reales del dataset HCD (4 pacientes, 1.444 bloques raw)
