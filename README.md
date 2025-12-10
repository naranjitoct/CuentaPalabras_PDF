# PASOS A SEGUIR PARA COMPILAR Y EJECUTAR

1 - Crear un enviroNment
2 - Activarlo (CONDA ACTIVATE)
3 - Instalar los requerimientos (librerías): pip install -r requirements.txt pyinstaller

4 - Crear un ejecutable: 
pyinstaller --onefile --name contar_palabras_pdf contar_palabras_pdf.py


5- Ejecutar con : contar_palabras_pdf.exe -w listado_palabras.xlsx -d "C:\ruta\pdfs" -o salida.csv --recursive


# Opciones útiles:
--substrings → cuenta subcadenas (ej. “plan” dentro de “planificación”).
--keep-accents → no normaliza acentos.
--recursive → busca PDFs en subcarpetas.
-- La búsqueda de palabra completa ahora también considera raíces flexionadas
   (stemming) para encontrar términos relacionados morfológicamente.


# EJEMLPLOS USO ESPAÑOL
python contar_palabras_pdf.py \
  --words palabras_es.xlsx \
  --pdf_dir docs \
  --output salida_es.csv

# EJEMPLOS USO INGLÉS
  python contar_palabras_pdf.py \
  --words words_en.csv \
  --pdf_dir reports \
  --output salida_en.csv --recursive

# EJEMPLO MIXTO
  python contar_palabras_pdf.py -w palabras_mixtas.csv -d docs -o salida_mixta.csv