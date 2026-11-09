-- 002_metrics.sql — vistas de métricas del producto (lo que se muestra en el panel y va al caso)
CREATE OR REPLACE VIEW v_conversations_daily AS
SELECT c.tenant_id,
       date_trunc('day', m.created_at)::date AS day,
       count(DISTINCT c.id)                  AS conversations,
       count(*) FILTER (WHERE m.direction = 'in')  AS inbound,
       count(*) FILTER (WHERE m.direction = 'out') AS outbound,
       count(*) FILTER (WHERE m.source = 'human')  AS human_messages
FROM conversations c
JOIN messages m ON m.conversation_id = c.id
GROUP BY 1, 2;

CREATE OR REPLACE VIEW v_handoff AS
SELECT tenant_id,
       count(*)                                             AS total,
       count(*) FILTER (WHERE status = 'human')              AS with_human,
       count(*) FILTER (WHERE status = 'closed')             AS closed,
       round(100.0 * count(*) FILTER (WHERE handoff_at IS NOT NULL) / GREATEST(count(*), 1), 1) AS handoff_pct
FROM conversations
GROUP BY 1;

CREATE OR REPLACE VIEW v_latency AS
SELECT c.tenant_id,
       count(*) FILTER (WHERE m.latency_ms IS NOT NULL) AS samples,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY m.latency_ms) AS p50_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY m.latency_ms) AS p95_ms,
       round(avg(m.latency_ms)) AS avg_ms
FROM messages m
JOIN conversations c ON c.id = m.conversation_id
WHERE m.direction = 'out'
GROUP BY 1;

CREATE OR REPLACE VIEW v_invoices AS
SELECT tenant_id,
       count(*)                                        AS total,
       count(*) FILTER (WHERE status = 'pass')         AS auto_pass,
       count(*) FILTER (WHERE status = 'review')       AS need_review,
       count(*) FILTER (WHERE status = 'approved')     AS approved,
       round(100.0 * count(*) FILTER (WHERE status IN ('pass','approved')) / GREATEST(count(*),1), 1) AS auto_pct,
       round(avg(extract(epoch FROM (reviewed_at - created_at))/60.0)::numeric, 1) AS review_minutes
FROM invoices
GROUP BY 1;
