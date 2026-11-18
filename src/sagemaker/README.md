# Perfiles de usuarios con K-Means — eventos Open CDP + AWS

Segmenta usuarios de una tienda multicategoría a partir de sus eventos (vistas, carrito y compras). Cada evento relaciona un usuario con un producto. Los datos son del proyecto abierto Open CDP.

Cuenta: **SalmiBecerra** (`323884514768`). Región: **us-east-2**. Bucket: `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026`.

Notebook: `perfiles.ipynb`.

## Arquitectura

```
Athena (SQL) → S3 gold → SageMaker Studio (K-Means) → Endpoint
Glue Catalog db_ecommerce sostiene las tablas que Athena consulta.
```

## Pre-requisitos

| Requisito | Detalle |
|---|---|
| Cuenta | SalmiBecerra, `323884514768`, región `us-east-2` |
| Bucket | `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026` |
| Base Glue | `db_ecommerce` con `gold_dim_usuario`, `gold_dim_producto` y `gold_fact_evento` |
| Rol | `GlueETLEcommerceRole` con Glue, S3, CloudWatch, SageMaker y Athena. Trust policy de Glue, SageMaker y Lambda (fase 2 del README principal) |

## Paso 1 — Consulta en Athena

En Athena, región **us-east-2**, elija un query result location:

`s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/athena-results/`

```sql
SELECT
    user_id,
    total_vistas,
    total_carritos,
    total_remociones,
    total_compras,
    COALESCE(ticket_promedio, 0) AS ticket_promedio,
    sesiones,
    categorias_distintas,
    tasa_conversion,
    categoria_principal
FROM "db_ecommerce"."gold_dim_usuario"
WHERE total_eventos > 0
  AND total_vistas IS NOT NULL
ORDER BY RAND()
LIMIT 100000;
```

## Paso 2 — Configurar SageMaker Studio

1. **AWS Console → SageMaker → Studio**, región **us-east-2**.
2. Abra o cree un dominio.
3. Lance **Studio**.
4. Cree un JupyterLab space con instancia `ml.t3.medium`.
5. Abra el notebook `perfiles.ipynb` con el kernel `python3 (ipykernel)`.
6. Use el rol `GlueETLEcommerceRole` como rol de ejecución del dominio o del space.

## Paso 3 — Leer datos desde Athena

El notebook instala `sagemaker==2.232.2`, `awswrangler` y `scikit-learn`, reinicia el kernel y ejecuta la consulta del paso 1 contra `db_ecommerce`.

## Paso 4 — Preparar datos para K-Means

Variables numéricas:

- `total_vistas`
- `total_carritos`
- `total_remociones`
- `total_compras`
- `ticket_promedio`
- `sesiones`
- `categorias_distintas`
- `tasa_conversion`

`categoria_principal` se codifica con `LabelEncoder`. Todas las variables se escalan con `StandardScaler`.

## Definición del problema y métrica

| Pregunta | Respuesta |
|---|---|
| Tipo de tarea | Agrupamiento (clustering). No es clasificación ni regresión: no existe una etiqueta correcta por cliente |
| Qué se quiere | Juntar clientes que se parecen en vistas, carrito, compras, ticket y conversión |
| Métrica principal | Coeficiente de silueta. Va de -1 a 1. Un valor más alto significa grupos compactos y separados |
| Por qué no F1 | F1 compara una predicción contra una clase verdadera. Aquí no hay clase verdadera |
| Cómo se elige k | Se prueba k de 2 a 8 sobre una muestra de hasta 8.000 clientes y se queda la k con mayor silueta. La gráfica del codo solo ayuda a mirar el resultado |

Antes de escalar, las variables numéricas se recortan al percentil 1 y al percentil 99. Un cliente con un volumen imposible no debe formar un grupo él solo. La categoría se codifica con `LabelEncoder` y todas las columnas se escalan con `StandardScaler`.

## Paso 5 — Elegir el número de clusters

El notebook imprime la silueta de cada k, elige `K_OPTIMO` y guarda `elbow_curve.png`.

## Paso 6 — Entrenar K-Means

Usa el `K_OPTIMO` del paso 5. No vuelva a fijarlo a mano, salvo que quiera comparar otro k.

## Paso 7 — Interpretar perfiles

El resumen por cluster usa volumen de vistas, carritos, compras, ticket promedio y tasa de conversión. Nombres de partida, para revisarlos con el resultado real:

| Cluster | Perfil | Lectura |
|---|---|---|
| 0 | Exploradores | Muchas vistas y poca compra |
| 1 | Compradores frecuentes | Compras repetidas y conversión alta |
| 2 | Abandonan el carrito | Llevan productos al carrito y no compran |
| 3 | Alto valor | Pocas compras con ticket promedio alto |

## Paso 8 — Guardar el modelo en S3

Artefactos en:

`s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/modelos/kmeans/model.tar.gz`

El CSV de perfiles queda en `modelos/kmeans/resultados/kmeans_perfiles.csv`.

## Paso 9 — Script de inferencia

El notebook escribe `inference.py`. La entrada es una lista de vectores ya codificados y escalados en el mismo orden de las variables del paso 4, más el código de `categoria_principal`.

## Paso 10 — Desplegar el endpoint

- Nombre: `kmeans-perfiles-ecommerce`
- Instancia: `ml.t2.medium`
- El despliegue tarda entre 3 y 5 minutos.

El endpoint cobra por hora aunque no reciba tráfico. Bórrelo al terminar.

## Paso 11 — Probar el endpoint

El notebook envía cuatro vectores de ejemplo y muestra el cluster, el perfil y la descripción.

## Paso 12 — Publicar el API y la aplicación de consulta

El endpoint de SageMaker es opcional y cobra por hora. El servicio que se documenta y se consulta es el API de este repositorio. Usted lo levanta siguiendo las guías. No hay que reescribirlo.

1. [src/api/README.md](../api/README.md). Publica el modelo como API REST con validación de entradas. Swagger queda en `/docs` y el contrato OpenAPI en `/openapi.json`.
2. [src/consulta/README.md](../consulta/README.md). La aplicación de consulta solo llama a esa URL. No abre el archivo del modelo. Atiende caídas, tiempos de espera y respuestas que no traen una predicción.

El paso 8 del notebook deja los archivos del modelo en la carpeta del cuaderno. El README del API indica dónde copiarlos. Si todavía no ejecutó el notebook, el mismo README tiene un entrenamiento de muestra con el CSV local.

## Costos y limpieza

```python
import boto3
sm_client = boto3.client('sagemaker', region_name='us-east-2')
sm_client.delete_endpoint(EndpointName='kmeans-perfiles-ecommerce')
sm_client.delete_endpoint_config(EndpointConfigName='kmeans-perfiles-ecommerce')
```

| Recurso | Tipo | Costo aprox. |
|---|---|---|
| SageMaker notebook | `ml.t3.medium` | ~$0.05/hora |
| SageMaker endpoint | `ml.t2.medium` | ~$0.05/hora |
| Athena | Por TB escaneado | ~$5/TB |
| S3 | Almacenamiento | ~$0.023/GB/mes |
| Glue jobs | G.1X, 10 workers | se cobra por DPU-hora mientras corren |
