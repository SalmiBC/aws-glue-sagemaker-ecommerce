# Implementación ETL en AWS Glue con Arquitectura Medallion

Taller de big data y machine learning sobre **eventos de comportamiento de una tienda en línea multicategoría**.

Cada fila es un evento. Cada evento relaciona productos y usuarios (relación muchos a muchos). Los datos provienen del proyecto abierto **Open CDP** (Customer Data Platform). El archivo de trabajo de este repositorio es el extracto de **octubre de 2019**. El dataset completo de Open CDP cubre 7 meses, de octubre de 2019 a abril de 2020, con el mismo esquema. Si se agregan los demás meses al mismo archivo de bronze, los jobs no cambian.

## Cuenta y recursos

| Dato | Valor |
|------|--------|
| Nombre de la cuenta | `SalmiBecerra` |
| ID de la cuenta | `323884514768` |
| Región | `us-east-2` (Ohio). El bucket de este proyecto ya existe en esta región. |
| Bucket S3 | `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026` |
| Base de datos Glue | `db_ecommerce` |
| Rol IAM | `GlueETLEcommerceRole` |

Columnas del evento: `event_time`, `event_type`, `product_id`, `category_id`, `category_code`, `brand`, `price`, `user_id`, `user_session`.

Tipos de evento: `view`, `cart`, `remove_from_cart`, `purchase`.

## **FASE 1: PREPARACIÓN DEL ENTORNO AWS**

### Paso 1: Usar el bucket S3

El bucket ya está creado en la cuenta SalmiBecerra. No hace falta crear otro.

1. Acceda al servicio **S3** en la consola de AWS, región **us-east-2**.
2. Abra el bucket `proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026`.
3. Confirme la etiqueta:
   - Clave: `workshop`
   - Valor: `big_data`
   - Clave: `proyecto`
   - Valor: `ecommerce-opencdp`
   - Clave: `cuenta`
   - Valor: `SalmiBecerra`

Si el bucket no tuviera etiquetas, agréguelas en **Propiedades → Etiquetas**.

### Paso 2: Crear la estructura de carpetas

Dentro del bucket, deje estos prefijos:

```
bronze/
  ├── catalogos/
  ├── ecommerce_behavior_events.csv.gz
  └── ECOMMERCE_DATA_BRONZE_PARQUET/
silver/
  └── ECOMMERCE_DATA_SILVER_PARQUET/
gold/
  ├── fact_evento/
  ├── dim_usuario/
  └── dim_producto/
scripts/
logs/
  └── errors/
athena-results/
modelos/
  └── kmeans/
```

`ECOMMERCE_DATA_BRONZE_PARQUET/`, `ECOMMERCE_DATA_SILVER_PARQUET/` y las tablas gold las escriben los jobs. Las carpetas `catalogos`, `scripts`, `logs/errors`, `athena-results` y `modelos/kmeans` se crean al subir archivos.

### Paso 3: Cargar archivos de catálogo

Cargue estos CSV en `bronze/catalogos/`.

**Archivo: catalogo_tipos_evento.csv**

```csv
event_type,codigo,descripcion
VIEW,1,Vista de producto
CART,2,Agregar al carrito
REMOVE_FROM_CART,3,Quitar del carrito
PURCHASE,4,Compra
```

**Archivo: catalogo_categorias_raiz.csv**

```csv
category_root,categoria_nombre
electronics,Electronica
appliances,Electrodomesticos
computers,Computadores
apparel,Ropa
auto,Automotriz
kids,Infantil
construction,Construccion
furniture,Muebles
accessories,Accesorios
sport,Deporte
medicine,Salud y farmacia
country_yard,Jardin y exterior
stationery,Papeleria
```

Los archivos locales están en `data/catalogs/`.

### Paso 4: Cargar el dataset de eventos

Cargue el archivo de eventos en `bronze/` con el nombre `ecommerce_behavior_events.csv.gz`.

El archivo local es `2019-Oct.csv.gz` (octubre 2019, comprimido). Spark lee el gzip sin descomprimirlo antes. La carga puede tardar varios minutos por el tamaño del archivo.

## **FASE 2: CONFIGURACIÓN DE IAM**

### Paso 5: Crear el rol de IAM para Glue y SageMaker

1. Acceda al servicio **IAM**.
2. Seleccione **Roles** → **Crear rol**.
3. Configure el rol:

   **Tipo de entidad de confianza:**
   - Servicio de AWS
   - Caso de uso: **Glue**
   - Siguiente

   **Permisos.** Adjunte estas políticas administradas:
   - `AWSGlueServiceRole`
   - `AmazonS3FullAccess`
   - `CloudWatchLogsFullAccess`
   - `AWSGlueConsoleFullAccess`
   - `AmazonSageMakerFullAccess`
   - `AmazonAthenaFullAccess`

   **Detalles del rol:**
   - Nombre: `GlueETLEcommerceRole`
   - Descripción: `Rol para ETL medallion de eventos e-commerce Open CDP y despliegue del modelo en SageMaker. Cuenta SalmiBecerra.`

   **Etiquetas:**
   - `workshop` = `big_data`
   - `proyecto` = `ecommerce-opencdp`
   - `cuenta` = `SalmiBecerra`

4. Cree el rol.
5. Abra **Trust relationships → Edit trust policy** y deje que Glue, SageMaker y Lambda puedan asumirlo:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "glue.amazonaws.com" },
      "Action": "sts:AssumeRole"
    },
    {
      "Effect": "Allow",
      "Principal": { "Service": "sagemaker.amazonaws.com" },
      "Action": "sts:AssumeRole"
    },
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

6. Anote el ARN:

`arn:aws:iam::323884514768:role/GlueETLEcommerceRole`

## **FASE 3: CONFIGURACIÓN DE GLUE DATA CATALOG**

### Paso 6: Crear la base de datos en Glue Catalog

1. Acceda a **AWS Glue** en la región **us-east-2**.
2. **Data Catalog → Databases → Add database**.
3. Configure:
   - **Nombre:** `db_ecommerce`
   - **Descripción:** `Eventos de comportamiento de tienda multicategoría Open CDP. Arquitectura medallion. Cuenta SalmiBecerra.`
   - **Etiquetas:** `workshop` = `big_data`, `proyecto` = `ecommerce-opencdp`, `cuenta` = `SalmiBecerra`
4. **Create database**.

## Siguientes fases

| Fase | Guía | Qué produce |
|------|------|-------------|
| Bronze | [src/bronze/README.md](bronze/README.md) | Eventos crudos en Parquet |
| Silver | [src/silver/README.md](silver/README.md) | Eventos limpios, con catálogos y llave única |
| Gold | [src/gold/README.md](gold/README.md) | `fact_evento`, `dim_usuario`, `dim_producto` |
| SageMaker | [src/sagemaker/README.md](sagemaker/README.md) | Perfiles de usuarios con K-Means. La k se elige con la silueta |
| Publicación | [src/aws/README.md](aws/README.md) | Silueta, Swagger y pantalla de consulta siempre disponibles en AWS |
