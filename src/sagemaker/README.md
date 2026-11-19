# Perfiles de usuarios con K-Means — eventos Open CDP + AWS

Segmenta usuarios de una tienda multicategoría a partir de sus eventos (vistas, carrito y compras). Cada evento relaciona un usuario con un producto. Los datos son del proyecto abierto Open CDP.

Cuenta: **SalmiBecerra** (`323884514768`). Región: **us-east-2**. Bucket: `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026`.

Notebook: `perfiles.ipynb`.

## Arquitectura

```
Athena (SQL) → S3 gold → SageMaker Studio (K-Means) → API con silueta, Swagger y consulta
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

SageMaker Studio es el lugar donde se abre el cuaderno y se entrena el agrupamiento. Hay que dejarlo listo una sola vez. Mientras el espacio JupyterLab esté en **Running**, se cobra aunque no esté ejecutando celdas. Al terminar, deténgalo.

Antes de crear nada, mire la esquina superior derecha de la consola. La región tiene que ser **Ohio (us-east-2)**. Si dice Norte de Virginia, cámbiela. Un dominio creado en otra región no ve este bucket.

### 2.1 Entrar a Dominios

1. En el buscador de la consola escriba **SageMaker** y abra **Amazon SageMaker AI**.
2. En el menú izquierdo abra **Dominios** (en inglés, **Domains**).
3. Mire la lista.
   - Si ya hay un dominio en estado **InService** o **Listo**, no cree otro. Siga en **2.3**.
   - Si la lista está vacía, siga en **2.2**.

### 2.2 Crear el dominio

1. Pulse **Crear dominio** (**Create domain**).
2. Elija **Configuración rápida** (**Quick setup**). Sirve para una sola persona. No use la configuración estándar.
3. Escriba el nombre: `dominio-ecommerce-salmi`.
4. En el rol de ejecución:
   - Si aparece `GlueETLEcommerceRole`, selecciónelo. Ese rol ya puede leer el bucket, Athena y Glue, y SageMaker puede asumirlo.
   - Si no aparece, elija **Crear un rol nuevo**. Anote el nombre que genere AWS, parecido a `AmazonSageMaker-ExecutionRole-...`. Después, en IAM, ábralo y adjunte `AmazonS3FullAccess`, `AmazonAthenaFullAccess` y `AWSGlueConsoleFullAccess`. Sin eso el cuaderno no lee las tablas de oro.
5. Deje la red como viene en la configuración rápida. Así el cuaderno puede instalar librerías.
6. Pulse **Crear dominio** y espere. Puede tardar de 5 a 15 minutos. No cierre la pestaña. Siga solo cuando el estado sea **InService**.

### 2.3 Abrir Studio

1. En **Dominios**, pulse el nombre del dominio.
2. Abra la pestaña **Perfiles de usuario** (**User profiles**). La configuración rápida ya creó uno.
3. En ese perfil pulse **Lanzar** (**Launch**) y luego **Studio**.
4. Espere a que cargue la página de inicio de Studio. La primera vez tarda un par de minutos.

### 2.4 Crear el espacio de JupyterLab

1. En el inicio de Studio elija **JupyterLab**.
2. Pulse **Crear espacio de JupyterLab** (**Create JupyterLab space**).
3. Nombre: `espacio-perfiles-ecommerce`.
4. Confirme la creación. Todavía no está encendido.
5. En la configuración del espacio elija la instancia **ml.t3.medium**. No use una instancia mayor: esta alcanza para el cuaderno y es la más barata de este flujo.
6. Deje el almacenamiento en el valor que propone la consola.
7. Pulse **Ejecutar espacio** (**Run space**). Espere a que el estado pase a **Running**. Suele tardar de 2 a 5 minutos.
8. Pulse **Abrir JupyterLab** (**Open JupyterLab**).

### 2.5 Abrir el cuaderno

1. En JupyterLab, menú **File → Upload** y suba `perfiles.ipynb`. También puede arrastrar el archivo a la lista de la izquierda.
2. Ábralo con doble clic.
3. Arriba a la derecha pulse el nombre del kernel y elija **Python 3 (ipykernel)**. Si pide instalar el kernel, acepte.
4. Ya puede ejecutar las celdas desde el paso 3. No ejecute todavía el despliegue del endpoint del paso 10: ese recurso cobra por hora hasta que se borre.

### 2.6 Apagarlo al terminar

1. Vuelva a la pestaña del espacio `espacio-perfiles-ecommerce`.
2. Pulse **Detener** (**Stop**).
3. El dominio puede quedarse creado. Lo que cobra por hora es el espacio mientras está en **Running**.

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

## Paso 12 — Publicar silueta, Swagger y la consulta

No cree el endpoint del paso 10 para la exposición. Cobra por hora aunque nadie lo use.

La silueta, Swagger y la pantalla de consulta se publican con la pila de CloudFormation descrita en [src/aws/README.md](../aws/README.md). Esas tres direcciones quedan encendidas. La pantalla llama al API; no abre el archivo del modelo. Swagger muestra el contrato y rechaza con 422 un número negativo o una categoría que el modelo no conoce.

El paso 8 del notebook deja los archivos del modelo en la carpeta del cuaderno. Si vuelve a entrenar, `src/aws/extraer_modelo.py` actualiza el JSON que usa la función. Si todavía no ejecutó el notebook, el repositorio ya trae la muestra de octubre: k = 2 y silueta 0.6625.

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
