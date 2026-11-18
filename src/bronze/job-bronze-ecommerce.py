import sys
import logging
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from pyspark.sql import functions as F

# Cuenta SalmiBecerra (323884514768)
# Bucket: proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026
# Dataset: eventos de comportamiento de una tienda multicategoría (Open CDP)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'BUCKET',
    'BRONZE_PATH'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

BUCKET = args['BUCKET']
BRONZE_PATH = args['BRONZE_PATH'].rstrip('/')

logger.info("=" * 60)
logger.info("JOB BRONZE - CARGA DE EVENTOS ECOMMERCE")
logger.info("=" * 60)
logger.info(f"Bucket: {BUCKET}")
logger.info(f"Bronze Path: {BRONZE_PATH}")
logger.info("=" * 60)


def s3_join(base, *parts):
    return "/".join([base.rstrip('/'), *parts])


def load_data(path):
    try:
        df_eventos = spark.read.format("csv") \
            .option("header", "true") \
            .option("inferSchema", "false") \
            .option("encoding", "UTF-8") \
            .option("sep", ",") \
            .option("quote", "\"") \
            .option("escape", "\"") \
            .option("ignoreLeadingWhiteSpace", "true") \
            .option("ignoreTrailingWhiteSpace", "true") \
            .option("mode", "PERMISSIVE") \
            .load(path)

        logger.info("Eventos de e-commerce cargados desde CSV")
        return df_eventos
    except Exception as e:
        logger.error(f"Error al leer eventos de e-commerce: {str(e)}")
        raise e


def validate_dataframe(df):
    logger.info("Iniciando validaciones basicas de calidad de datos (muestra)")

    df_sample = df.sample(False, 0.01, seed=42)
    registros_sample = df_sample.count()
    logger.info(f"Validando con muestra de {registros_sample} registros (1% del total)")

    null_counts = df_sample.select([
        F.count(F.when(F.col(c).isNull() | (F.trim(F.col(c)) == ''), c)).alias(c)
        for c in df_sample.columns
    ]).collect()[0].asDict()

    columnas_con_nulos = 0
    for col_name, null_count in null_counts.items():
        if null_count > 0 and registros_sample > 0:
            porcentaje = (null_count / registros_sample) * 100
            logger.warning(f"Columna '{col_name}': ~{porcentaje:.2f}% valores NULL o vacios (estimado)")
            columnas_con_nulos += 1

    if columnas_con_nulos == 0:
        logger.info("No se detectaron valores NULL significativos")
    else:
        logger.warning(f"Total de columnas con valores NULL: {columnas_con_nulos}")

    logger.info("Analizando duplicados (muestra 1%)")
    registros_unicos_sample = df_sample.dropDuplicates().count()
    duplicados_sample = registros_sample - registros_unicos_sample

    if duplicados_sample > 0:
        porcentaje_dup = (duplicados_sample / registros_sample) * 100
        logger.warning(f"Duplicados en muestra: {duplicados_sample} (~{porcentaje_dup:.2f}%)")
    else:
        logger.info("No se detectaron duplicados en la muestra")

    return columnas_con_nulos, duplicados_sample


def save_dataframe(df, path):
    logger.info("Guardando eventos en formato Parquet")

    try:
        df_with_partition = df.withColumn(
            'year_partition',
            F.year(F.to_timestamp(F.col('event_time'), "yyyy-MM-dd HH:mm:ss 'UTC'"))
        )

        df_repartitioned = df_with_partition.repartition(30, 'year_partition')
        dynamic_frame = DynamicFrame.fromDF(df_repartitioned, glueContext, "dynamic_frame_eventos")

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

        logger.info("Datos guardados exitosamente en formato Parquet")
        logger.info(f"Ubicacion: {path}")
        logger.info("Datos particionados por year_partition (anio de event_time)")

    except Exception as e:
        logger.error(f"Error al guardar datos en Parquet: {str(e)}")
        raise e


if __name__ == '__main__':
    file_full_path = s3_join(BRONZE_PATH, "ecommerce_behavior_events.csv.gz")
    df = load_data(file_full_path)
    validate_dataframe(df)
    file_path_save = s3_join(BRONZE_PATH, "ECOMMERCE_DATA_BRONZE_PARQUET")
    save_dataframe(df, file_path_save)
    job.commit()
    logger.info("Job Bronze completado exitosamente")
    logger.info("Los eventos estan listos para ser procesados en la capa Silver")
