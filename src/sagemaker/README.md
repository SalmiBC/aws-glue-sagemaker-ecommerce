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

## Paso 5 — Elegir el número de clusters

El notebook grafica la inercia para k de 2 a 9 (método del codo) y guarda `elbow_curve.png`.

## Paso 6 — Entrenar K-Means

Valor inicial: `K_OPTIMO = 4`. Ajuste ese número según la gráfica.

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

## Paso 12 — API REST (opcional)

1. Lambda `kmeans-perfiles-ecommerce-invoker`, runtime Python 3.12, rol `GlueETLEcommerceRole`.
2. El rol ya confía en `lambda.amazonaws.com`. Agregue permiso para `sagemaker:InvokeEndpoint` si la política de SageMaker del rol no lo cubre en su cuenta.
3. API Gateway REST, nombre `kmeans-perfiles-ecommerce-api`, regional.
4. Recurso `/predecir`, método POST, integración Lambda.
5. Stage `prod`.

```bash
curl.exe -X POST https://<api-id>.execute-api.us-east-2.amazonaws.com/prod/predecir -H "Content-Type: application/json" -d "{\"instancias\": [[10, 2, 0, 1, 40.0, 3, 2, 0.1, 0]]}"
```

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
