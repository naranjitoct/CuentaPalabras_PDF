# ============================================
#   EXTRACTOR DE PALABRAS CLAVE DESDE PDF
#   INTERFAZ GRÁFICA CON TKINTER
# ============================================

import os
import glob
import itertools
import tkinter as tk
from tkinter import filedialog, messagebox

import PyPDF2
import nltk
import spacy
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

# Descargar stopwords de NLTK la primera vez
nltk.download('stopwords')
from nltk.corpus import stopwords

# Cargar modelo de spaCy
nlp = spacy.load("en_core_web_sm")
stop_words = set(stopwords.words('english'))

# ======================================================
#          CARPETAS DE RESULTADOS
# ======================================================

BASE_RESULTS = "RESULTS"
os.makedirs(BASE_RESULTS, exist_ok=True)

SUBFOLDERS = {
    "tf": os.path.join(BASE_RESULTS, "TF"),
    "tfidf": os.path.join(BASE_RESULTS, "TFIDF"),
    "ngrams": os.path.join(BASE_RESULTS, "NGRAMS"),
    "cooc": os.path.join(BASE_RESULTS, "COOCCURRENCES"),
}

for sf in SUBFOLDERS.values():
    os.makedirs(sf, exist_ok=True)


# ======================================================
#                   FUNCIONES PRINCIPALES
# ======================================================

def load_pdfs(folder_path):
    texts = []
    pdf_names = []
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))

    log(f"Se han encontrado {len(pdf_files)} PDF.")
    if len(pdf_files) == 0:
        return [], []

    for file in pdf_files:
        try:
            with open(file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                pages_text = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
                texts.append("\n".join(pages_text))
                pdf_names.append(os.path.basename(file))
                log(f"  ✔ Leído: {os.path.basename(file)}")

        except Exception as e:
            log(f"  ❌ Error leyendo {file}: {e}")

    return texts, pdf_names


def preprocess(text):
    doc = nlp(text.lower())
    tokens = [
        token.lemma_
        for token in doc
        if token.is_alpha
        and token.lemma_ not in stop_words
        and len(token.lemma_) > 2
    ]
    return " ".join(tokens)


def get_cooccurrence_matrix(texts, tf_df, top_n=50):
    top_words = tf_df["word"].head(top_n).tolist()
    matrix = pd.DataFrame(0, index=top_words, columns=top_words)

    for text in texts:
        tokens = text.split()
        unique_tokens = set(tokens)
        filtered = [t for t in unique_tokens if t in top_words]

        for w1, w2 in itertools.combinations(filtered, 2):
            matrix.loc[w1, w2] += 1
            matrix.loc[w2, w1] += 1

    return matrix


# ======================================================
#                      TKINTER UI
# ======================================================

def log(msg):
    text_log.insert(tk.END, msg + "\n")
    text_log.see(tk.END)


def select_folder():
    folder = filedialog.askdirectory()
    if folder:
        folder_path_var.set(folder)


def run_processing():
    folder = folder_path_var.get()
    if not folder or not os.path.isdir(folder):
        messagebox.showerror("Error", "Debes seleccionar una carpeta válida.")
        return

    log("\n==============================")
    log("   INICIANDO PROCESAMIENTO")
    log("==============================\n")

    # 1. Cargar PDFs
    log("📄 Cargando PDFs...")
    raw_corpus, pdf_names = load_pdfs(folder)
    if len(raw_corpus) == 0:
        messagebox.showerror("Error", "No se encontraron PDFs.")
        return

    # 2. Preprocesar
    log("\n🔧 Preprocesando textos...")
    clean_corpus = [preprocess(t) for t in raw_corpus]

    # 3. TF
    if var_tf.get():
        log("\n📊 Calculando TF por documento...")

        vectorizer_tf = CountVectorizer()
        X_tf = vectorizer_tf.fit_transform(clean_corpus)
        palabras = vectorizer_tf.get_feature_names_out()

        # GLOBAL
        tf_global = X_tf.toarray().sum(axis=0)
        tf_global_df = pd.DataFrame({"word": palabras, "tf": tf_global})
        tf_global_df = tf_global_df.sort_values("tf", ascending=False)
        tf_global_df.to_csv(os.path.join(BASE_RESULTS, "tf_global.csv"), index=False)
        log("  ✔ Guardado: RESULTS/tf_global.csv")

        # POR DOCUMENTO
        for idx, pdf in enumerate(pdf_names):
            tf_individual = X_tf[idx].toarray().flatten()
            df_doc = pd.DataFrame({"word": palabras, "tf": tf_individual})
            df_doc = df_doc[df_doc["tf"] > 0].sort_values("tf", ascending=False)

            salida = os.path.join(SUBFOLDERS["tf"], pdf.replace(".pdf", "_tf.csv"))
            df_doc.to_csv(salida, index=False)
            log(f"  ✔ TF guardado por documento: {salida}")

        tf_df = tf_global_df
    else:
        tf_df = None

    # 4. TF-IDF
    if var_tfidf.get():
        log("\n📈 Calculando TF-IDF por documento...")

        vectorizer_tfidf = TfidfVectorizer(max_df=0.85, min_df=2)
        X_tfidf = vectorizer_tfidf.fit_transform(clean_corpus)
        palabras = vectorizer_tfidf.get_feature_names_out()

        # GLOBAL
        tfidf_global = X_tfidf.sum(axis=0).A1
        tfidf_df = pd.DataFrame({"word": palabras, "tfidf": tfidf_global})
        tfidf_df = tfidf_df.sort_values("tfidf", ascending=False)
        tfidf_df.to_csv(os.path.join(BASE_RESULTS, "tfidf_global.csv"), index=False)
        log("  ✔ Guardado: RESULTS/tfidf_global.csv")

        # POR DOCUMENTO
        for idx, pdf in enumerate(pdf_names):
            fila = X_tfidf[idx].toarray().flatten()
            df_doc = pd.DataFrame({"word": palabras, "tfidf": fila})
            df_doc = df_doc[df_doc["tfidf"] > 0].sort_values("tfidf", ascending=False)

            salida = os.path.join(SUBFOLDERS["tfidf"], pdf.replace(".pdf", "_tfidf.csv"))
            df_doc.to_csv(salida, index=False)
            log(f"  ✔ TF-IDF guardado por documento: {salida}")

    # 5. N-grams
    if var_ngrams.get():
        log("\n🔠 Extrayendo n-grams por documento...")

        vectorizer_ng = CountVectorizer(ngram_range=(2, 3), min_df=2)
        X_ng = vectorizer_ng.fit_transform(clean_corpus)
        ngrams = vectorizer_ng.get_feature_names_out()

        # GLOBAL
        ng_global = X_ng.toarray().sum(axis=0)
        ng_df = pd.DataFrame({"ngram": ngrams, "freq": ng_global})
        ng_df = ng_df.sort_values("freq", ascending=False)
        ng_df.to_csv(os.path.join(BASE_RESULTS, "ngrams_global.csv"), index=False)
        log("  ✔ Guardado: RESULTS/ngrams_global.csv")

        # POR DOCUMENTO
        for idx, pdf in enumerate(pdf_names):
            fila = X_ng[idx].toarray().flatten()
            df_doc = pd.DataFrame({"ngram": ngrams, "freq": fila})
            df_doc = df_doc[df_doc["freq"] > 0].sort_values("freq", ascending=False)

            salida = os.path.join(SUBFOLDERS["ngrams"], pdf.replace(".pdf", "_ngrams.csv"))
            df_doc.to_csv(salida, index=False)
            log(f"  ✔ N-grams guardado por documento: {salida}")

    # 6. Coocurrencias
    if var_cooc.get():
        if tf_df is None:
            messagebox.showwarning("Aviso", "Para coocurrencias es necesario activar TF.\nOmitiendo.")
        else:
            log("\n🔗 Calculando coocurrencias globales...")
            cooc = get_cooccurrence_matrix(clean_corpus, tf_df, top_n=50)
            salida = os.path.join(SUBFOLDERS["cooc"], "cooccurrence_matrix.csv")
            cooc.to_csv(salida)
            log(f"  ✔ Guardado: {salida}")

    log("\n🎉 PROCESO COMPLETADO\n")
    messagebox.showinfo("Finalizado", "El procesamiento ha terminado correctamente.")



#     INTERFAZ TKINTER


root = tk.Tk()
root.title("Extractor de Palabras Clave desde PDF")
root.geometry("700x550")

# Carpeta
frame_top = tk.Frame(root)
frame_top.pack(pady=10)

tk.Label(frame_top, text="Carpeta de PDFs:").grid(row=0, column=0, padx=5)
folder_path_var = tk.StringVar()
tk.Entry(frame_top, textvariable=folder_path_var, width=50).grid(row=0, column=1)
tk.Button(frame_top, text="Seleccionar", command=select_folder).grid(row=0, column=2, padx=5)

# Opciones
frame_opts = tk.LabelFrame(root, text="Opciones a ejecutar", padx=10, pady=10)
frame_opts.pack(pady=10)

var_tf = tk.BooleanVar(value=True)
var_tfidf = tk.BooleanVar(value=True)
var_ngrams = tk.BooleanVar(value=True)
var_cooc = tk.BooleanVar(value=True)

tk.Checkbutton(frame_opts, text="Frecuencias (TF)", variable=var_tf).pack(anchor="w")
tk.Checkbutton(frame_opts, text="TF-IDF", variable=var_tfidf).pack(anchor="w")
tk.Checkbutton(frame_opts, text="N-grams", variable=var_ngrams).pack(anchor="w")
tk.Checkbutton(frame_opts, text="Coocurrencias", variable=var_cooc).pack(anchor="w")

# Botón ejecutar
tk.Button(root, text="Ejecutar", command=run_processing, bg="#4CAF50", fg="white", height=2).pack(pady=10)

# Log
text_log = tk.Text(root, height=15, width=90)
text_log.pack(pady=10)

root.mainloop()
