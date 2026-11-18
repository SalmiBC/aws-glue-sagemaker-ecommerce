import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

MODELO_URL = os.environ.get("MODELO_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT_SEGUNDOS = float(os.environ.get("MODELO_TIMEOUT", "5"))

app = FastAPI(
    title="Consulta de perfiles de clientes",
    description="Esta aplicación no carga el modelo. Llama al API publicado en MODELO_URL.",
    version="1.0.0",
)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "plantillas"))


def consultar_modelo(payload):
    try:
        respuesta = httpx.post(
            f"{MODELO_URL}/predecir",
            json=payload,
            timeout=TIMEOUT_SEGUNDOS,
        )
    except httpx.TimeoutException:
        return {
            "ok": False,
            "mensaje": "El servicio del modelo no respondió a tiempo. Intente de nuevo en unos segundos.",
        }
    except httpx.RequestError:
        return {
            "ok": False,
            "mensaje": (
                "No se pudo conectar con el servicio del modelo. "
                "Compruebe que el API esté encendido y que MODELO_URL apunte a ese endpoint."
            ),
        }

    if respuesta.status_code == 422:
        return {
            "ok": False,
            "mensaje": "El API rechazó los datos. Revise números negativos, vacíos o una categoría que el modelo no conoce.",
            "detalle": respuesta.text,
        }
    if respuesta.status_code >= 400:
        return {
            "ok": False,
            "mensaje": f"El API respondió con un error {respuesta.status_code}.",
            "detalle": respuesta.text[:500],
        }
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return {
            "ok": False,
            "mensaje": "El API respondió, pero el contenido no es JSON válido.",
        }
    if not isinstance(cuerpo, dict) or not cuerpo.get("predicciones"):
        return {
            "ok": False,
            "mensaje": "La respuesta llegó, pero no trae una predicción utilizable.",
        }
    return {"ok": True, "predicciones": cuerpo["predicciones"]}


@app.get("/salud")
def salud():
    return {"aplicacion": "consulta", "modelo_url": MODELO_URL}


@app.get("/", response_class=HTMLResponse)
def formulario(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"resultado": None, "modelo_url": MODELO_URL, "enviado": None},
    )


@app.post("/", response_class=HTMLResponse)
def enviar(
    request: Request,
    total_vistas: int = Form(...),
    total_carritos: int = Form(...),
    total_remociones: int = Form(...),
    total_compras: int = Form(...),
    ticket_promedio: float = Form(...),
    sesiones: int = Form(...),
    categorias_distintas: int = Form(...),
    tasa_conversion: float = Form(...),
    categoria_principal: str = Form(...),
):
    payload = {
        "instancias": [{
            "total_vistas": total_vistas,
            "total_carritos": total_carritos,
            "total_remociones": total_remociones,
            "total_compras": total_compras,
            "ticket_promedio": ticket_promedio,
            "sesiones": sesiones,
            "categorias_distintas": categorias_distintas,
            "tasa_conversion": tasa_conversion,
            "categoria_principal": categoria_principal.strip(),
        }]
    }
    resultado = consultar_modelo(payload)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "resultado": resultado,
            "modelo_url": MODELO_URL,
            "enviado": payload["instancias"][0],
        },
    )
