import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
from paddleocr import PaddleOCR
import threading
import cv2
import re
from unidecode import unidecode
from fuzzywuzzy import fuzz

# Configuración inicial de PaddleOCR para idioma español
ocr = PaddleOCR(use_angle_cls=True, lang='es')

# Diccionario de localidades a zonas
zonas = {
    "3 de Febrero": "2", "TRES DE FEBRERO": "2", "Almirante Brown": "3", "Avellaneda": "2",
    "Berazategui": "3", "Berisso": "4", "CABA": "1", "Campana": "4", "Cañuelas": "4",
    "Del Viso": "4", "Derqui": "4", "Ensenada": "4", "Escobar": "4", "Esteban Echeverría": "3",
    "Ezeiza": "3", "Florencio Varela": "3", "Garin": "4", "General Rodríguez": "4",
    "Guernica": "4", "Hurlingham": "2", "Ingeniero Maschwitz": "4", "INGENIERO": "4",
    "Ituzaingó": "2", "José C. Paz": "3", "La Matanza Norte": "2", "La Matanza Sur": "3",
    "Lanús": "2", "La Plata Centro": "4", "La Plata Norte": "4", "La Plata Oeste": "4",
    "Lomas de Zamora": "2", "Luján": "4", "Malvinas Argentinas": "3", "Marcos Paz": "4",
    "Merlo": "3", "Moreno": "3", "Morón": "2", "Nordelta": "4", "Pilar": "4",
    "Quilmes": "3", "San Fernando": "2", "San Isidro": "2", "San Martín": "2",
    "San Miguel": "3", "San Vicente": "4", "Tigre": "3", "Vicente López": "2",
    "Villa Rosa": "4", "Zárate": "4", "La Plata": "4", "Canning": "3",
    "Belen de Escobar": "4", "Isidro Casanova": "3", "San Justo": "2"
}

# Lista de sublocalidades conocidas de CABA
caba_sublocalidades = [
    "La Boca", "San Nicolás", "Floresta", "Caballito", "Flores", "Barracas", "Villa Del Parque",
    "Parque Patricios", "La Paternal", "Mataderos", "Monte Castro", "San Nicolas", "Villa del Parque"
]

# Lista de palabras irrelevantes a filtrar (en minúsculas)
irrelevant_words = {
    'entrega:', 'envio', 'flex', 'venta:', 'dirección:', 'direccion:', 'direccion', 'ireccion',
    'direccian', 'ccion', 'referencia', 'barrio:', 'residencial', 'comercial', 'cp:', 'sryd',
    'tec.', 'n15.tiene', 'ucuman', 'lavalle', 'bautista', 'alberdi', 'av.', 'martin', 'garcia',
    'calle', 'av', 'avenida', 'n', 'referencia:', 'entre:', 'entre', 'japony', 'san', 'blas',
    'mirave', '7mo', 'piso', 'departamento', 'lote', 'no', 'funciona', 'el', 'timbre', 'casa',
    'puerta', 'porton', 'negro', 'rejas', 'gris', 'localidad', 'barrio', 'destinatario:',
    'destinatario', 'puerto', 'de', 'olivos', 'juan', 'ref', 'dias', 'solis', 'barr', 'busqueda',
    'e', 'sus', 's.a.depadua', 'nobel750', 'albeniz1791', 'williams', 'aguirre', 'belende',
    'sancarlos451', 'melo', 'negrete', 'viola2873', 'paraguay', '21402140', '23', 'opoldo',
    'lugones', 'burzaco1852', 'lindo', 'rawson', 'don', 'bosco', '246', 'aristobulo', 'del',
    'valle', 'hipolito', 'irurtia', 'amancio', 'alcorta', 'toldo', 'verd', 'colonia', 'lynch',
    '2668', 'reconquista', 'pack', 'id', 'south', 'spad', 'srl', '1003', 'san nicolas', 'nunez',
    'correa', 'latina', 'fraga', 'alem', 'primera', 'junta'
}

def extract_text_from_image(image_path, log_text):
    """Extrae texto de una imagen utilizando PaddleOCR."""
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise Exception(f"No se pudo cargar la imagen: {image_path}")
        
        result = ocr.ocr(image_path, cls=True)
        if not result or not result[0]:
            raise Exception("No se detectó texto en la imagen")
            
        extracted_text = " ".join([line[1][0] for line in result[0]])
        log_text.insert(tk.END, f"Texto extraído de {image_path}: {extracted_text}\n")
        return extracted_text
    except Exception as e:
        log_text.insert(tk.END, f"Error al extraer texto de {image_path}: {str(e)}\n")
        return None

def find_locality_and_zone(extracted_text, log_text, cp_number=None):
    """Encuentra la localidad y la zona a partir del texto extraído."""
    entrega_index = extracted_text.lower().find("entrega:")
    if entrega_index == -1:
        log_text.insert(tk.END, "Advertencia: No se encontró 'Entrega:' en el texto.\n")
        return None, "Desconocida"

    entrega_text = extracted_text[entrega_index:]
    cp_pattern = r"[Cc][Pp][ :]*\d+"
    cp_matches = list(re.finditer(cp_pattern, entrega_text))
    
    if not cp_matches:
        log_text.insert(tk.END, "Advertencia: No se encontró 'CP:' después de 'Entrega:'\n")
        return None, "Desconocida"

    cp_indices = [entrega_index + match.start() for match in cp_matches]
    residential_index = extracted_text.lower().find("residencial")
    commercial_index = extracted_text.lower().find("comercial")
    end_index = min(residential_index, commercial_index) if residential_index != -1 and commercial_index != -1 else (residential_index if residential_index != -1 else commercial_index)
    if end_index == -1:
        end_index = len(extracted_text)

    localities = []
    for cp_index in cp_indices:
        next_cp_index = extracted_text.find("CP:", cp_index + 3) if cp_index < len(cp_indices) - 1 else end_index
        if next_cp_index == -1 or next_cp_index > end_index:
            next_cp_index = end_index
        locality_text = extracted_text[cp_index + 3:next_cp_index].strip()

        locality_words = locality_text.split()
        filtered_words = []
        for word in locality_words:
            word_lower = word.lower()
            if word_lower in ['ireccion', 'direccian', 'ccion']:
                word_lower = 'direccion'
            if not (word.isdigit() or re.match(r"\d{2}-[A-Za-z]{3}\.", word) or word_lower in irrelevant_words or word.endswith(':')):
                filtered_words.append(word)
        locality = " ".join(filtered_words[:3]).strip()

        if not locality:
            prev_text = extracted_text[max(entrega_index, cp_index - 50):cp_index].strip()
            prev_words = prev_text.split()
            filtered_prev_words = [word for word in prev_words if not (word.isdigit() or re.match(r"\d{2}-[A-Za-z]{3}\.", word) or word.lower() in irrelevant_words or word.endswith(':'))]
            locality = " ".join(filtered_prev_words[-3:]).strip()

        locality_words = locality.split()
        unique_words = []
        for word in locality_words:
            if word not in unique_words or word in ["CABA"]:
                unique_words.append(word)
        locality = " ".join(unique_words).strip().capitalize()
        localities.append(locality)

    if not any(localities) and cp_number and 1000 <= cp_number <= 1499:
        localities = ["CABA"]

    corrected_localities = []
    for locality in localities:
        is_caba = any(subloc.lower() in locality.lower() for subloc in caba_sublocalidades) or (cp_number and 1000 <= cp_number <= 1499)
        if is_caba and not locality.startswith("CABA"):
            subloc = next((subloc for subloc in caba_sublocalidades if subloc.lower() in locality.lower()), locality)
            locality = f"CABA {subloc}"
        corrected_localities.append(locality)

    zones = []
    for locality in corrected_localities:
        zona = "1" if locality.startswith("CABA") or (cp_number and 1000 <= cp_number <= 1499) else None
        if not zona:
            locality_normalized = unidecode(locality).lower()
            best_match_score = 0
            best_match_key = None
            for key in zonas:
                key_normalized = unidecode(key).lower()
                similarity = fuzz.partial_ratio(locality_normalized, key_normalized)
                if similarity > best_match_score and similarity >= 75:
                    best_match_score = similarity
                    best_match_key = key
            if best_match_key:
                zona = zonas[best_match_key]
                log_text.insert(tk.END, f"Coincidencia aproximada: {locality} -> {best_match_key} (Zona {zona})\n")
            else:
                zona = "Desconocida"
                log_text.insert(tk.END, f"Advertencia: Localidad no encontrada: {locality}\n")
        zones.append(zona)

    return corrected_localities, zones

def process_batch(image_paths_batch, batch_index, log_text, result_text, progress_var, all_results, all_zona_counts, single_mode=False):
    """Procesa un lote de imágenes con PaddleOCR."""
    batch_size = 1 if single_mode else min(3, len(image_paths_batch))
    batch_results = []
    batch_zona_counts = {"1": 0, "2": 0, "3": 0, "4": 0}
    processed_localities = set()

    log_text.insert(tk.END, f"Procesando lote {batch_index + 1} con {batch_size} imágenes...\n")
    root.update()

    for idx, image_path in enumerate(image_paths_batch[:batch_size], 1):
        try:
            extracted_text = extract_text_from_image(image_path, log_text)
            if not extracted_text:
                batch_results.append(f"Imagen {idx}: No se pudo extraer texto - Zona Desconocida")
                continue

            cp_pattern = r"[Cc][Pp][ :]*(\d+)"
            cp_match = re.search(cp_pattern, extracted_text)
            cp_number = int(cp_match.group(1)) if cp_match else None

            localities, zones = find_locality_and_zone(extracted_text, log_text, cp_number)
            for label_idx, (locality, zona) in enumerate(zip(localities, zones), 1):
                if locality in processed_localities or not locality:
                    log_text.insert(tk.END, f"Duplicado o inválido ignorado (Lote {batch_index + 1}, Etiqueta {label_idx}): {locality}\n")
                    continue
                processed_localities.add(locality)
                batch_results.append(f"Imagen {idx} (Etiqueta {label_idx}): {locality} - Zona {zona}")
                if zona != "Desconocida":
                    batch_zona_counts[zona] += 1

        except Exception as e:
            log_text.insert(tk.END, f"Error procesando {image_path}: {str(e)}\n")

    with threading.Lock():
        all_results.extend(batch_results)
        for zona, count in batch_zona_counts.items():
            all_zona_counts[zona] += count

    progress_var.set(((batch_index + 1) / (len(image_paths) // (1 if single_mode else 3) + 1)) * 100)
    root.update()

def process_images(image_paths, log_text, result_text, progress_var, single_mode=False):
    """Procesa todas las imágenes cargadas."""
    log_text.delete(1.0, tk.END)
    log_text.insert(tk.END, f"Iniciando procesamiento {'(modo individual)' if single_mode else '(modo por lotes)' }...\n")
    progress_var.set(0)
    root.update()

    all_results = []
    all_zona_counts = {"1": 0, "2": 0, "3": 0, "4": 0}

    if single_mode:
        for i, path in enumerate(image_paths):
            process_batch([path], i, log_text, result_text, progress_var, all_results, all_zona_counts, single_mode)
    else:
        batch_size = 3
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            process_batch(batch, i // batch_size, log_text, result_text, progress_var, all_results, all_zona_counts)

    result_text.delete(1.0, tk.END)
    result_text.insert(tk.END, "Resultados:\n" + "\n".join(all_results) + "\n\nConteo final por zona:\n")
    for zona, count in all_zona_counts.items():
        result_text.insert(tk.END, f"Zona {zona}: {count} envíos\n")
    log_text.insert(tk.END, "Procesamiento completado.\n")
    start_button.config(state="normal")

def load_images():
    """Carga las imágenes seleccionadas por el usuario."""
    global image_paths
    file_paths = filedialog.askopenfilenames(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
    if file_paths:
        image_paths = list(file_paths)
        log_text.delete(1.0, tk.END)
        log_text.insert(tk.END, f"Cargadas {len(image_paths)} imágenes: {', '.join(image_paths)}\n")
        start_button.config(state="normal")

def start_process():
    """Inicia el procesamiento en un hilo separado."""
    if not image_paths:
        messagebox.showerror("Error", "Por favor, carga al menos una imagen antes de procesar.")
        return
    single_mode = messagebox.askyesno("Modo de procesamiento", "¿Deseas procesar una imagen a la vez? (Más lento pero detallado)")
    start_button.config(state="disabled")
    threading.Thread(target=process_images, args=(image_paths, log_text, result_text, progress_var, single_mode), daemon=True).start()

def export_results():
    """Exporta los resultados a un archivo de texto."""
    ruta = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
    if ruta:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(result_text.get(1.0, tk.END))
        messagebox.showinfo("Éxito", f"Resultados guardados en {ruta}")

# Configuración de la interfaz gráfica
root = tk.Tk()
root.title("Procesador de Etiquetas de Envío")
root.geometry("900x700")
root.config(bg="#2E2E2E")

# Variables globales
image_paths = []
progress_var = tk.DoubleVar()

# Frame principal
frame = tk.Frame(root, bg="#2E2E2E")
frame.pack(pady=10)

# Botones
tk.Button(frame, text="Cargar Imágenes", command=load_images, bg="#555555", fg="#FFFFFF").grid(row=0, column=0, padx=5, pady=5, sticky="w")
start_button = tk.Button(frame, text="Iniciar Procesamiento", command=start_process, bg="#555555", fg="#FFFFFF", state="disabled")
start_button.grid(row=0, column=1, padx=5, pady=5)
tk.Button(frame, text="Exportar Resultados", command=export_results, bg="#555555", fg="#FFFFFF").grid(row=0, column=2, padx=5, pady=5)

# Área de log
tk.Label(frame, text="Log:", fg="#FFFFFF", bg="#2E2E2E").grid(row=1, column=0, columnspan=3, pady=5, sticky="w")
log_text = scrolledtext.ScrolledText(frame, height=5, width=100, bg="#333333", fg="#FFFFFF", insertbackground="white")
log_text.grid(row=2, column=0, columnspan=3, padx=5, pady=5)
log_text.insert(tk.END, "Bienvenido. Usa 'Cargar Imágenes' para comenzar.\n")

# Área de resultados
tk.Label(frame, text="Resultados:", fg="#FFFFFF", bg="#2E2E2E").grid(row=3, column=0, columnspan=3, pady=5, sticky="w")
result_text = scrolledtext.ScrolledText(frame, height=20, width=100, bg="#333333", fg="#FFFFFF", insertbackground="white")
result_text.grid(row=4, column=0, columnspan=3, padx=5, pady=5)

# Barra de progreso
progress_bar = ttk.Progressbar(frame, variable=progress_var, maximum=100)
progress_bar.grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

# Iniciar la interfaz
root.mainloop()
