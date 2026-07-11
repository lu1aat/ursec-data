---
name: resumen-actualizacion
description: Genera el resumen de la última descarga de URSEC y lo agrega al historial de actualizaciones del sitio (docs/index.html). Correr SIEMPRE después de python3 downloader.py, antes de comitear. También aplica si el usuario pide "generar el resumen de actualización", "actualizar el historial" o similar.
---

# Resumen de actualización

Este skill arma el resumen en español de los archivos nuevos que trajo la
última corrida de `downloader.py` (los que aparecen como diff sin comitear
en `db/files.csv`) y lo publica en el botón "Historial de actualizaciones"
del sitio.

No hay forma de generar un buen resumen en español de resoluciones/planillas
de forma determinística — por eso este paso lo hace el agente leyendo el
texto extraído, no un script.

## Pasos

1. **Metadata de archivos nuevos.** Correr:
   ```bash
   python3 extract_text.py --new-meta
   ```
   Devuelve un JSON con `url, filename, title, date_published, category,
   source, size_str, ext, local_path` de cada archivo agregado a
   `db/files.csv` desde el último commit. Si la lista está vacía, avisar
   al usuario que no hay archivos nuevos y parar acá.

2. **Texto extraído.** Correr:
   ```bash
   python3 extract_text.py --new-text
   ```
   Imprime, para cada archivo nuevo, su título/categoría/fecha/URL seguido
   del texto extraído (PDF/DOCX/ODT: texto narrativo; XLSX/ODS: nombres de
   hoja y encabezados de columna, porque son datos tabulares, no texto). El
   texto largo viene truncado a ~6000 caracteres por archivo — alcanza para
   entender de qué trata cada documento.

3. **Escribir el resumen general.** Leé el texto del paso 2 y redactá un
   resumen en español, 3-6 oraciones, en prosa (no bullet list), que cubra:
   - Cuántos archivos nuevos y de qué tipo (resoluciones, planillas, etc.)
   - Los temas/categorías más relevantes
   - Cualquier resolución con impacto notorio (sanciones, licencias,
     medidas cautelares, normativa nueva) mencionada por número y motivo
   - Qué actualizan las planillas XLSX/ODS si las hay (ej. "actualiza el
     padrón de medios registrados")

   Tono neutro, como un boletín interno. No inventes datos que no estén en
   el texto extraído. Este es el texto que se ve primero, colapsado, en el
   historial — tiene que dar la idea completa sin abrir nada más.

4. **Escribir un resumen por documento.** Además del resumen general,
   redactá para cada archivo nuevo un `summary` propio de 1-3 oraciones
   (más detallado que el general, es lo que se ve al expandir "Ver
   archivos"). Para PDF/DOCX/ODT: qué resuelve/dispone el documento en
   concreto — número de expediente si es relevante, a quién afecta, motivo,
   resultado (multa, autorización, denegación, etc.), citando lo que
   efectivamente dice el texto extraído. Para XLSX/ODS: qué contiene la
   planilla (qué hojas tiene, cuántas filas, qué representan las columnas
   principales) en vez de repetir el resumen general. No copiar el resumen
   general en cada archivo — cada `summary` de archivo debe aportar detalle
   que el general no tiene.

5. **Guardar el registro.** Crear `db/updates/YYYY-MM-DD.json` (la fecha es
   la de hoy, la de la corrida — no `date_published` de los archivos) con
   esta forma exacta:
   ```json
   {
     "date": "YYYY-MM-DD",
     "count": <número de archivos nuevos>,
     "summary": "<el resumen general del paso 3>",
     "files": [
       {
         "url": "...", "filename": "...", "title": "...",
         "category": "...", "ext": "pdf",
         "summary": "<el resumen por documento del paso 4>"
       }
     ]
   }
   ```
   `files` sale de la salida de `--new-meta` más el campo `summary` que
   agregaste en el paso 4 (podés omitir `date_published`, `source`,
   `size_str`, `local_path` — el sitio los ignora si quedan).

6. **Regenerar el sitio.**
   ```bash
   python3 web.py
   ```
   Esto lee todo `db/updates/*.json` (incluido el nuevo) y lo inyecta en
   `docs/index.html`.

7. **Confirmar al usuario** cuántos archivos se resumieron y en qué fecha,
   y recordarle que falta comitear (`db/files.csv`, `db/visited_pages.txt`,
   `db/updates/YYYY-MM-DD.json`, `docs/index.html`). No comitear sin que lo
   pida explícitamente.

## Notas

- Si `extract_text.py --new-meta` tira `[]` pero `git status` muestra
  cambios en `db/files.csv`, puede ser que ya se haya comiteado la
  descarga — el script tiene un fallback que compara `HEAD` contra
  `HEAD~1` en ese caso, así que igual debería encontrar los archivos del
  último commit de descarga.
- Los tipos de archivo soportados para extracción son PDF, DOCX, ODT
  (texto narrativo) y XLSX, ODS (metadata de hojas/columnas). Cualquier
  otro tipo devuelve "(tipo de archivo no soportado)" — mencionalo en el
  resumen igual, con el nombre del archivo.
