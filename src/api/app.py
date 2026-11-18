import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
ARTEFACTOS = BASE / "artefactos"

app = FastAPI(
    title="Perfiles de clientes de la tienda",
    description=(
        "Agrupa un cliente de la tienda multicategoría en un perfil. "
        "El modelo es K-Means entrenado con vistas, carrito, compras, ticket y conversión. "
        "La métrica para elegir el número de grupos es el coeficiente de silueta."
    ),
    version="1.0.0",
)


class PerfilEntrada(BaseModel):
    total_vistas: int = Field(ge=0, le=1_000_000, examples=[20])
    total_carritos: int = Field(ge=0, le=1_000_000, examples=[4])
    total_remociones: int = Field(ge=0, le=1_000_000, examples=[1])
    total_compras: int = Field(ge=0, le=1_000_000, examples=[2])
    ticket_promedio: float = Field(ge=0, le=1_000_000, examples=[45.5])
    sesiones: int = Field(ge=0, le=1_000_000, examples=[3])
    categorias_distintas: int = Field(ge=0, le=100, examples=[2])
    tasa_conversion: float = Field(ge=0, le=100, examples=[0.1])
    categoria_principal: str = Field(min_length=1, max_length=80, examples=["electronics"])


class Solicitud(BaseModel):
    instancias: list[PerfilEntrada] = Field(min_length=1, max_length=100)


class Prediccion(BaseModel):
    cluster: int
    perfil: str
    descripcion: str


class Respuesta(BaseModel):
    predicciones: list[Prediccion]


@lru_cache(maxsize=1)
def cargar_modelo():
    necesarios = [
        "kmeans_model.joblib",
        "scaler.joblib",
        "encoders.joblib",
        "perfiles.json",
        "columnas.json",
    ]
    faltan = [nombre for nombre in necesarios if not (ARTEFACTOS / nombre).exists()]
    if faltan:
        raise FileNotFoundError(
            "Faltan artefactos del modelo: " + ", ".join(faltan)
        )
    with open(ARTEFACTOS / "perfiles.json", encoding="utf-8") as archivo:
        perfiles = json.load(archivo)
    with open(ARTEFACTOS / "columnas.json", encoding="utf-8") as archivo:
        columnas = json.load(archivo)
    return {
        "modelo": joblib.load(ARTEFACTOS / "kmeans_model.joblib"),
        "scaler": joblib.load(ARTEFACTOS / "scaler.joblib"),
        "encoders": joblib.load(ARTEFACTOS / "encoders.joblib"),
        "perfiles": perfiles,
        "columnas": columnas,
    }


@app.get("/salud", tags=["servicio"])
def salud():
    try:
        cargar_modelo()
    except FileNotFoundError as exc:
        return {"estado": "sin_modelo", "detalle": str(exc)}
    return {"estado": "listo"}


@app.post("/predecir", response_model=Respuesta, tags=["prediccion"])
def predecir(solicitud: Solicitud):
    try:
        artefactos = cargar_modelo()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    encoder = artefactos["encoders"]["categoria_principal"]
    conocidas = set(encoder.classes_)
    desconocidas = sorted({
        item.categoria_principal
        for item in solicitud.instancias
        if item.categoria_principal not in conocidas
    })
    if desconocidas:
        raise HTTPException(
            status_code=422,
            detail={
                "mensaje": "Hay categorías que el modelo no vio en el entrenamiento.",
                "categorias_desconocidas": desconocidas,
                "categorias_validas": sorted(conocidas),
            },
        )

    filas = []
    for item in solicitud.instancias:
        valores = item.model_dump()
        valores["categoria_principal"] = int(encoder.transform([item.categoria_principal])[0])
        filas.append([valores[columna] for columna in artefactos["columnas"]])

    matriz = artefactos["scaler"].transform(np.array(filas, dtype=float))
    grupos = artefactos["modelo"].predict(matriz)

    predicciones = []
    for grupo in grupos:
        ficha = artefactos["perfiles"].get(
            str(int(grupo)),
            {"nombre": f"Grupo {int(grupo)}", "descripcion": "Sin descripción"},
        )
        predicciones.append({
            "cluster": int(grupo),
            "perfil": ficha["nombre"],
            "descripcion": ficha["descripcion"],
        })
    return {"predicciones": predicciones}
