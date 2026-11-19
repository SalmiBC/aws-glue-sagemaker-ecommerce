# Silueta, Swagger y consulta en AWS

Estas tres páginas quedan publicadas en la cuenta **SalmiBecerra** (`323884514768`), región **us-east-2**. No hay que encender SageMaker, ni Docker, ni un programa en la computadora. Se abren con el navegador.

No usan un endpoint de SageMaker. Ese endpoint cobra por hora aunque nadie lo consulte. Aquí el modelo responde dentro de una función que solo se ejecuta cuando alguien pregunta, y las páginas viven en el mismo servicio.

| Página | Ruta | Qué muestra |
|---|---|---|
| Silueta | `/silueta` | El coeficiente ya calculado. Con la muestra de octubre gana **k = 2**, silueta **0.6625**. Explica por qué no se usa F1. |
| Swagger | `/docs` | El contrato del API. `POST /predecir` valida números y categoría. Un negativo o una categoría desconocida responden **422**. El JSON del contrato está en `/openapi.json`. |
| Consulta | `/consulta` | El formulario. No guarda el modelo: llama a `/predecir`. Si el servicio tarda más de 8 segundos, responde mal o no trae `predicciones`, la pantalla lo dice. |

La pantalla de inicio, `/`, es la misma consulta.

## Publicarlas una sola vez

El paquete de la función ya está en:

`s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/modelos/kmeans/lambda/perfiles-ecommerce.zip`

La plantilla que crea el permiso, la función y el API es `src/aws/plantilla.yaml`.

Hay que hacerlo con un usuario que pueda crear roles en IAM. El usuario `cli-rues` puede subir archivos al bucket, pero AWS le niega `iam:CreateRole`. Por eso este paso se hace en la consola, con quien administra la cuenta.

1. Entre a la consola de la cuenta SalmiBecerra. Arriba a la derecha la región tiene que ser **Ohio (us-east-2)**.
2. Abra **CloudFormation → Create stack → With new resources**.
3. Elija **Upload a template file** y suba `src/aws/plantilla.yaml`.
4. Nombre de la pila: `perfiles-ecommerce`. Pulse siguiente hasta crear la pila. No cambie parámetros: no tiene.
5. Espere a que el estado sea **CREATE_COMPLETE**. Tarda cerca de un minuto.
6. Abra la pestaña **Outputs**. Ahí están las tres direcciones: Silueta, Swagger y Consulta.

A partir de ese momento las páginas siguen disponibles. No hay un espacio de Studio que detener ni un endpoint que borrar para estas tres.

## Qué mostrar

En **Silueta**, señale la fila de 2 grupos y el número 0.6625. Diga que se probaron de 2 a 8 grupos y se quedó el más alto, porque no existe una etiqueta verdadera por cliente.

En **Swagger**, abra `POST /predecir` y en los ejemplos elija **Mira y no compra**, luego **Compra varias veces**. El grupo cambia. Después ponga `total_vistas` en `-1` y muestre el 422.

En **Consulta**, pulse **Probar explorador** y después **Probar comprador**. Si solo cambia las vistas o la categoría y deja 2 compras o 4 carritos, el perfil sigue igual: en el entrenamiento casi nadie compraba, y esas dos cifras ya están del lado de Compradores frecuentes. Luego escriba `no-existe` en la categoría: la pantalla dice que el API rechazó los datos.

## Volver a publicar si cambia el modelo

Desde la carpeta del repositorio, con un usuario que sí pueda crear la función:

```powershell
py -3 src/aws/extraer_modelo.py
powershell -ExecutionPolicy Bypass -File src/aws/desplegar.ps1
```

`extraer_modelo.py` lee los archivos de `src/api/artefactos/` y escribe el JSON que usa la función. No hace falta empaquetar scikit-learn: la función solo guarda los centros de los grupos, la escala y las categorías, y asigna cada cliente al centro más cercano.

## Costo

La función y el API se cobran por consulta. Una exposición entra en la capa gratuita. No deje creado el endpoint `kmeans-perfiles-ecommerce` de SageMaker: ese sí cobra por hora.

## Probar el mismo servicio en local

`py -3 src/aws/probar_local.py` compara las respuestas con el modelo de scikit-learn y revisa la validación, la silueta, Swagger y la pantalla. Las guías de [src/api/README.md](../api/README.md) y [src/consulta/README.md](../consulta/README.md) siguen sirviendo para encender una copia en la computadora. Para la exposición use las direcciones de la pila.
