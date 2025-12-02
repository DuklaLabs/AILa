# ======================================================
# ZÁKLAD: Oficiální image od Ultralytics
# Má správně nastavený PyTorch, NumPy, OpenCV, YOLOv11
# ======================================================
FROM ultralytics/ultralytics:latest

# Pracovní adresář pro tvůj projekt
WORKDIR /app

# ------------------------------------------------------
# Základní info pro debug
# ------------------------------------------------------
RUN python - << 'EOF'
import sys, numpy as np, torch, cv2
print("Python:", sys.version)
print("NumPy:", np.__version__)
print("Torch:", torch.__version__, "CUDA available:", torch.cuda.is_available())
print("OpenCV:", cv2.__version__)
EOF

# ------------------------------------------------------
# Sem přidáš svoje skripty – hlavně build_dataset.py
# ------------------------------------------------------
COPY build_dataset.py ./build_dataset.py

# vytvoříme složky pro data (pro jistotu)
RUN mkdir -p /app/raw_sources /app/data

# ------------------------------------------------------
# Postavíme dataset (bez Kaggle)
# Když by nějaký mirror umřel, build NEspadne díky "|| true"
# ------------------------------------------------------
RUN python build_dataset.py || true

# ------------------------------------------------------
# (Volitelné) doinstaluj si další věci, které budeš chtít
# např. FastAPI, Uvicorn atd.
# ------------------------------------------------------
# RUN pip install fastapi uvicorn[standard] psycopg2-binary

# ------------------------------------------------------
# Výchozí příkaz – hodí tě do shellu
# Můžeš pak ručně:
#   yolo train ...
#   yolo predict ...
#   python main.py (FastAPI) atd.
# ------------------------------------------------------
CMD ["/bin/bash"]
