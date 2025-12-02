import os
import zipfile
import json
import shutil
from pathlib import Path
import requests
from PIL import Image
import hashlib


BASE = Path(__file__).resolve().parent
RAW = BASE / "raw_sources"
DATA = BASE / "data"

TRAIN_IMG = DATA / "images/train"
VAL_IMG = DATA / "images/val"
TRAIN_LBL = DATA / "labels/train"
VAL_LBL = DATA / "labels/val"

for d in [RAW, TRAIN_IMG, VAL_IMG, TRAIN_LBL, VAL_LBL]:
    d.mkdir(parents=True, exist_ok=True)

# ======================================================
# DEFINUJEME JEDNOTNÉ TŘÍDY
# ======================================================

CLASS_MAP = {
    "ok": 0,
    "ok_print": 0,

    "spaghetti": 1,
    "stringy": 1,

    "bed_detach": 2,
    "detached": 2,

    "air_print": 3,

    "nozzle_clog": 4,
    "clog": 4,

    "blob": 5,
    "blobs": 5,

    "stringing": 6,

    "layer_shift": 7,
    "shift": 7,

    "warping": 8,
    "warp": 8,

    "first_layer_issue": 9,
}

# ======================================================
# HELPER FUNKCE
# ======================================================

def download(url, path):
    print(f"⬇️  Stahuji {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    path.write_bytes(r.content)

def unzip(zfile, target):
    with zipfile.ZipFile(zfile, "r") as f:
        f.extractall(target)

def hash_img(path: Path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except:
        return None

def write_yolo_label(path: Path, entries):
    lines = [
        f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"
        for cls, xc, yc, bw, bh in entries
    ]
    path.write_text("\n".join(lines))

ALL = []
HASHES = set()

def add_item(img: Path, labels: list):
    h = hash_img(img)
    if not h or h in HASHES:
        return
    HASHES.add(h)
    ALL.append((img, labels))

# ======================================================
# 1) DATASOURCE: PRINTWATCH
# ======================================================

def load_printwatch():
    z= RAW/"3d-printing-errors.zip"
    unzip(z, RAW / "3d-printing-errors")

    base = RAW / "3d-printing-errors"
    for img in (base / "images").glob("*.jpg"):
        lbl = base / "labels" / (img.stem + ".txt")
        if not lbl.exists():
            continue

        items = []
        for line in lbl.read_text().strip().split("\n"):
            cls, xc, yc, bw, bh = line.split()
            items.append((1, float(xc), float(yc), float(bw), float(bh)))  # spaghetti = 1

        add_item(img, items)

# ======================================================
# 2) DATASOURCE: SMARTFDM
# ======================================================

def load_smartfdm():
  
    z = RAW / "3d-printing-failure-detection.zip"
    unzip(z, RAW / "3d-printing-failure-detection")

    base = RAW / "3d-printing-failure-detection"
    imgdir = base / "images"
    lbldir = base / "labels"

    for img in imgdir.glob("*.jpg"):
        lbl = lbldir / (img.stem + ".txt")
        if not lbl.exists():
            continue

        items = []
        for line in lbl.read_text().split("\n"):
            parts = line.split()
            cls_name = parts[0].lower()
            if cls_name not in CLASS_MAP:
                continue
            cls_id = CLASS_MAP[cls_name]
            xc, yc, bw, bh = map(float, parts[1:])
            items.append((cls_id, xc, yc, bw, bh))

        add_item(img, items)

# ======================================================
# 3) DATASOURCE: LAYERSHIFT
# ======================================================

def load_layershift():
   
    z = RAW / "3d-printing-success-failure-dataset-finetuned.zip"
    unzip(z, RAW / "success-failure-dataset")

    base = RAW / "success-failure-dataset"

    for img in (base / "images").glob("*.jpg"):
        label_path = base / "labels" / (img.stem + ".txt")
        if not label_path.exists():
            continue

        items = []
        for line in label_path.read_text().split("\n"):
            cls_id, xc, yc, bw, bh = map(float, line.split())
            add_item(img, [(int(cls_id), xc, yc, bw, bh)])
        add_item(img, items)


# ======================================================
# STÁHNEME + PŘEVEDEME VŠE
# ======================================================

load_printwatch()
load_smartfdm()
load_layershift()
print(f"📊 Celkem obrázků po sloučení: {len(ALL)}")

# ======================================================
# TRAIN/VAL SPLIT 90/10
# ======================================================

ALL.sort(key=lambda x: x[0].name)
split = int(len(ALL)*0.9)
train = ALL[:split]
val = ALL[split:]

print(f"📚 Train: {len(train)}")
print(f"🧪 Val:   {len(val)}")

def save(part, imgdir, lbldir):
    for img, labels in part:
        dst_img = imgdir / img.name
        dst_lbl = lbldir / (img.stem + ".txt")
        shutil.copy(img, dst_img)
        write_yolo_label(dst_lbl, labels)

save(train, TRAIN_IMG, TRAIN_LBL)
save(val, VAL_IMG, VAL_LBL)

# ======================================================
# CONFIG FILE
# ======================================================

(DATA / "yolo_config.yaml").write_text(
    "path: ./data\n"
    "train: images/train\n"
    "val: images/val\n"
    "names:\n" +
    "".join([f"  {i}: {cls}\n" for cls, i in CLASS_MAP.items()])
)

print("🎉 HOTOVO! Super-dataset je připraven.")
