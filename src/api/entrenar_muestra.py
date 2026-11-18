"""Entrena K-Means con una muestra del CSV de octubre y guarda los artefactos del API.

Úselo si todavía no ejecutó el notebook de SageMaker. El notebook, al llegar al paso 8,
escribe los mismos archivos en esta carpeta.
"""
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import LabelEncoder, StandardScaler

DESTINO = Path(__file__).resolve().parent / "artefactos"
COLUMNAS = [
    "total_vistas",
    "total_carritos",
    "total_remociones",
    "total_compras",
    "ticket_promedio",
    "sesiones",
    "categorias_distintas",
    "tasa_conversion",
    "categoria_principal",
]
NUMERICAS = COLUMNAS[:-1]
DESCRIPCIONES = {
    "Exploradores": "Miran mucho y compran poco",
    "Compradores frecuentes": "Compran varias veces",
    "Abandonan el carrito": "Meten productos y no pagan",
    "Alto valor": "Compran poco, pero el ticket es alto",
}


def buscar_csv():
    if os.environ.get("EVENTOS_CSV"):
        return Path(os.environ["EVENTOS_CSV"])
    aqui = Path(__file__).resolve()
    for padre in aqui.parents:
        candidato = padre / "eCommerce-2019-Oct.csv"
        if candidato.exists():
            return candidato
    raise FileNotFoundError(
        "No está el CSV de octubre. Defina EVENTOS_CSV o deje el archivo junto al proyecto."
    )


def recortar_precio(serie):
    precios = pd.to_numeric(serie, errors="coerce")
    validos = precios[precios >= 0]
    if validos.empty:
        return precios.where(precios >= 0)
    q1 = validos.quantile(0.25)
    q3 = validos.quantile(0.75)
    limite = q3 + 1.5 * (q3 - q1)
    precios = precios.where(precios >= 0)
    return precios.clip(upper=limite)


def fichas_de_usuario(eventos):
    eventos = eventos.copy()
    eventos["event_type"] = eventos["event_type"].astype(str).str.strip().str.upper()
    eventos["price"] = recortar_precio(eventos["price"])
    raiz = eventos["category_code"].fillna("").astype(str).str.split(".").str[0]
    eventos["category_root"] = raiz.replace("", "sin_categoria")

    def contar(tipo):
        return lambda s: int((s == tipo).sum())

    compras = eventos.loc[eventos["event_type"] == "PURCHASE"].groupby("user_id")["price"].mean()
    fichas = eventos.groupby("user_id").agg(
        total_vistas=("event_type", contar("VIEW")),
        total_carritos=("event_type", contar("CART")),
        total_remociones=("event_type", contar("REMOVE_FROM_CART")),
        total_compras=("event_type", contar("PURCHASE")),
        sesiones=("user_session", "nunique"),
        categorias_distintas=("category_root", "nunique"),
        categoria_principal=("category_root", lambda s: s.value_counts().index[0]),
    )
    fichas["ticket_promedio"] = compras.reindex(fichas.index).fillna(0)
    fichas["tasa_conversion"] = np.where(
        fichas["total_vistas"] > 0,
        fichas["total_compras"] / fichas["total_vistas"],
        0,
    )
    return fichas.reset_index()


def nombrar_grupos(centros, k):
    nombres = [
        "Exploradores",
        "Compradores frecuentes",
        "Abandonan el carrito",
        "Alto valor",
    ]
    vistas = centros[:, COLUMNAS.index("total_vistas")]
    carritos = centros[:, COLUMNAS.index("total_carritos")]
    compras = centros[:, COLUMNAS.index("total_compras")]
    ticket = centros[:, COLUMNAS.index("ticket_promedio")]
    puntajes = {
        "Exploradores": vistas / (compras + 1),
        "Compradores frecuentes": compras,
        "Abandonan el carrito": carritos - compras,
        "Alto valor": ticket,
    }
    libres = set(range(k))
    asignado = {}
    for nombre in nombres:
        if not libres:
            break
        grupo = max(libres, key=lambda i: puntajes[nombre][i])
        asignado[grupo] = nombre
        libres.remove(grupo)
    for grupo in sorted(libres):
        asignado[grupo] = f"Grupo {grupo}"
    return {
        str(grupo): {
            "nombre": nombre,
            "descripcion": DESCRIPCIONES.get(nombre, "Grupo adicional de clientes"),
        }
        for grupo, nombre in asignado.items()
    }


def main():
    ruta = buscar_csv()
    print(f"Leyendo muestra de {ruta}")
    eventos = pd.read_csv(
        ruta,
        nrows=200_000,
        usecols=["event_type", "category_code", "price", "user_id", "user_session"],
    )
    fichas = fichas_de_usuario(eventos)
    print(f"Clientes en la muestra: {len(fichas):,}")

    datos = fichas[COLUMNAS].copy()
    for columna in NUMERICAS:
        datos[columna] = datos[columna].clip(
            datos[columna].quantile(0.01),
            datos[columna].quantile(0.99),
        )
    encoder = LabelEncoder()
    datos["categoria_principal"] = encoder.fit_transform(datos["categoria_principal"].astype(str))
    scaler = StandardScaler()
    matriz = scaler.fit_transform(datos)

    rng = np.random.RandomState(42)
    muestra = matriz[rng.choice(len(matriz), min(8000, len(matriz)), replace=False)]
    siluetas = {}
    for k in range(2, 9):
        modelo = KMeans(n_clusters=k, random_state=42, n_init=10)
        siluetas[k] = float(silhouette_score(muestra, modelo.fit_predict(muestra)))
    k_optimo = max(siluetas, key=siluetas.get)
    print("Silueta por k:", {k: round(v, 4) for k, v in siluetas.items()})
    print("Metrica principal: coeficiente de silueta. K elegido:", k_optimo)

    modelo = KMeans(n_clusters=k_optimo, random_state=42, n_init=10, max_iter=300)
    modelo.fit(matriz)
    centros = scaler.inverse_transform(modelo.cluster_centers_)
    perfiles = nombrar_grupos(centros, k_optimo)

    DESTINO.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, DESTINO / "kmeans_model.joblib")
    joblib.dump(scaler, DESTINO / "scaler.joblib")
    joblib.dump({"categoria_principal": encoder}, DESTINO / "encoders.joblib")
    (DESTINO / "perfiles.json").write_text(
        json.dumps(perfiles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DESTINO / "columnas.json").write_text(
        json.dumps(COLUMNAS, ensure_ascii=False),
        encoding="utf-8",
    )
    (DESTINO / "metrica.json").write_text(
        json.dumps(
            {
                "metrica": "coeficiente_de_silueta",
                "justificacion": "No hay etiqueta verdadera por cliente, por eso no se usa F1.",
                "silueta_por_k": siluetas,
                "k_elegido": k_optimo,
                "filas_muestra": int(len(eventos)),
                "clientes": int(len(fichas)),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Artefactos guardados en {DESTINO}")


if __name__ == "__main__":
    main()
