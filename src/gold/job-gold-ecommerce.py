import sys
import logging
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Cuenta SalmiBecerra (323884514768)
# Modelo estrella de eventos de tienda multicategoría (Open CDP)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'BUCKET',
    'SILVER_PATH',
    'GOLD_PATH'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")

job = Job(glueContext)
job.init(args['JOB_NAME'], args)

BUCKET = args['BUCKET']
SILVER_PATH = args['SILVER_PATH'].rstrip('/')
GOLD_PATH = args['GOLD_PATH'].rstrip('/')

logger.info("=" * 60)
logger.info("JOB GOLD - MODELO DIMENSIONAL ECOMMERCE")
logger.info("=" * 60)
logger.info(f"Bucket: {BUCKET}")
logger.info(f"Silver Path: {SILVER_PATH}")
logger.info(f"Gold Path: {GOLD_PATH}")
logger.info("=" * 60)


def s3_join(base, *parts):
    return "/".join([base.rstrip('/'), *parts])


def load_silver_data(database_name="db_ecommerce", table_name="silver_ecommerce_data_silver_parquet"):
    try:
        logger.info("Cargando eventos desde Silver usando Glue Data Catalog")
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=database_name,
            table_name=table_name,
            transformation_ctx="dynamic_frame_silver"
        )
        df = dynamic_frame.toDF()
        if 'year_partition' in df.columns:
            df = df.drop('year_partition')
        logger.info(f"Datos cargados desde catalog: {len(df.columns)} columnas")
        return df
    except Exception as e:
        logger.error(f"Error al cargar datos desde catalog: {str(e)}")
        raise e


def crear_dim_usuario(df):
    """Atributos de comportamiento por usuario. SCD tipo 1."""
    logger.info("Creando dimension: dim_usuario")

    dim_usuario = df.groupBy('user_id').agg(
        F.count('*').alias('total_eventos'),
        F.sum(F.when(F.col('event_type') == 'VIEW', 1).otherwise(0)).alias('total_vistas'),
        F.sum(F.when(F.col('event_type') == 'CART', 1).otherwise(0)).alias('total_carritos'),
        F.sum(F.when(F.col('event_type') == 'REMOVE_FROM_CART', 1).otherwise(0)).alias('total_remociones'),
        F.sum(F.when(F.col('event_type') == 'PURCHASE', 1).otherwise(0)).alias('total_compras'),
        F.round(F.avg(F.when(F.col('event_type') == 'PURCHASE', F.col('price'))), 2).alias('ticket_promedio'),
        F.countDistinct('user_session').alias('sesiones'),
        F.countDistinct('category_root').alias('categorias_distintas'),
        F.min('event_time').alias('primera_actividad'),
        F.max('event_time').alias('ultima_actividad')
    )

    dim_usuario = dim_usuario.withColumn(
        'tasa_conversion',
        F.when(F.col('total_vistas') > 0, F.round(F.col('total_compras') / F.col('total_vistas'), 4)).otherwise(F.lit(0.0))
    )

    conteo_categoria = df.filter(F.col('category_root').isNotNull()) \
        .groupBy('user_id', 'category_root') \
        .count()
    ventana = Window.partitionBy('user_id').orderBy(F.col('count').desc(), F.col('category_root'))
    categoria_principal = conteo_categoria.withColumn('rn', F.row_number().over(ventana)) \
        .filter(F.col('rn') == 1) \
        .select('user_id', F.col('category_root').alias('categoria_principal'))

    dim_usuario = dim_usuario.join(categoria_principal, on='user_id', how='left')
    logger.info(f"Dimension dim_usuario creada: {dim_usuario.count()} usuarios")
    return dim_usuario


def crear_dim_producto(df):
    """Atributos descriptivos del producto."""
    logger.info("Creando dimension: dim_producto")

    dim_producto = df.groupBy('product_id').agg(
        F.max('category_id').alias('category_id'),
        F.max('category_code').alias('category_code'),
        F.max('category_root').alias('category_root'),
        F.max('categoria_nombre').alias('categoria_nombre'),
        F.max('brand').alias('brand'),
        F.round(F.avg('price'), 2).alias('precio_referencia'),
        F.count('*').alias('total_eventos_producto'),
        F.sum(F.when(F.col('event_type') == 'PURCHASE', 1).otherwise(0)).alias('total_compras_producto')
    )

    logger.info(f"Dimension dim_producto creada: {dim_producto.count()} productos")
    return dim_producto


def crear_fact_evento(df):
    """Un registro por evento de usuario sobre un producto."""
    logger.info("Creando tabla de hechos: fact_evento")

    fact_evento = df.select(
        'id_unico',
        'user_id',
        'product_id',
        'user_session',
        'event_time',
        'event_date',
        'event_type',
        'codigo_evento',
        'descripcion_evento',
        'etapa_funnel',
        'flag_compra',
        'price',
        'hora_evento',
        'dia_semana',
        'mes_evento',
        'category_root'
    )

    logger.info(f"Tabla de hechos fact_evento creada: {fact_evento.count()} eventos")
    return fact_evento


def save_table_to_gold(df, path, table_name, partition_col=None):
    logger.info(f"Guardando tabla: {table_name}")

    try:
        if partition_col:
            df_repartitioned = df.repartition(30, partition_col)
            dynamic_frame = DynamicFrame.fromDF(df_repartitioned, glueContext, f"dynamic_frame_{table_name}")
            glueContext.write_dynamic_frame.from_options(
                frame=dynamic_frame,
                connection_type="s3",
                connection_options={
                    "path": path,
                    "partitionKeys": [partition_col]
                },
                format="parquet",
                format_options={"compression": "snappy"}
            )
            logger.info(f"Tabla {table_name} guardada con particion por {partition_col}")
        else:
            df_repartitioned = df.repartition(20)
            dynamic_frame = DynamicFrame.fromDF(df_repartitioned, glueContext, f"dynamic_frame_{table_name}")
            glueContext.write_dynamic_frame.from_options(
                frame=dynamic_frame,
                connection_type="s3",
                connection_options={"path": path},
                format="parquet",
                format_options={"compression": "snappy"}
            )
            logger.info(f"Tabla {table_name} guardada sin particion")

        logger.info(f"Ubicacion: {path}")
    except Exception as e:
        logger.error(f"Error al guardar tabla {table_name}: {str(e)}")
        raise e


def validar_integridad_referencial(dim_usuario, dim_producto, fact_evento):
    logger.info("Validando integridad referencial de usuarios y productos")

    usuarios_huerfanos = fact_evento.select('user_id').distinct().join(
        dim_usuario.select('user_id').distinct(),
        on='user_id',
        how='left_anti'
    )
    productos_huerfanos = fact_evento.select('product_id').distinct().join(
        dim_producto.select('product_id').distinct(),
        on='product_id',
        how='left_anti'
    )

    count_usuarios = usuarios_huerfanos.count()
    count_productos = productos_huerfanos.count()

    if count_usuarios > 0:
        logger.warning(f"Usuarios en hechos sin dimension: {count_usuarios}")
    if count_productos > 0:
        logger.warning(f"Productos en hechos sin dimension: {count_productos}")
    if count_usuarios == 0 and count_productos == 0:
        logger.info("Integridad referencial validada")

    return count_usuarios + count_productos


def main():
    df_silver = load_silver_data()
    dim_usuario = crear_dim_usuario(df_silver)
    dim_producto = crear_dim_producto(df_silver)
    fact_evento = crear_fact_evento(df_silver)
    validar_integridad_referencial(dim_usuario, dim_producto, fact_evento)

    save_table_to_gold(dim_usuario, s3_join(GOLD_PATH, "dim_usuario"), "dim_usuario")
    save_table_to_gold(dim_producto, s3_join(GOLD_PATH, "dim_producto"), "dim_producto")
    save_table_to_gold(
        fact_evento,
        s3_join(GOLD_PATH, "fact_evento"),
        "fact_evento",
        partition_col="event_type"
    )

    logger.info("=" * 60)
    logger.info("RESUMEN MODELO DIMENSIONAL - CAPA GOLD")
    logger.info("=" * 60)
    logger.info("Dimension dim_usuario: Guardada")
    logger.info("Dimension dim_producto: Guardada")
    logger.info("Tabla hechos fact_evento: Guardada")
    logger.info("Esquema: Star Schema")
    logger.info("Particionamiento hechos: event_type")
    logger.info("=" * 60)

    job.commit()
    logger.info("Job Gold completado exitosamente")


if __name__ == '__main__':
    main()
