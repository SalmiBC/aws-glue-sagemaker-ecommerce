# Publicar el API del modelo

La publicación que se usa en la exposición está en AWS: la silueta, Swagger y la pantalla de consulta salen de la misma función. Esa guía está en [src/aws/README.md](../aws/README.md). No hay que dejar esta copia encendida en la computadora.

Lo que sigue sirve para probar el mismo contrato en local. Valida cada entrada y publica Swagger en `/docs` y el contrato OpenAPI en `/openapi.json`.

La aplicación de consulta local está en [src/consulta/README.md](../consulta/README.md).

Cuenta del proyecto: **SalmiBecerra** (`323884514768`).

## Paso 1: Conseguir los archivos del modelo

Elija una de las dos rutas.

**Ruta A. Ya ejecutó el notebook de SageMaker hasta el paso 8.**  
Ese paso copia los artefactos a `src/api/artefactos/`. Deben existir:

- `kmeans_model.joblib`
- `scaler.joblib`
- `encoders.joblib`
- `perfiles.json`
- `columnas.json`

**Ruta B. Todavía no ejecutó el notebook.**  
Desde la carpeta `src/api`, con el CSV de octubre accesible en el proyecto:

```bash
py -3 -m pip install -r requirements.txt
py -3 entrenar_muestra.py
```

El script lee 200.000 eventos del inicio de octubre de 2019, aplica el mismo recorte de precios y elige el número de grupos con el coeficiente de silueta. Es una muestra, no los siete meses.

## Paso 2: Instalar y encender el API

En `src/api`:

```bash
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Deje esa ventana abierta.

## Paso 3: Abrir la documentación

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

En Swagger, `POST /predecir` muestra los campos obligatorios y los límites. Un número negativo, una lista vacía o una categoría que el modelo no conoce responden **422** y no entran al modelo.

## Paso 4: Probar una consulta válida

En Swagger hay dos ejemplos: **Mira y no compra** y **Compra varias veces**. El primero responde Exploradores. El segundo, Compradores frecuentes.

El grupo lo mueven las compras y el carrito. En la muestra casi nadie compraba, así que 2 compras o 4 carritos ya quedan del lado de Compradores frecuentes. Cambiar solo las vistas, el ticket o la categoría no alcanza para salir de ese grupo.

```bash
curl.exe -X POST http://127.0.0.1:8000/predecir -H "Content-Type: application/json" -d "{\"instancias\":[{\"total_vistas\":30,\"total_carritos\":0,\"total_remociones\":0,\"total_compras\":0,\"ticket_promedio\":0,\"sesiones\":4,\"categorias_distintas\":3,\"tasa_conversion\":0,\"categoria_principal\":\"electronics\"}]}"
```

La respuesta trae `cluster`, `perfil` y `descripcion`.

## Paso 5: Contenedor, si prefiere Docker

Desde la raíz del repositorio, después del paso 1:

```bash
docker compose up --build
```

El API queda en el puerto 8000 y la pantalla de consulta en el puerto 8080. La pantalla llama a `http://modelo:8000`. No copia el modelo.

## Qué valida el API

| Campo | Regla |
|---|---|
| Conteos (`total_vistas`, carritos, remociones, compras, sesiones, categorías) | Entero entre 0 y el máximo indicado en Swagger |
| `ticket_promedio` y `tasa_conversion` | Número mayor o igual a 0 |
| `categoria_principal` | Texto que exista en el entrenamiento |
| `instancias` | Entre 1 y 100 clientes por llamada |
