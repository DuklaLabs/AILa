# YOLODetector

Samostatný (mimo `docker-compose.yml`) prototyp na detekci vad 3D tisku
(YOLOv11). Nesouvisí s hlavním FastAPI/`ailacore` stackem — je to trénovací
prostředí, ne služba s API.

- `Dockerfile` — staví na `ultralytics/ultralytics:latest` (PyTorch/NumPy/
  OpenCV/YOLOv11 předinstalované), zkopíruje `build_dataset.py`, spustí ho při
  buildu (`|| true`, takže selhání stahování zdrojů build nezastaví) a skončí
  v interaktivním shellu (`CMD ["/bin/bash"]") — trénink/predikce se pak pouští
  ručně uvnitř kontejneru (`yolo train ...`).
- `build_dataset.py` — stáhne/sestaví dataset z veřejných zdrojů (bez Kaggle),
  sjednotí třídy vad tisku do jednoho `CLASS_MAP` (0 ok … 9 first_layer_issue)
  a rozdělí do `data/images/{train,val}` + `data/labels/{train,val}` ve
  standardním YOLO formátu.
- `yolo11n.pt` — předtrénované váhy (YOLOv11 nano) uložené v repu jako
  výchozí bod pro fine-tuning.

Použití:

```
cd YOLODetector
docker build -t yolo-detector .
docker run -it --gpus all yolo-detector
# uvnitř kontejneru:
yolo train model=yolo11n.pt data=data.yaml epochs=100
```
