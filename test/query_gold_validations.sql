-- Consultas de validacion del modelo estrella de eventos Open CDP.
-- Cuenta SalmiBecerra (323884514768)
-- Base: db_ecommerce
-- Región Athena: us-east-2
-- Resultados: s3://proyecto-final-aws-glue-sagemaker-workshop-ecomerse-11-2026/athena-results/

-- 1. Eventos por tipo
-- Distribucion del embudo: vistas, carrito, remocion y compra.
SELECT
    event_type,
    COUNT(*) AS total_eventos,
    COUNT(DISTINCT user_id) AS usuarios,
    COUNT(DISTINCT product_id) AS productos
FROM "db_ecommerce"."gold_fact_evento"
GROUP BY event_type
ORDER BY total_eventos DESC;


-- 2. Ticket promedio y compras por categoria de producto
SELECT
    p.categoria_nombre,
    p.category_root,
    COUNT(DISTINCT p.product_id) AS productos,
    SUM(p.total_compras_producto) AS compras,
    ROUND(AVG(p.precio_referencia), 2) AS precio_promedio
FROM "db_ecommerce"."gold_dim_producto" AS p
GROUP BY p.categoria_nombre, p.category_root
ORDER BY compras DESC
LIMIT 15;


-- 3. Tasa de conversion por categoria principal del usuario
SELECT
    u.categoria_principal,
    COUNT(*) AS usuarios,
    ROUND(AVG(u.tasa_conversion), 4) AS tasa_conversion_promedio,
    ROUND(AVG(u.ticket_promedio), 2) AS ticket_promedio,
    SUM(u.total_compras) AS compras
FROM "db_ecommerce"."gold_dim_usuario" AS u
GROUP BY u.categoria_principal
ORDER BY compras DESC
LIMIT 15;


-- 4. Dataset para perfiles de usuario (K-Means)
-- Una fila por usuario. Las variables numericas alimentan el modelo.
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
