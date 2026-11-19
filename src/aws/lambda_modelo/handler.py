"""API de perfiles, Swagger, silueta y pantalla de consulta. Solo biblioteca estándar."""

import base64
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
MODELO = json.loads((BASE / "modelo.json").read_text(encoding="utf-8"))
PAGINAS = BASE / "paginas"
ESTATICOS = BASE / "estaticos"

LIMITES = {
    "total_vistas": (0, 1_000_000, True),
    "total_carritos": (0, 1_000_000, True),
    "total_remociones": (0, 1_000_000, True),
    "total_compras": (0, 1_000_000, True),
    "ticket_promedio": (0, 1_000_000, False),
    "sesiones": (0, 1_000_000, True),
    "categorias_distintas": (0, 100, True),
    "tasa_conversion": (0, 100, False),
}

CABECERAS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def responder(codigo, cuerpo, tipo="application/json; charset=utf-8"):
    if not isinstance(cuerpo, str):
        cuerpo = json.dumps(cuerpo, ensure_ascii=False)
    cabeceras = dict(CABECERAS)
    cabeceras["Content-Type"] = tipo
    return {"statusCode": codigo, "headers": cabeceras, "body": cuerpo}


def raiz_de(evento):
    ruta = evento.get("rawPath") or "/"
    for sufijo in ("/docs", "/silueta", "/consulta", "/openapi.json", "/predecir", "/salud"):
        if ruta.endswith(sufijo):
            return ruta[: -len(sufijo)]
    return ""


def pagina(nombre, evento, reemplazos=None):
    texto = (PAGINAS / nombre).read_text(encoding="utf-8")
    texto = texto.replace("{{RAIZ}}", raiz_de(evento))
    for clave, valor in (reemplazos or {}).items():
        texto = texto.replace("{{" + clave + "}}", valor)
    return responder(200, texto, "text/html; charset=utf-8")


def html_celda(texto):
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def pagina_silueta(evento):
    metrica = MODELO["metrica"]
    elegido = int(metrica["k_elegido"])
    siluetas = metrica["silueta_por_k"]
    mayor = max(float(valor) for valor in siluetas.values()) or 1
    filas = []
    for grupos, valor in siluetas.items():
        numero = float(valor)
        ancho = max(0, round(100 * numero / mayor))
        clase = ' class="gana"' if int(grupos) == elegido else ""
        filas.append(
            f"<tr{clase}><td>{html_celda(grupos)}</td><td>{numero:.4f}</td>"
            f'<td><div class="barra" style="width:{ancho}%"></div></td></tr>'
        )
    return pagina("silueta.html", evento, {
        "JUSTIFICACION": html_celda(metrica["justificacion"]),
        "K": str(elegido),
        "SILUETA": f"{float(siluetas[str(elegido)]):.4f}",
        "FILAS": f"{int(metrica['filas_muestra']):,}".replace(",", " "),
        "CLIENTES": f"{int(metrica['clientes']):,}".replace(",", " "),
        "FILAS_TABLA": "\n".join(filas),
    })


def contrato(evento):
    cabeceras = {clave.lower(): valor for clave, valor in (evento.get("headers") or {}).items()}
    host = cabeceras.get("host", "")
    protocolo = cabeceras.get("x-forwarded-proto", "https")
    servidor = f"{protocolo}://{host}{raiz_de(evento)}" if host else ""
    categorias = MODELO["categorias"]
    propiedades = {}
    for campo, (minimo, maximo, entero) in LIMITES.items():
        propiedades[campo] = {
            "type": "integer" if entero else "number",
            "minimum": minimo,
            "maximum": maximo,
        }
    propiedades["categoria_principal"] = {
        "type": "string",
        "minLength": 1,
        "maxLength": 80,
        "enum": categorias,
    }
    documento = {
        "openapi": "3.0.3",
        "info": {
            "title": "Perfiles de clientes de la tienda",
            "version": "1.0.0",
            "description": (
                "Agrupa un cliente de la tienda multicategoría en un perfil. "
                "El modelo es K-Means. El número de grupos se eligió con el coeficiente de silueta."
            ),
        },
        "paths": {
            "/predecir": {
                "post": {
                    "operationId": "predecir",
                    "summary": "Asignar un perfil a uno o más clientes",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["instancias"],
                                    "properties": {
                                        "instancias": {
                                            "type": "array",
                                            "minItems": 1,
                                            "maxItems": 100,
                                            "items": {
                                                "type": "object",
                                                "required": list(LIMITES) + ["categoria_principal"],
                                                "properties": propiedades,
                                            },
                                        }
                                    },
                                },
                                "examples": {
                                    "explorador": {
                                        "summary": "Mira y no compra",
                                        "value": {
                                            "instancias": [{
                                                "total_vistas": 30,
                                                "total_carritos": 0,
                                                "total_remociones": 0,
                                                "total_compras": 0,
                                                "ticket_promedio": 0,
                                                "sesiones": 4,
                                                "categorias_distintas": 3,
                                                "tasa_conversion": 0,
                                                "categoria_principal": "electronics",
                                            }]
                                        },
                                    },
                                    "comprador": {
                                        "summary": "Compra varias veces",
                                        "value": {
                                            "instancias": [{
                                                "total_vistas": 12,
                                                "total_carritos": 2,
                                                "total_remociones": 0,
                                                "total_compras": 3,
                                                "ticket_promedio": 40,
                                                "sesiones": 4,
                                                "categorias_distintas": 2,
                                                "tasa_conversion": 0.25,
                                                "categoria_principal": "electronics",
                                            }]
                                        },
                                    },
                                },
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Perfil de cada cliente"},
                        "422": {"description": "Datos fuera de las reglas o categoría desconocida"},
                    },
                }
            },
            "/salud": {"get": {"summary": "Estado del servicio", "responses": {"200": {"description": "Listo"}}}},
            "/silueta": {"get": {"summary": "Coeficiente de silueta ya calculado", "responses": {"200": {"description": "Página"}}}},
        },
    }
    if servidor:
        documento["servers"] = [{"url": servidor}]
    return responder(200, documento)


def es_entero(valor):
    return type(valor) is int


def es_numero(valor):
    return type(valor) in (int, float) and valor == valor and valor not in (float("inf"), float("-inf"))


def validar_instancia(item, indice):
    if not isinstance(item, dict):
        return f"La instancia {indice} no es un objeto."
    for campo, (minimo, maximo, entero) in LIMITES.items():
        if campo not in item:
            return f"Falta el campo {campo}."
        valor = item[campo]
        if entero:
            if not es_entero(valor):
                return f"{campo} debe ser un entero."
        elif not es_numero(valor):
            return f"{campo} debe ser un número."
        if valor < minimo or valor > maximo:
            return f"{campo} debe estar entre {minimo} y {maximo}."
    if "categoria_principal" not in item:
        return "Falta el campo categoria_principal."
    categoria = item["categoria_principal"]
    if not isinstance(categoria, str) or not categoria.strip() or len(categoria) > 80:
        return "categoria_principal debe ser un texto de 1 a 80 caracteres."
    return ""


def predecir_fila(valores):
    codigo = MODELO["categorias"].index(valores["categoria_principal"])
    cruda = []
    for columna in MODELO["columnas"]:
        if columna == "categoria_principal":
            cruda.append(float(codigo))
        else:
            cruda.append(float(valores[columna]))
    escalada = []
    for valor, media, escala in zip(cruda, MODELO["media"], MODELO["escala"]):
        escalada.append(0.0 if escala == 0 else (valor - media) / escala)
    mejor = 0
    mejor_distancia = None
    for indice, centro in enumerate(MODELO["centroides"]):
        distancia = sum((punto - referencia) ** 2 for punto, referencia in zip(escalada, centro))
        if mejor_distancia is None or distancia < mejor_distancia:
            mejor = indice
            mejor_distancia = distancia
    return mejor


def predecir(evento):
    try:
        cuerpo = json.loads(evento.get("body") or "")
    except json.JSONDecodeError:
        return responder(422, {"detail": "El cuerpo no es JSON válido."})
    if not isinstance(cuerpo, dict) or "instancias" not in cuerpo:
        return responder(422, {"detail": "El cuerpo debe incluir la lista instancias."})
    instancias = cuerpo["instancias"]
    if not isinstance(instancias, list) or not 1 <= len(instancias) <= 100:
        return responder(422, {"detail": "instancias debe tener entre 1 y 100 clientes."})

    for indice, item in enumerate(instancias, start=1):
        error = validar_instancia(item, indice)
        if error:
            return responder(422, {"detail": error})

    desconocidas = sorted({
        item["categoria_principal"]
        for item in instancias
        if item["categoria_principal"] not in MODELO["categorias"]
    })
    if desconocidas:
        return responder(422, {
            "detail": {
                "mensaje": "Hay categorías que el modelo no vio en el entrenamiento.",
                "categorias_desconocidas": desconocidas,
                "categorias_validas": MODELO["categorias"],
            }
        })

    predicciones = []
    for item in instancias:
        grupo = predecir_fila(item)
        ficha = MODELO["perfiles"].get(
            str(grupo),
            {"nombre": f"Grupo {grupo}", "descripcion": "Sin descripción"},
        )
        predicciones.append({
            "cluster": grupo,
            "perfil": ficha["nombre"],
            "descripcion": ficha["descripcion"],
        })
    return responder(200, {"predicciones": predicciones})


def archivo_estatico(nombre, tipo):
    ruta = ESTATICOS / nombre
    if not ruta.is_file():
        return responder(404, {"detail": "No está el archivo de Swagger."})
    return responder(200, ruta.read_text(encoding="utf-8"), tipo)


def preparar(evento):
    if not isinstance(evento, dict):
        evento = {}
    if evento.get("rawPath") and (evento.get("requestContext") or {}).get("http"):
        return evento
    contexto_original = evento.get("requestContext") or {}
    ruta = evento.get("path") or evento.get("rawPath") or "/"
    etapa = contexto_original.get("stage") or ""
    if etapa and etapa != "$default":
        prefijo = "/" + etapa
        if ruta == prefijo:
            ruta = "/"
        elif ruta.startswith(prefijo + "/"):
            ruta = ruta[len(prefijo):]
    metodo = evento.get("httpMethod") or (contexto_original.get("http") or {}).get("method") or "GET"
    cuerpo = evento.get("body")
    if evento.get("isBase64Encoded") and isinstance(cuerpo, str):
        cuerpo = base64.b64decode(cuerpo).decode("utf-8")
    return {
        "rawPath": ruta or "/",
        "headers": evento.get("headers") or {},
        "body": cuerpo,
        "requestContext": {"http": {"method": metodo}, "stage": etapa},
    }


def handler(evento, contexto):
    evento = preparar(evento)
    metodo = (evento.get("requestContext") or {}).get("http", {}).get("method", "GET").upper()
    ruta = evento.get("rawPath") or "/"
    if metodo == "OPTIONS":
        return responder(204, "")
    if ruta.endswith("/predecir") and metodo == "POST":
        return predecir(evento)
    if ruta.endswith("/openapi.json") and metodo == "GET":
        return contrato(evento)
    if ruta.endswith("/docs") and metodo == "GET":
        return pagina("docs.html", evento)
    if ruta.endswith("/silueta") and metodo == "GET":
        return pagina_silueta(evento)
    if ruta.endswith("/salud") and metodo == "GET":
        return responder(200, {"estado": "listo"})
    if ruta.endswith("/swagger-ui.css") and metodo == "GET":
        return archivo_estatico("swagger-ui.css", "text/css; charset=utf-8")
    if ruta.endswith("/swagger-ui-bundle.js") and metodo == "GET":
        return archivo_estatico("swagger-ui-bundle.js", "text/javascript; charset=utf-8")
    if metodo == "GET" and (ruta in ("/", "") or ruta.rstrip("/").endswith("/consulta")):
        return pagina("consulta.html", evento)
    return responder(404, {"detail": "Ruta no encontrada."})
