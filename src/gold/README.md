# JOB GOLD - Modelo dimensional de eventos de e-commerce

Esquema estrella de la tienda multicategoría (Open CDP). La tabla de hechos registra cada evento. Las dimensiones describen al usuario y al producto.

Cuenta: **SalmiBecerra** (`323884514768`). Región: **us-east-2**. Bucket: `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026`.

Script: `job-gold-ecommerce.py`.

## Parámetros del Job

| Parámetro | Valor |
|-----------|--------|
| `--BUCKET` | `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026` |
| `--SILVER_PATH` | `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/silver/` |
| `--GOLD_PATH` | `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/gold/` |

El job lee el catálogo `db_ecommerce.silver_ecommerce_data_silver_parquet`. Ejecute antes el crawler silver.

## Modelo dimensional

### Hechos: `fact_evento`

- **Propósito:** cada interacción de un usuario con un producto.
- **Granularidad:** un registro por evento.
- **Campos:** `id_unico`, `user_id` (FK), `product_id` (FK), `user_session`, `event_time`, `event_date`, `event_type`, `codigo_evento`, `descripcion_evento`, `etapa_funnel`, `flag_compra`, `price`, `hora_evento`, `dia_semana`, `mes_evento`, `category_root`.
- **Partición:** `event_type` (`VIEW`, `CART`, `REMOVE_FROM_CART`, `PURCHASE`).

### Dimensión: `dim_usuario`

- **Propósito:** perfil de comportamiento del usuario. SCD tipo 1.
- **Llave:** `user_id`.
- **Campos:** `total_eventos`, `total_vistas`, `total_carritos`, `total_remociones`, `total_compras`, `ticket_promedio`, `sesiones`, `categorias_distintas`, `tasa_conversion`, `categoria_principal`, `primera_actividad`, `ultima_actividad`.

### Dimensión: `dim_producto`

- **Propósito:** atributos del producto.
- **Llave:** `product_id`.
- **Campos:** `category_id`, `category_code`, `category_root`, `categoria_nombre`, `brand`, `precio_referencia`, `total_eventos_producto`, `total_compras_producto`.

## Configuración del Job en AWS Glue

**Información básica:**
- **Nombre:** `job-gold-ecommerce`
- **Rol de IAM:** `GlueETLEcommerceRole`
- **Tipo:** Spark
- **Versión de Glue:** 5.0
- **Lenguaje:** Python 3

**Recursos:**
- **Worker:** G.1X
- **Workers:** 10
- **Timeout:** 480 minutos

**Etiquetas:**
- `workshop` = `big_data`
- `proyecto` = `ecommerce-opencdp`
- `cuenta` = `SalmiBecerra`

Pegue `src/gold/job-gold-ecommerce.py`, guarde y ejecute después del crawler silver.

## Estructura resultante en S3

```
gold/
├── dim_usuario/
│   └── *.parquet
├── dim_producto/
│   └── *.parquet
└── fact_evento/
    ├── event_type=VIEW/
    ├── event_type=CART/
    ├── event_type=REMOVE_FROM_CART/
    └── event_type=PURCHASE/
```

## Características del modelo

1. Esquema estrella: `fact_evento` se une a `dim_usuario` por `user_id` y a `dim_producto` por `product_id`.
2. SCD tipo 1 en las dimensiones.
3. Hechos particionados por `event_type`.
4. Campos calculados: `flag_compra`, `tasa_conversion`, `ticket_promedio`, `precio_referencia`, `categoria_principal`.
5. Integridad: todo `user_id` y `product_id` del hecho existe en su dimensión.

# Crawlear capa Gold

1. **Create crawler** en **us-east-2**.
2. **Name:** `crawler-gold-ecommerce`
3. **Description:** `Cataloga el modelo estrella de eventos, usuarios y productos`
4. **Tags:** `workshop` = `big_data`, `proyecto` = `ecommerce-opencdp`, `cuenta` = `SalmiBecerra`
5. **S3 path:** `s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/gold/`
6. **Subsequent crawler runs:** Crawl all sub-folders
7. **IAM role:** `GlueETLEcommerceRole`
8. **Target database:** `db_ecommerce`
9. **Table name prefix:** `gold_`
10. **Schedule:** On demand
11. Ejecute el crawler y compruebe las tablas:
    - `gold_dim_usuario`
    - `gold_dim_producto`
    - `gold_fact_evento` (partición `event_type`)
