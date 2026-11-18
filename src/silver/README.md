# JOB SILVER - Reglas de negocio de eventos de e-commerce

Limpia y enriquece los eventos de usuarios y productos de la tienda multicategoría (Open CDP). No borra filas inválidas: las reporta en el log.

Cuenta: **SalmiBecerra** (`323884514768`). Región: **us-east-2**. Bucket: `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026`.

Script: `job-silver-ecommerce.py`.

## Reglas de negocio

| Nº | Regla | Descripción | Implementación |
|----|--------|-------------|----------------|
| **RN-001** | Estandarización de fechas | `event_time` pasa a timestamp y se crea `event_date` en `YYYY-MM-DD` | Acepta `yyyy-MM-dd HH:mm:ss 'UTC'`. Valores no convertibles quedan NULL y van al log |
| **RN-002** | Limpieza de duplicados | Un evento por `user_id`, `user_session`, `event_time`, `event_type` y `product_id` | `dropDuplicates` sobre esas columnas |
| **RN-003** | Normalización de tipos | Unificar `event_type` y `brand` | Mayúsculas y trim. `view` → `VIEW`. Marca vacía → NULL. `category_code` en minúsculas |
| **RN-004** | Variables derivadas | Contexto temporal y precio numérico | `hora_evento`, `dia_semana`, `mes_evento` y `price` como double |
| **RN-005** | Enriquecimiento de categoría | Nombre legible de la categoría del producto | `category_root` es el primer segmento de `category_code`. Join con `catalogo_categorias_raiz.csv`. Raíz desconocida → log |
| **RN-006** | Llave única | Identificador del evento | `id_unico` = `user_id` + `product_id` + timestamp + `event_type`. Si falta un componente → log |
| **RN-007** | Registros inválidos | No se eliminan eventos | CSV en `logs/errors/` con columnas `columna`, `mensaje_error`, `valor` |
| **RN-008** | Código de tipo de evento | Código numérico del catálogo | Join con `catalogo_tipos_evento.csv`. Tipo desconocido → `codigo_evento` NULL y log |
| **RN-009** | Etapa del embudo | Cómo avanza el usuario frente al producto | `VIEW`→`VISTA`, `CART`→`CARRITO`, `REMOVE_FROM_CART`→`REMOCION`, `PURCHASE`→`COMPRA`. `flag_compra` = 1 solo en compra |
| **RN-010** | Nombres de columnas | snake_case | Minúsculas y guiones bajos |

## Crear el Job

1. **AWS Glue → ETL jobs → Script editor**, motor Spark, región **us-east-2**.
2. Pegue `src/silver/job-silver-ecommerce.py`.
3. **Job details:**
   - **Nombre:** `job-silver-ecommerce`
   - **Rol de IAM:** `GlueETLEcommerceRole`
   - **Versión de Glue:** 5.0
   - **Lenguaje:** Python 3
   - **Worker:** G.1X
   - **Workers:** 10
   - **Timeout:** 480 minutos
4. **Job parameters:**

| Parámetro | Valor |
|-----------|--------|
| `--BUCKET` | `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026` |
| `--BRONZE_PATH` | `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/bronze/` |
| `--SILVER_PATH` | `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/silver/` |
| `--CATALOGOS_PATH` | `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/bronze/catalogos/` |
| `--LOGS_PATH` | `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/logs/` |

5. **Tags:** `workshop` = `big_data`, `proyecto` = `ecommerce-opencdp`, `cuenta` = `SalmiBecerra`.
6. **Save** y **Run**. El job bronze debe haber terminado antes.

Salida: `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/silver/ECOMMERCE_DATA_SILVER_PARQUET/`, particionado por `year_partition`.

# Crawlear capa Silver

## Paso 1: Acceder a AWS Glue

**Crawlers → Create crawler** en **us-east-2**.

## Paso 2: Propiedades

1. **Name:** `crawler-silver-ecommerce`
2. **Description:** `Cataloga los eventos limpios de la tienda multicategoría en la capa silver`
3. **Tags:** `workshop` = `big_data`, `proyecto` = `ecommerce-opencdp`, `cuenta` = `SalmiBecerra`

## Paso 3: Origen

- **Data source:** S3
- **S3 path:** `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/silver/ECOMMERCE_DATA_SILVER_PARQUET/`
- **Subsequent crawler runs:** Crawl all sub-folders

## Paso 4: Rol

`GlueETLEcommerceRole`

## Paso 5: Destino

- **Target database:** `db_ecommerce`
- **Table name prefix:** `silver_`
- **Frequency:** On demand

## Paso 6: Crear

- Nombre: `crawler-silver-ecommerce`
- IAM role: `GlueETLEcommerceRole`
- Target database: `db_ecommerce`
- Table prefix: `silver_`

## Paso 7: Ejecutar

Seleccione `crawler-silver-ecommerce` y pulse **Run**. Espere el estado **Ready**.

## Paso 8: Verificar

En `db_ecommerce` debe existir `silver_ecommerce_data_silver_parquet`.

Revise:
- Columnas derivadas: `event_date`, `codigo_evento`, `descripcion_evento`, `etapa_funnel`, `flag_compra`, `category_root`, `categoria_nombre`, `hora_evento`, `dia_semana`, `mes_evento`, `id_unico`
- **Partition keys:** `year_partition`
- **Classification:** parquet

El job gold lee esta tabla por el catálogo. Si el crawler deja otro nombre, actualice `table_name` en `job-gold-ecommerce.py`.
