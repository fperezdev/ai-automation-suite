-- 003: el gráfico necesita saber cuántas conversaciones del día pasaron por una persona,
-- y el panel muestra costo por conversación medido, no estimado.
DROP VIEW IF EXISTS v_conversations_daily;

CREATE VIEW v_conversations_daily AS
SELECT c.tenant_id,
       date_trunc('day', m.created_at)::date AS day,
       count(DISTINCT c.id)                                     AS conversations,
       count(DISTINCT c.id) FILTER (WHERE c.handoff_at IS NOT NULL) AS handoff_conversations,
       count(*) FILTER (WHERE m.direction = 'in')               AS inbound,
       count(*) FILTER (WHERE m.direction = 'out')              AS outbound,
       count(*) FILTER (WHERE m.source = 'human')               AS human_messages
FROM conversations c
JOIN messages m ON m.conversation_id = c.id
GROUP BY 1, 2;

CREATE OR REPLACE VIEW v_cost AS
SELECT c.tenant_id,
       count(DISTINCT c.id)                        AS conversations,
       coalesce(sum(m.cost_usd), 0)                AS cost_usd_total,
       round(coalesce(sum(m.cost_usd), 0) / GREATEST(count(DISTINCT c.id), 1), 6) AS cost_usd_per_conversation,
       count(*) FILTER (WHERE m.tokens IS NOT NULL) AS with_tokens
FROM conversations c
LEFT JOIN messages m ON m.conversation_id = c.id
GROUP BY 1;
