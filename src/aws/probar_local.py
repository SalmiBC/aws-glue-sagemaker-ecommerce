"""Comprueba que la Lambda responde igual que el modelo de scikit-learn y que valida las entradas."""

import json
import sys
from pathlib import Path

import joblib
import numpy as np

CARPETA = Path(__file__).resolve().parent / "lambda_modelo"
sys.path.insert(0, str(CARPETA))
import handler  # noqa: E402

ORIGEN = Path(__file__).resolve().parents[1] / "api" / "artefactos"
EJEMPLO = {
    "total_vistas": 20,
    "total_carritos": 4,
    "total_remociones": 1,
    "total_compras": 2,
    "ticket_promedio": 45.5,
    "sesiones": 3,
    "categorias_distintas": 2,
    "tasa_conversion": 0.1,
    "categoria_principal": "electronics",
}


def evento(metodo, ruta, cuerpo=None):
    return {
        "rawPath": ruta,
        "requestContext": {"http": {"method": metodo}},
        "headers": {"host": "ejemplo.execute-api.us-east-2.amazonaws.com", "x-forwarded-proto": "https"},
        "body": None if cuerpo is None else json.dumps(cuerpo),
    }


def cuerpo(respuesta):
    return json.loads(respuesta["body"])


def main():
    modelo = joblib.load(ORIGEN / "kmeans_model.joblib")
    scaler = joblib.load(ORIGEN / "scaler.joblib")
    encoder = joblib.load(ORIGEN / "encoders.joblib")["categoria_principal"]
    columnas = json.loads((ORIGEN / "columnas.json").read_text(encoding="utf-8"))
    categorias = list(encoder.classes_)

    rng = np.random.default_rng(7)
    fallos = 0
    for categoria in categorias:
        for _ in range(3):
            item = {
                "total_vistas": int(rng.integers(0, 80)),
                "total_carritos": int(rng.integers(0, 15)),
                "total_remociones": int(rng.integers(0, 8)),
                "total_compras": int(rng.integers(0, 6)),
                "ticket_promedio": float(rng.uniform(0, 400)),
                "sesiones": int(rng.integers(0, 12)),
                "categorias_distintas": int(rng.integers(0, 8)),
                "tasa_conversion": float(rng.uniform(0, 1)),
                "categoria_principal": categoria,
            }
            codigo = int(encoder.transform([categoria])[0])
            fila = []
            for columna in columnas:
                fila.append(float(codigo) if columna == "categoria_principal" else float(item[columna]))
            esperado = int(modelo.predict(scaler.transform(np.array([fila])))[0])
            obtenido = handler.predecir_fila(item)
            if obtenido != esperado:
                fallos += 1
                print("Difieren", item, esperado, obtenido)
    if fallos:
        raise SystemExit(f"{fallos} predicciones no coinciden con scikit-learn")

    buena = handler.handler(evento("POST", "/predecir", {"instancias": [EJEMPLO]}), None)
    if buena["statusCode"] != 200 or "predicciones" not in cuerpo(buena):
        raise SystemExit(f"La consulta válida falló: {buena}")

    negativa = handler.handler(evento("POST", "/predecir", {"instancias": [{**EJEMPLO, "total_vistas": -1}]}), None)
    if negativa["statusCode"] != 422:
        raise SystemExit("Un número negativo debería responder 422")

    rara = handler.handler(
        evento("POST", "/predecir", {"instancias": [{**EJEMPLO, "categoria_principal": "no-existe"}]}),
        None,
    )
    detalle = cuerpo(rara).get("detail", {})
    if rara["statusCode"] != 422 or "categorias_validas" not in detalle:
        raise SystemExit("Una categoría desconocida debería responder 422 con la lista válida")

    vacia = handler.handler(evento("POST", "/predecir", {"instancias": []}), None)
    if vacia["statusCode"] != 422:
        raise SystemExit("Una lista vacía debería responder 422")

    silueta = handler.handler(evento("GET", "/silueta"), None)
    if silueta["statusCode"] != 200 or "0.6625" not in silueta["body"] or ">2<" not in silueta["body"]:
        raise SystemExit("La página de silueta no muestra k=2 ni 0.6625")

    docs = handler.handler(evento("GET", "/docs"), None)
    if "swagger-ui" not in docs["body"]:
        raise SystemExit("Swagger no está en /docs")

    contrato = cuerpo(handler.handler(evento("GET", "/openapi.json"), None))
    if "/predecir" not in contrato["paths"]:
        raise SystemExit("OpenAPI no publica /predecir")

    formato_antiguo = handler.handler({
        "path": "/prod/silueta",
        "httpMethod": "GET",
        "headers": {},
        "requestContext": {"stage": "prod"},
    }, None)
    if formato_antiguo["statusCode"] != 200 or "0.6625" not in formato_antiguo["body"]:
        raise SystemExit("El formato antiguo de API Gateway no abre la silueta")

    consulta = handler.handler(evento("GET", "/"), None)
    if "Consultar perfil" not in consulta["body"] or "/predecir" not in consulta["body"]:
        raise SystemExit("La pantalla de consulta no apunta al API")

    print("Predicciones iguales al modelo original.")
    print("Validación, silueta, Swagger y pantalla de consulta responden en local.")
    print(json.dumps(cuerpo(buena), ensure_ascii=False))


if __name__ == "__main__":
    main()
