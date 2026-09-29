"""Privacy boundary after parsing and clinical filtering; preserves equality keys."""
import re
import pandas as pd
from pipeline.pseudonimizacion import pseudonymize_identifier


def stable_id(value, prefix):
    current = str(value or '').strip()
    if re.fullmatch(prefix + r'-[A-F0-9]{8}', current):
        return current
    return pseudonymize_identifier(current, prefix=prefix)


def protect_census(frame):
    result = frame.copy()
    for column, prefix in [('Documento', 'PAC'), ('codigoHC', 'HC')]:
        if column in result:
            result[column] = result[column].map(lambda x: stable_id(x, prefix) if pd.notna(x) and str(x).strip() else '')
    if '_archivo' in result:
        result['_archivo'] = result['_archivo'].map(lambda x: stable_id(x, 'DOC'))
    # Unknown export columns can contain names, contacts or insurance identifiers.
    allowed = ['Cama', 'Estado', 'Area', 'Edad', 'Documento', 'codigoHC', 'Ingreso', 'Estada', 'tipo_cama', '_archivo']
    return result[[c for c in allowed if c in result]].copy()
