"""Convierte los artefactos del notebook en un JSON que la Lambda puede leer sin scikit-learn."""

import json
from pathlib import Path

import joblib

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = RAIZ / "api" / "artefactos"
DESTINO = Path(__file__).resolve().parent / "lambda_modelo" / "modelo.json"


def main():
    modelo = joblib.load(ORIGEN / "kmeans_model.joblib")
    scaler = joblib.load(ORIGEN / "scaler.joblib")
    encoders = joblib.load(ORIGEN / "encoders.joblib")
    perfiles = json.loads((ORIGEN / "perfiles.json").read_text(encoding="utf-8"))
    columnas = json.loads((ORIGEN / "columnas.json").read_text(encoding="utf-8"))
    metrica = json.loads((ORIGEN / "metrica.json").read_text(encoding="utf-8"))
    categorias = [str(nombre) for nombre in encoders["categoria_principal"].classes_]
    documento = {
        "columnas": columnas,
        "categorias": categorias,
        "media": [float(valor) for valor in scaler.mean_],
        "escala": [float(valor) for valor in scaler.scale_],
        "centroides": [[float(valor) for valor in fila] for fila in modelo.cluster_centers_],
        "perfiles": perfiles,
        "metrica": metrica,
    }
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Modelo publicado en {DESTINO}")


if __name__ == "__main__":
    main()
