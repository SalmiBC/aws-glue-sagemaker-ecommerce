-- Seguimiento de un evento entre bronze y silver.
-- Cuenta SalmiBecerra (323884514768). Base db_ecommerce. Región us-east-2.
-- Reemplace los identificadores de ejemplo por un user_id y product_id reales
-- despues de ver el resultado de la primera consulta.

-- 1. Muestra de un evento crudo en bronze
SELECT
    event_time,
    event_type,
    product_id,
    category_id,
    category_code,
    brand,
    price,
    user_id,
    user_session,
    year_partition
FROM "db_ecommerce"."bronze_ecommerce_data_bronze_parquet"
WHERE event_type = 'view'
LIMIT 5;


-- 2. El mismo tipo de evento ya limpio en silver
SELECT
    id_unico,
    event_time,
    event_date,
    event_type,
    codigo_evento,
    descripcion_evento,
    etapa_funnel,
    flag_compra,
    product_id,
    category_code,
    category_root,
    categoria_nombre,
    brand,
    price,
    user_id,
    user_session,
    hora_evento,
    mes_evento
FROM "db_ecommerce"."silver_ecommerce_data_silver_parquet"
WHERE event_type = 'VIEW'
LIMIT 5;


-- 3. El usuario de esa muestra en la dimension gold
-- Cambie el literal por el user_id obtenido en el paso 2.
SELECT
    user_id,
    total_eventos,
    total_vistas,
    total_carritos,
    total_compras,
    ticket_promedio,
    sesiones,
    categorias_distintas,
    tasa_conversion,
    categoria_principal
FROM "db_ecommerce"."gold_dim_usuario"
WHERE user_id = '541312140';
