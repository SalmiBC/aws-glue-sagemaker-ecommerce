# JOB BRONZE - Carga de eventos de e-commerce

Cada fila del archivo es un evento entre un usuario y un producto de la tienda multicategoría (Open CDP).

Cuenta: **SalmiBecerra** (`323884514768`). Región: **us-east-2**. Bucket: `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026`.

Script: `job-bronze-ecommerce.py`.

## Paso 1: Crear el Job de Glue para Bronze

1. Acceda a **AWS Glue** en **us-east-2**.
2. En el menú lateral, seleccione **ETL jobs**.
3. Haga clic en **Script editor**.
4. Configure:
   - **Motor:** Spark
   - **Opciones:** Start fresh
   - Haga clic en **Create**
5. Pegue el contenido de `src/bronze/job-bronze-ecommerce.py`.

## Paso 2: Configurar los detalles del Job

En la pestaña **Job details**:

**Información básica:**
- **Nombre:** `job-bronze-ecommerce`
- **Rol de IAM:** `GlueETLEcommerceRole`
- **Tipo:** Spark
- **Versión de Glue:** 5.0
- **Lenguaje:** Python 3

**Configuración de recursos:**
- **Tipo de worker:** G.1X
- **Número de workers:** 10
- **Tiempo de espera del trabajo:** 480 minutos

## Paso 3: Agregar parámetros del Job

| Clave | Valor |
|-------|-------|
| `--BUCKET` | `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026` |
| `--BRONZE_PATH` | `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/bronze/` |

El job lee `bronze/ecommerce_behavior_events.csv.gz` y escribe `bronze/ECOMMERCE_DATA_BRONZE_PARQUET/`, particionado por `year_partition` (año de `event_time`).

## Paso 4: Agregar etiquetas

- **Clave:** `workshop` — **Valor:** `big_data`
- **Clave:** `proyecto` — **Valor:** `ecommerce-opencdp`
- **Clave:** `cuenta` — **Valor:** `SalmiBecerra`

## Paso 5: Guardar y ejecutar

1. **Save**.
2. **Run**.
3. Espere a que el estado sea **Succeeded** antes de crear el crawler. Con el extracto de octubre 2019 el job puede tardar varios minutos.

# Crawlear capa Bronze

## Paso 1: Acceder a AWS Glue

1. **AWS Glue** en **us-east-2**.
2. **Crawlers → Create crawler**.

## Paso 2: Propiedades del Crawler

1. **Name:** `crawler-bronze-ecommerce`
2. **Description:** `Cataloga los eventos crudos de la tienda multicategoría en la capa bronze`
3. **Tags:** `workshop` = `big_data`, `proyecto` = `ecommerce-opencdp`, `cuenta` = `SalmiBecerra`
4. **Next**

## Paso 3: Origen de datos

1. **Add a data source**
2. Configure:
   - **Data source:** S3
   - **S3 path:** `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/bronze/ECOMMERCE_DATA_BRONZE_PARQUET/`
   - **Subsequent crawler runs:** Crawl all sub-folders
3. **Add an S3 data source**
4. **Next**

## Paso 4: Rol de IAM

**Existing IAM role:** `GlueETLEcommerceRole`

## Paso 5: Destino

1. **Target database:** `db_ecommerce`
2. **Table name prefix:** `bronze_`
3. **Crawler schedule:** On demand
4. **Next**

## Paso 6: Revisar y crear

- Nombre: `crawler-bronze-ecommerce`
- Data source: `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/bronze/ECOMMERCE_DATA_BRONZE_PARQUET/`
- IAM role: `GlueETLEcommerceRole`
- Target database: `db_ecommerce`
- Table prefix: `bronze_`

**Create crawler**.

## Paso 7: Ejecutar el Crawler

1. Seleccione `crawler-bronze-ecommerce`.
2. **Run**.
3. Espere el estado **Ready**. Tiempo estimado: 1-2 minutos.

## Paso 8: Verificar la tabla

1. **Data Catalog → Tables**.
2. Filtre por `db_ecommerce`.
3. Debe existir `bronze_ecommerce_data_bronze_parquet`.
4. En la tabla revise:
   - **Esquema:** `event_time`, `event_type`, `product_id`, `category_id`, `category_code`, `brand`, `price`, `user_id`, `user_session`
   - **Partition keys:** `year_partition`
   - **Location:** ruta bronze en S3
   - **Classification:** parquet
