# Privacidad y límites de la entrega

El repositorio de entrega no incluye historias clínicas, bases SQLite, uploads, modelos entrenados ni diccionario institucional de profesionales. Los informes por paciente y el JSON maestro históricos se conservan en la máquina y se excluyen de la nueva versión pública. El historial previo permanece; no se declara eliminación retrospectiva.

Las pruebas usan fixtures sintéticas y bases temporales. No se ejecutaron borrados ni migraciones sobre datos existentes. El repositorio guarda evidencia de pruebas de software y del benchmark sintético, no texto clínico real.

La API limita el tamaño de solicitudes antes de parsear multipart, rechaza rutas no válidas, separa corpus documental aprobado de uploads clínicos y devuelve errores genéricos. Los logs de aplicación incluyen timestamp/nivel/módulo/operación/request ID/estado, sin cuerpos ni parámetros. Iniciar Uvicorn con `--no-access-log`. Las respuestas tienen `Cache-Control: no-store`.

Los reportes NLP nuevos conservan métricas y referencias pseudónimas, no nombres originales de archivo ni narrativa clínica. La pseudonimización de texto devuelve únicamente el texto transformado y cantidad de reemplazos, sin original ni mapa. Sin embargo, regex no reconoce todas las entidades: nombres sin etiqueta, direcciones y cuasiidentificadores pueden escapar. No afirmar anonimización completa ni permitir publicación automática de texto transformado. El original puede existir en memoria de sesión o archivos institucionales; aplicar control de acceso y retención.

`codigoHC` permanece en memoria mientras el parser lo necesita para reconstruir Documento y deduplicar. Las claves se pseudonimizan al persistir/intercambiar; la equivalencia de deduplicación se verifica con fixtures. Se conserva el esquema SQLite y no se migra el histórico. Las bases históricas pueden contener identificadores y deben mantenerse privadas.

El salt público heredado y los hashes truncados siguen siendo limitaciones. Configurar un salt privado para instalaciones nuevas y conservar el valor institucional durante traslados; cambiarlo sobre datos existentes requiere migración y conciliación, no sustitución improvisada.

La API usa autenticación Basic opcional y restringe a loopback si falta contraseña. Docker exige contraseña y publica en loopback. Streamlit requiere control de acceso independiente antes de uso en red. Para un hospital faltan identidad institucional, roles, TLS, auditoría durable, cifrado, backup/restore operativo, revisión de amenazas y aprobación clínica/legal institucional.

El contexto Docker usa una lista de inclusión y no copia bases, `.env`, `.local`, reportes por paciente ni modelos. RAG solo acepta bytes de protocolos revisados presentes en un manifiesto SHA-256; esto evita indexación de una HC arbitraria, pero cada incorporación de corpus requiere revisión humana. Un directorio nuevo de índice evita mezclar cargas heredadas, que no se borran.
