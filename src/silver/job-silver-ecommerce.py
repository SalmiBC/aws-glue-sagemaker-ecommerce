import sys
import logging
import re
from datetime import datetime
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from pyspark.sql import functions as F

# Cuenta SalmiBecerra (323884514768)
# Eventos de productos y usuarios de una tienda multicategoría (Open CDP)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'BUCKET',
    'BRONZE_PATH',
    'SILVER_PATH',
    'CATALOGOS_PATH',
    'LOGS_PATH'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

spark.conf.set("spark.sql.parquet.datetimeRebaseModeInWrite", "LEGACY")
spark.conf.set("spark.sql.parquet.int96RebaseModeInWrite", "LEGACY")

BUCKET = args['BUCKET']
BRONZE_PATH = args['BRONZE_PATH'].rstrip('/')
SILVER_PATH = args['SILVER_PATH'].rstrip('/')
CATALOGOS_PATH = args['CATALOGOS_PATH'].rstrip('/')
LOGS_PATH = args['LOGS_PATH'].rstrip('/') + '/'

errores = []

logger.info("=" * 60)
logger.info("JOB SILVER - REGLAS DE NEGOCIO EVENTOS ECOMMERCE")
logger.info("=" * 60)
logger.info(f"Bucket: {BUCKET}")
logger.info(f"Bronze Path: {BRONZE_PATH}")
logger.info(f"Silver Path: {SILVER_PATH}")
logger.info(f"Catalogos Path: {CATALOGOS_PATH}")
logger.info(f"Logs Path: {LOGS_PATH}")
logger.info("=" * 60)


def s3_join(base, *parts):
    return "/".join([base.rstrip('/'), *parts])


def load_bronze_data(path):
    try:
        logger.info("Cargando eventos desde Bronze (Parquet particionado)")
        df = spark.read.parquet(path)
        if 'year_partition' in df.columns:
            df = df.drop('year_partition')
        logger.info(f"Datos cargados: {len(df.columns)} columnas")
        return df
    except Exception as e:
        logger.error(f"Error al cargar datos de Bronze: {str(e)}")
        raise e


def load_catalog(path, catalog_name):
    try:
        logger.info(f"Cargando catalogo: {catalog_name}")
        df = spark.read.format("csv") \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .option("encoding", "UTF-8") \
            .load(path)
        logger.info(f"Catalogo cargado: {df.count()} registros")
        return df
    except Exception as e:
        logger.error(f"Error al cargar catalogo {catalog_name}: {str(e)}")
        raise e


def registrar_error(columna, mensaje, valor):
    errores.append({
        'columna': columna,
        'mensaje_error': mensaje,
        'valor': str(valor)
    })


def to_snake_case(col_name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', col_name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    s3 = re.sub(r'[\s\-\.]+', '_', s2)
    return s3.lower()


def aplicar_rn010_estandarizacion_columnas(df):
    """RN-010: nombres de columnas en snake_case."""
    logger.info("Aplicando RN-010: Estandarizacion de nombres de columnas")
    columnas_renombradas = 0
    for old_col in df.columns:
        new_col = to_snake_case(old_col)
        if old_col != new_col:
            df = df.withColumnRenamed(old_col, new_col)
            columnas_renombradas += 1
    logger.info(f"Columnas renombradas a snake_case: {columnas_renombradas}")
    return df


def aplicar_rn001_estandarizacion_fechas(df):
    """RN-001: event_time a timestamp y event_date en formato YYYY-MM-DD."""
    logger.info("Aplicando RN-001: Estandarizacion de event_time")

    if 'event_time' not in df.columns:
        logger.warning("Columna 'event_time' no encontrada")
        return df

    evento_ts = F.coalesce(
        F.to_timestamp(F.col('event_time'), "yyyy-MM-dd HH:mm:ss 'UTC'"),
        F.to_timestamp(F.col('event_time'), "yyyy-MM-dd HH:mm:ss"),
        F.to_timestamp(F.col('event_time'))
    )

    df = df.withColumn('event_time', evento_ts)
    df = df.withColumn('event_date', F.to_date(F.col('event_time')))
    logger.info("event_time convertido a timestamp y event_date a YYYY-MM-DD")
    return df


def aplicar_rn003_normalizacion_eventos(df):
    """RN-003: unificar event_type y brand (mayusculas, sin espacios)."""
    logger.info("Aplicando RN-003: Normalizacion de tipo de evento y marca")

    if 'event_type' in df.columns:
        df = df.withColumn('event_type', F.upper(F.trim(F.col('event_type'))))
    else:
        logger.warning("Columna 'event_type' no encontrada")

    if 'brand' in df.columns:
        df = df.withColumn(
            'brand',
            F.when(F.trim(F.col('brand')) == '', None).otherwise(F.upper(F.trim(F.col('brand'))))
        )

    if 'category_code' in df.columns:
        df = df.withColumn(
            'category_code',
            F.when(F.trim(F.col('category_code')) == '', None).otherwise(F.lower(F.trim(F.col('category_code'))))
        )

    return df


def aplicar_rn002_limpieza_duplicados(df):
    """RN-002: un evento unico por usuario, sesion, instante, tipo y producto."""
    logger.info("Aplicando RN-002: Limpieza de eventos duplicados")

    llaves = ['user_id', 'user_session', 'event_time', 'event_type', 'product_id']
    presentes = [col for col in llaves if col in df.columns]

    if len(presentes) != len(llaves):
        logger.warning(f"No se pudo deduplicar. Faltan columnas: {set(llaves) - set(presentes)}")
        return df

    df = df.dropDuplicates(llaves)
    logger.info("Eventos duplicados eliminados")
    return df


def aplicar_rn008_mapeo_tipo_evento(df, df_cat_evento):
    """RN-008: codigo numerico del tipo de evento segun el catalogo."""
    logger.info("Aplicando RN-008: Mapeo de tipo de evento")

    if 'event_type' not in df.columns:
        logger.warning("Columna 'event_type' no encontrada")
        return df

    df_cat_evento = df_cat_evento.withColumn('event_type', F.upper(F.trim(F.col('event_type'))))

    df = df.join(
        df_cat_evento.select(
            'event_type',
            F.col('codigo').cast('int').alias('codigo_evento'),
            F.col('descripcion').alias('descripcion_evento')
        ),
        on='event_type',
        how='left'
    )
    logger.info("Codigos de tipo de evento mapeados")
    return df


def aplicar_rn009_etapa_funnel(df):
    """RN-009: etapa del embudo y bandera de compra."""
    logger.info("Aplicando RN-009: Etapa de funnel y flag de compra")

    df = df.withColumn(
        'flag_compra',
        F.when(F.col('event_type') == 'PURCHASE', 1).otherwise(0)
    )
    df = df.withColumn(
        'etapa_funnel',
        F.when(F.col('event_type') == 'VIEW', 'VISTA')
         .when(F.col('event_type') == 'CART', 'CARRITO')
         .when(F.col('event_type') == 'REMOVE_FROM_CART', 'REMOCION')
         .when(F.col('event_type') == 'PURCHASE', 'COMPRA')
         .otherwise('DESCONOCIDO')
    )
    logger.info("Etapa de funnel y flag_compra creados")
    return df


def aplicar_rn005_enriquecimiento_categoria(df, df_cat_categoria):
    """RN-005: categoria raiz y nombre legible desde category_code."""
    logger.info("Aplicando RN-005: Enriquecimiento de categoria de producto")

    if 'category_code' not in df.columns:
        logger.warning("Columna 'category_code' no encontrada")
        return df

    df = df.withColumn('category_root', F.split(F.col('category_code'), '\\.').getItem(0))

    df_cat_categoria = df_cat_categoria.withColumn(
        'category_root',
        F.lower(F.trim(F.col('category_root')))
    )

    df = df.join(
        df_cat_categoria.select(
            'category_root',
            F.col('categoria_nombre')
        ),
        on='category_root',
        how='left'
    )
    logger.info("Categorias de producto enriquecidas")
    return df


def aplicar_rn004_variables_derivadas(df):
    """RN-004: hora, dia de la semana, mes y precio numerico."""
    logger.info("Aplicando RN-004: Variables derivadas del evento")

    if 'event_time' in df.columns:
        df = df.withColumn('hora_evento', F.hour(F.col('event_time')))
        df = df.withColumn('dia_semana', F.dayofweek(F.col('event_time')))
        df = df.withColumn('mes_evento', F.month(F.col('event_time')))

    if 'price' in df.columns:
        df = df.withColumn('price', F.col('price').cast('double'))

    logger.info("Variables derivadas creadas")
    return df


def aplicar_rn011_outliers_precio(df):
    """RN-011: un precio extremo no debe arrastrar el ticket del cliente.

    El precio negativo no es un monto válido: pasa a NULL y se anota.
    El precio por encima de Q3 + 1.5 * IQR se recorta a ese límite
    (criterio de Tukey). El evento se conserva. K-Means usa el ticket
    promedio, y un solo precio absurdo movería los grupos.
    """
    logger.info("Aplicando RN-011: Tratamiento de outliers de precio")

    if 'price' not in df.columns:
        logger.warning("Columna 'price' no encontrada")
        return df

    negativos = df.filter(F.col('price') < 0).count()
    if negativos > 0:
        registrar_error('price', 'Precio negativo pasado a NULL', f'{negativos} registros')
        df = df.withColumn(
            'price',
            F.when(F.col('price') < 0, F.lit(None).cast('double')).otherwise(F.col('price'))
        )

    cuantiles = df.approxQuantile('price', [0.25, 0.75], 0.01)
    if len(cuantiles) < 2 or cuantiles[0] is None or cuantiles[1] is None:
        logger.warning("No se pudo calcular el rango intercuartilico del precio")
        return df.withColumn('flag_outlier_precio', F.lit(0))

    q1, q3 = cuantiles
    iqr = q3 - q1
    limite = q3 + (1.5 * iqr)
    if limite <= 0:
        limite = q3

    logger.info(f"Limite de Tukey para price: {limite:.2f} (Q1={q1:.2f}, Q3={q3:.2f})")
    df = df.withColumn(
        'flag_outlier_precio',
        F.when(F.col('price') > F.lit(float(limite)), 1).otherwise(0)
    )
    recortados = df.filter(F.col('flag_outlier_precio') == 1).count()
    if recortados > 0:
        registrar_error(
            'price',
            f'Precio recortado al limite {limite:.2f}. El evento se conserva',
            f'{recortados} registros'
        )
        df = df.withColumn(
            'price',
            F.when(F.col('flag_outlier_precio') == 1, F.lit(float(limite))).otherwise(F.col('price'))
        )

    logger.info(f"Precios recortados: {recortados}")
    return df


def aplicar_rn006_llave_unica(df):
    """RN-006: id_unico del evento usuario-producto."""
    logger.info("Aplicando RN-006: Creacion de llave unica del evento")

    columnas = ['user_id', 'product_id', 'event_time', 'event_type']
    presentes = [col for col in columnas if col in df.columns]

    if len(presentes) != len(columnas):
        logger.warning(f"No se pudo crear llave unica. Faltan columnas: {set(columnas) - set(presentes)}")
        registrar_error(
            'id_unico',
            'No se pudieron encontrar todas las columnas necesarias',
            ', '.join(columnas)
        )
        return df

    df = df.withColumn(
        'id_unico',
        F.concat_ws(
            '_',
            F.col('user_id'),
            F.col('product_id'),
            F.date_format(F.col('event_time'), 'yyyyMMddHHmmss'),
            F.col('event_type')
        )
    )
    logger.info("Llave unica (id_unico) creada")
    return df


def validaciones_consolidadas(df):
    """RN-007 se alimenta de estos conteos. No elimina filas."""
    logger.info("Ejecutando validaciones consolidadas")

    validaciones = df.select(
        F.count(F.when(F.col('event_time').isNull(), 1)).alias('event_time_null'),
        F.count(F.when(F.col('event_type').isNull() | (F.col('event_type') == ''), 1)).alias('event_type_null'),
        F.count(F.when(F.col('user_id').isNull() | (F.trim(F.col('user_id')) == ''), 1)).alias('user_id_null'),
        F.count(F.when(F.col('product_id').isNull() | (F.trim(F.col('product_id')) == ''), 1)).alias('product_id_null'),
        F.count(F.when(F.col('price').isNull() | (F.col('price') < 0), 1)).alias('price_invalido'),
        F.count(F.when(F.col('codigo_evento').isNull(), 1)).alias('codigo_evento_null'),
        F.count(F.when(F.col('category_code').isNull(), 1)).alias('category_code_null'),
        F.count(F.when(F.col('categoria_nombre').isNull() & F.col('category_code').isNotNull(), 1)).alias('categoria_sin_catalogo'),
        F.count(F.when(F.col('id_unico').isNull() | (F.col('id_unico') == ''), 1)).alias('id_unico_invalido'),
        F.count(F.when(F.col('flag_compra') == 1, 1)).alias('compras'),
        F.count(F.when(F.col('event_type') == 'VIEW', 1)).alias('vistas')
    ).collect()[0].asDict()

    if validaciones['event_time_null'] > 0:
        registrar_error('event_time', 'Fecha de evento invalida', f"{validaciones['event_time_null']} registros")
    if validaciones['event_type_null'] > 0:
        registrar_error('event_type', 'Tipo de evento vacio', f"{validaciones['event_type_null']} registros")
    if validaciones['user_id_null'] > 0:
        registrar_error('user_id', 'Usuario obligatorio NULL', f"{validaciones['user_id_null']} registros")
    if validaciones['product_id_null'] > 0:
        registrar_error('product_id', 'Producto obligatorio NULL', f"{validaciones['product_id_null']} registros")
    if validaciones['price_invalido'] > 0:
        registrar_error('price', 'Precio nulo o negativo', f"{validaciones['price_invalido']} registros")
    if validaciones['codigo_evento_null'] > 0:
        registrar_error('event_type', 'Tipo de evento no encontrado en catalogo', f"{validaciones['codigo_evento_null']} registros")
    if validaciones['category_code_null'] > 0:
        registrar_error('category_code', 'Evento sin categoria de producto', f"{validaciones['category_code_null']} registros")
    if validaciones['categoria_sin_catalogo'] > 0:
        registrar_error('category_root', 'Categoria raiz no encontrada en catalogo', f"{validaciones['categoria_sin_catalogo']} registros")
    if validaciones['id_unico_invalido'] > 0:
        registrar_error('id_unico', 'Llave unica incompleta', f"{validaciones['id_unico_invalido']} registros")

    logger.info(f"Vistas: {validaciones['vistas']}")
    logger.info(f"Compras: {validaciones['compras']}")
    logger.info("Validaciones consolidadas completadas")
    return df


def exportar_log_errores(logs_path):
    """RN-007: exportar inconsistencias sin borrar los eventos."""
    logger.info("Aplicando RN-007: Generando log de errores")

    if not errores:
        logger.info("No se registraron errores durante el procesamiento")
        return

    df_errores = spark.createDataFrame(errores)
    fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
    ruta_errores = f"{logs_path}errors_{fecha_actual}.csv"
    df_errores.coalesce(1).write.mode('overwrite').option('header', 'true').csv(ruta_errores)
    logger.info(f"Log de errores exportado: {ruta_errores}")
    logger.info(f"Total de errores registrados: {len(errores)}")


def save_to_silver(df, path):
    logger.info("Guardando eventos en capa Silver")

    try:
        df_with_partition = df.withColumn('year_partition', F.year(F.col('event_time')))
        df_repartitioned = df_with_partition.repartition(30, 'year_partition')
        dynamic_frame = DynamicFrame.fromDF(df_repartitioned, glueContext, "dynamic_frame_silver")

        glueContext.write_dynamic_frame.from_options(
            frame=dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": path,
                "partitionKeys": ["year_partition"]
            },
            format="parquet",
            format_options={
                "compression": "snappy"
            }
        )
        logger.info(f"Datos guardados exitosamente en Silver: {path}")
    except Exception as e:
        logger.error(f"Error al guardar datos en Silver: {str(e)}")
        raise e


def main():
    bronze_parquet_path = s3_join(BRONZE_PATH, "ECOMMERCE_DATA_BRONZE_PARQUET")
    df = load_bronze_data(bronze_parquet_path)

    df_cat_evento = load_catalog(
        s3_join(CATALOGOS_PATH, "catalogo_tipos_evento.csv"),
        "Tipos de evento"
    )
    df_cat_categoria = load_catalog(
        s3_join(CATALOGOS_PATH, "catalogo_categorias_raiz.csv"),
        "Categorias raiz"
    )

    df = aplicar_rn010_estandarizacion_columnas(df)
    df = aplicar_rn001_estandarizacion_fechas(df)
    df = aplicar_rn003_normalizacion_eventos(df)
    df = aplicar_rn002_limpieza_duplicados(df)
    df = aplicar_rn008_mapeo_tipo_evento(df, df_cat_evento)
    df = aplicar_rn009_etapa_funnel(df)
    df = aplicar_rn005_enriquecimiento_categoria(df, df_cat_categoria)
    df = aplicar_rn004_variables_derivadas(df)
    df = aplicar_rn011_outliers_precio(df)
    df = aplicar_rn006_llave_unica(df)
    df = validaciones_consolidadas(df)
    exportar_log_errores(LOGS_PATH)

    silver_output_path = s3_join(SILVER_PATH, "ECOMMERCE_DATA_SILVER_PARQUET")
    save_to_silver(df, silver_output_path)

    logger.info("=" * 60)
    logger.info("RESUMEN DE PROCESAMIENTO - CAPA SILVER")
    logger.info("=" * 60)
    logger.info(f"Total de columnas: {len(df.columns)}")
    logger.info(f"Total de errores detectados: {len(errores)}")
    logger.info("Estado: EVENTOS PROCESADOS EN SILVER")
    logger.info("=" * 60)

    job.commit()
    logger.info("Job Silver completado exitosamente")


if __name__ == '__main__':
    main()
