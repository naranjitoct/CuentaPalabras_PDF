import csv
import re
import sys
from pathlib import Path
from typing import List, Dict
import unicodedata
import pandas as pd

# --- GUI ---
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ----------------- Utilidades -----------------

## unicodedata.normalize(form, unistr) https://docs.python.org/es/3.13/library/unicodedata.html
## Retorna la forma normalizada form para la cadena Unicode unistr. Los valores válidos para form son “NFC”, “NFKC”, “NFD” y “NFKD”.
## Fusilado parte de : https://www.bomberbot.com/python/python-replace-k-with-multiple-values-advanced-techniques-and-best-practices/

def normalize_text(s: str, remove_accents: bool = True) -> str:
    s = s.casefold() # Más robusto que lower (en otros idiomas principalmente...)
    if remove_accents:
        s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return s

def read_words(word_file: Path) -> List[str]:
    ext = word_file.suffix.lower()
    ## EXCEK O CSV ??
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(word_file, header=None)
    elif ext == ".csv":
        try:
            df = pd.read_csv(word_file, header=None, sep=None, engine="python")
        except Exception:
            df = pd.read_csv(word_file, header=None)
    else:
        raise ValueError(f"Formato no soportado: {word_file.name} (usa .xlsx, .xls o .csv)")
    
    series = df.iloc[:, 0].astype(str).str.strip()
    words = [w for w in series if w and w.lower() != "nan"] #Palabras en el listado
    
    #Voy guardando las ya vistas paara no repetirlas. Me quedo con dedup (limpia sin duplicados)
    seen, dedup = set(), []
    for w in words:
        if w not in seen:
            seen.add(w)
            dedup.append(w)
    return dedup

def pick_pdf_backend(): #Algunos archivos han dado error... intentamos leer con dos librerías.
    """
    Selecciona backend de PDF en runtime sin romper la UI:
    - Intenta pdfminer.six
    - Si falla, intenta pypdf
    - Devuelve ('pdfminer', extractor) o ('pypdf', extractor)
    - Si ninguno está, devuelve ('none', None)
    """
    try:
        from pdfminer.high_level import extract_text as pdf_extract_text
        return "pdfminer", pdf_extract_text
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        def _extract_with_pypdf(path_str: str) -> str:
            text_parts = []
            try:
                reader = PdfReader(path_str)
                for p in reader.pages:
                    try:
                        text_parts.append(p.extract_text() or "")
                    except Exception:
                        continue
            except Exception:
                return ""
            return "\n".join(text_parts)
        return "pypdf", _extract_with_pypdf
    except Exception:
        return "none", None

#Mejoras para tener resultados más óptimos y según opción de palabra/frase completa.
def compile_pattern(token: str, whole_word: bool) -> re.Pattern:
    escaped = re.escape(token)
    if whole_word:
        pattern = rf'(?<!\w){escaped}(?!\w)'
    else:
        pattern = escaped
    return re.compile(pattern, flags=re.UNICODE)

#Aquí sumamos los token que vamos encontrando...
def count_occurrences(text: str, patterns: Dict[str, re.Pattern]) -> Dict[str, int]:
    return {token: sum(1 for _ in pat.finditer(text)) for token, pat in patterns.items()}

# ----------------- Interfaz Tk -----------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Contar palabras en PDFs (by RSG)")
        self.geometry("720x440")
        self.minsize(680, 400)

        # Variables
        self.var_words = tk.StringVar()
        self.var_pdfdir = tk.StringVar()
        self.var_output = tk.StringVar(value=str(Path.cwd() / "resultado_conteos.csv"))
        self.var_substrings = tk.BooleanVar(value=False)
        self.var_keep_accents = tk.BooleanVar(value=False)  # False => normaliza
        self.var_recursive = tk.BooleanVar(value=False)

        # Progreso
        self.var_progress_text = tk.StringVar(value="Listo.")
        self.var_progress_count = tk.StringVar(value="")
        self.progress_value = tk.IntVar(value=0)
        self.progress_max = 100

        self.create_widgets()

    def create_widgets(self):
        pad = {'padx': 10, 'pady': 6}
        frame = ttk.Frame(self); frame.pack(fill="both", expand=True, **pad)

        # Archivo palabras
        ttk.Label(frame, text="Archivo de palabras (Excel/CSV):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.var_words).grid(row=1, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(frame, text="Examinar...", command=self.select_words_file).grid(row=1, column=2, sticky="we", **pad)

        # Carpeta PDFs
        ttk.Label(frame, text="Carpeta con PDFs:").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.var_pdfdir).grid(row=3, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(frame, text="Examinar...", command=self.select_pdf_dir).grid(row=3, column=2, sticky="we", **pad)

        # Archivo salida
        ttk.Label(frame, text="Archivo de salida (CSV):").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.var_output).grid(row=5, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(frame, text="Cambiar...", command=self.select_output_file).grid(row=5, column=2, sticky="we", **pad)

        # Opciones
        options = ttk.LabelFrame(frame, text="Opciones")
        options.grid(row=6, column=0, columnspan=3, sticky="we", **pad)
        ttk.Checkbutton(options, text="Contar subcadenas (no sólo palabra/frase completa)", variable=self.var_substrings).grid(row=0, column=0, sticky="w", padx=10, pady=4)
        ttk.Checkbutton(options, text="Mantener acentos (no normalizar)", variable=self.var_keep_accents).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        ttk.Checkbutton(options, text="Buscar recursivamente en subcarpetas", variable=self.var_recursive).grid(row=2, column=0, sticky="w", padx=10, pady=4)

        # Progreso
        prog = ttk.LabelFrame(frame, text="Progreso")
        prog.grid(row=7, column=0, columnspan=3, sticky="we", **pad)
        self.progress = ttk.Progressbar(prog, orient="horizontal", mode="determinate",
                                        maximum=self.progress_max, variable=self.progress_value)
        self.progress.grid(row=0, column=0, columnspan=3, sticky="we", padx=10, pady=6)
        ttk.Label(prog, textvariable=self.var_progress_text).grid(row=1, column=0, sticky="w", padx=10)
        ttk.Label(prog, textvariable=self.var_progress_count).grid(row=1, column=2, sticky="e", padx=10)

        # Botones
        ttk.Button(frame, text="Ejecutar conteo", command=self.on_run).grid(row=8, column=0, sticky="we", **pad)
        ttk.Button(frame, text="Salir", command=self.destroy).grid(row=8, column=2, sticky="we", **pad)

        frame.columnconfigure(0, weight=1)
        prog.columnconfigure(0, weight=1)

    def select_words_file(self):
        path = filedialog.askopenfilename(title="Selecciona Excel o CSV con palabras",
                                          filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")])
        if path: self.var_words.set(path)

    def select_pdf_dir(self):
        path = filedialog.askdirectory(title="Selecciona carpeta con PDFs")
        if path: self.var_pdfdir.set(path)

    def select_output_file(self):
        initial = self.var_output.get() or str(Path.cwd() / "resultado_conteos.csv")
        path = filedialog.asksaveasfilename(title="Guardar CSV de salida",
                                            defaultextension=".csv",
                                            initialfile=Path(initial).name,
                                            initialdir=str(Path(initial).parent),
                                            filetypes=[("CSV", "*.csv")])
        if path:
            if not str(path).lower().endswith(".csv"):
                path = f"{path}.csv"
            self.var_output.set(path)

    # Progreso
    def update_progress(self, current: int, total: int, filename: str):
        if total <= 0:
            self.progress_value.set(0)
            self.var_progress_text.set("Sin PDFs.")
            self.var_progress_count.set("")
        else:
            val = int(current * self.progress_max / total)
            self.progress_value.set(val)
            self.var_progress_text.set(f"Procesando: {filename}" if filename else "Procesando...")
            self.var_progress_count.set(f"{current} / {total} PDFs")
        self.update_idletasks()

    def on_run(self):
        words = self.var_words.get().strip()
        pdfdir = self.var_pdfdir.get().strip()
        outcsv = self.var_output.get().strip() or str(Path.cwd() / "resultado_conteos.csv")

        if not words:
            messagebox.showwarning("Falta archivo de palabras", "Selecciona el archivo (Excel/CSV).")
            return
        if not pdfdir:
            messagebox.showwarning("Falta carpeta de PDFs", "Selecciona la carpeta con los PDFs.")
            return

        backend_name, backend_fn = pick_pdf_backend()
        if backend_name == "none":
            messagebox.showerror(
                "Dependencias PDF faltantes",
                "Necesitas instalar al menos uno:\n  pip install pdfminer.six\n  o\n  pip install pypdf"
            )
            return

        try:
            self.run_count(words_path=Path(words),
                           pdf_dir=Path(pdfdir),
                           out_csv=Path(outcsv),
                           backend_name=backend_name,
                           pdf_text_fn=backend_fn,
                           substrings=self.var_substrings.get(),
                           keep_accents=self.var_keep_accents.get(),
                           recursive=self.var_recursive.get())
        except Exception as e:
            # Además del messagebox, imprime el error si abriste desde terminal
            print("ERROR:", e, file=sys.stderr)
            messagebox.showerror("Error inesperado", str(e))

    # Lógica principal
    def run_count(self, words_path: Path, pdf_dir: Path, out_csv: Path,
                  backend_name: str, pdf_text_fn,
                  substrings: bool, keep_accents: bool, recursive: bool) -> None:

        if not words_path.exists():
            messagebox.showerror("Error", f"No existe el archivo de palabras:\n{words_path}")
            return
        if not pdf_dir.exists() or not pdf_dir.is_dir():
            messagebox.showerror("Error", f"No existe la carpeta de PDFs o no es carpeta:\n{pdf_dir}")
            return

        try:
            original_words = read_words(words_path)
        except Exception as e:
            messagebox.showerror("Error leyendo palabras", str(e)); return

        if not original_words:
            messagebox.showerror("Sin palabras", "El archivo no contiene palabras en la 1ª columna.")
            return

        remove_accents = not keep_accents
        whole_word = not substrings

        original_to_norm = {w: normalize_text(w, remove_accents) for w in original_words}
        norm_tokens_unique = list({normalize_text(w, remove_accents) for w in original_words})
        patterns = {nw: compile_pattern(nw, whole_word) for nw in norm_tokens_unique}

        pdf_paths = sorted(pdf_dir.rglob("*.pdf") if recursive else pdf_dir.glob("*.pdf"))
        total = len(pdf_paths)

        if total == 0:
            if not messagebox.askyesno("Aviso",
                "No se encontraron PDFs en la carpeta indicada.\n"
                "¿Quieres generar el CSV igualmente sólo con la columna 'palabra'?"):
                return

        counts_per_pdf: Dict[str, Dict[str, int]] = {}

        self.config(cursor="wait"); self.update_idletasks()
        try:
            for idx, pdf_path in enumerate(pdf_paths, start=1):
                self.update_progress(idx-1, total, pdf_path.name)

                # Extraer texto usando el backend elegido
                text = ""
                try:
                    text = pdf_text_fn(str(pdf_path)) or ""
                except Exception:
                    text = ""  # si falla un archivo, continúa

                norm_text = normalize_text(text, remove_accents)
                per_token_counts = count_occurrences(norm_text, patterns)
                total_words = len(norm_text.split())
                per_token_counts["__TOTAL_PALABRAS__"] = total_words
                counts_per_pdf[pdf_path.name] = per_token_counts

                self.update_progress(idx, total, pdf_path.name)

            pdf_names = list(counts_per_pdf.keys())
            out_csv.parent.mkdir(parents=True, exist_ok=True)

            with out_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["palabra"] + pdf_names)

                for w in original_words:
                    nw = original_to_norm[w]
                    row = [w] + [counts_per_pdf[p].get(nw, 0) for p in pdf_names]
                    writer.writerow(row)

                total_row = ["__TOTAL_PALABRAS__"] + [
                    counts_per_pdf[p].get("__TOTAL_PALABRAS__", 0) for p in pdf_names
                ]
                writer.writerow(total_row)

            messagebox.showinfo("Listo", f"CSV generado:\n{out_csv}\n\nBackend PDF: {backend_name}")
        finally:
            self.config(cursor=""); self.update_progress(total, max(total,1), "")

if __name__ == "__main__":
    # Check mínimo de pandas (tkinter ya está si llegamos aquí)
    try:
        import pandas  # noqa
    except Exception:
        # Ya hay ventana, podemos advertir bien
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Dependencias faltantes", "Falta 'pandas'. Instala con:\n  pip install pandas")
        sys.exit(1)

    app = App()
    app.mainloop()
