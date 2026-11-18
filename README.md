# Eventos de e-commerce: ETL medallion y perfiles de usuario

Pipeline de big data sobre el comportamiento de una tienda en línea multicategoría. Cada fila es un evento y cada evento relaciona un usuario con un producto: vista, carrito, quitar del carrito o compra. Los datos son del proyecto abierto Open CDP (octubre 2019 a abril 2020). Este repositorio procesa el extracto de octubre de 2019, que ya está en S3. Los demás meses usan el mismo esquema y el mismo pipeline.

Fuente de los datos: [eCommerce behavior data from multi category store](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store).

## Cuenta

| Dato | Valor |
|------|--------|
| Cuenta | SalmiBecerra |
| ID | `323884514768` |
| Región | `us-east-2` |
| Bucket | `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026` |
| Base Glue | `db_ecommerce` |
| Rol | `GlueETLEcommerceRole` |

## Arquitectura

1. **Bronze.** El CSV de eventos se guarda en Parquet, particionado por año.
2. **Silver.** Se estandarizan fechas y tipos de evento, se eliminan duplicados, se enriquece la categoría del producto y se construye la llave del evento. Las inconsistencias se registran y no se borran.
3. **Gold.** Esquema estrella: `fact_evento`, `dim_usuario` y `dim_producto`.
4. **SageMaker.** K-Means sobre el perfil de cada usuario (vistas, carrito, compras, ticket y conversión). El endpoint se llama `kmeans-perfiles-ecommerce`.

## Cómo está organizado

```
src/bronze/     job-bronze-ecommerce.py
src/silver/     job-silver-ecommerce.py
src/gold/       job-gold-ecommerce.py
src/sagemaker/  perfiles.ipynb
data/catalogs/  tipos de evento y categorías raíz
test/           consultas de validación en Athena
```

Los pasos de consola, parámetros de los jobs y crawlers están en [src/README.md](src/README.md) y en el README de cada capa.

## Datos en S3

El archivo de octubre está en:

`s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/bronze/ecommerce_behavior_events.csv.gz`

Los catálogos están en `bronze/catalogos/` y los scripts en `scripts/`.
