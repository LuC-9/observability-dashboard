-- Minimal gold metrics layer for the dashboard.
-- NOTE (verify): adjust the bronze_metric column names below to match metric_pull.py output.
-- Run once to backfill the table, then the workflow's merge_metrics step keeps it fresh.
--
-- Confirm bronze columns first:
--   SELECT * FROM `oa-apmena-observability-dv.bronze_metric.timeseries` LIMIT 1;

-- 1) silver view: typed + one numeric `value` per point, service resolved best-effort
CREATE OR REPLACE VIEW `oa-apmena-observability-dv.silver_metric.timeseries` AS
SELECT
  end_time                                  AS timestamp,
  project_id,
  project_env                               AS environment,
  metric_type,
  -- service from resource/metric labels when present (run.googleapis.com exposes service_name)
  COALESCE(
    JSON_VALUE(TO_JSON_STRING(resource_labels), '$.service_name'),
    JSON_VALUE(TO_JSON_STRING(metric_labels),   '$.service_name')
  )                                         AS service_name,
  resource_type,
  -- single numeric value: gauge/int/double, else distribution mean
  COALESCE(value_double, CAST(value_int AS FLOAT64), hist_mean) AS value,
  hist_count, hist_sum, hist_min, hist_max,
  ingested_at
FROM `oa-apmena-observability-dv.bronze_metric.timeseries`;

-- 2) gold view (rename/trim for the dashboard contract)
CREATE OR REPLACE VIEW `oa-apmena-observability-dv.gold_metric.metrics` AS
SELECT timestamp, project_id, environment, service_name, metric_type, value, ingested_at,
       CAST(NULL AS STRING) AS unit
FROM `oa-apmena-observability-dv.silver_metric.timeseries`;

-- 3) persisted table for fast dashboard reads (initial backfill)
CREATE TABLE IF NOT EXISTS `oa-apmena-observability-dv.gold.metrics`
PARTITION BY DATE(timestamp)
CLUSTER BY service_name, metric_type AS
SELECT * FROM `oa-apmena-observability-dv.gold_metric.metrics`;

-- 4) incremental merge (add this as merge_metrics step in workflow.yaml)
-- MERGE `oa-apmena-observability-dv.gold.metrics` T
-- USING (SELECT * FROM `oa-apmena-observability-dv.gold_metric.metrics`
--        WHERE ingested_at >= (SELECT COALESCE(MAX(ingested_at), TIMESTAMP '1970-01-01')
--                              FROM `oa-apmena-observability-dv.gold.metrics`)) S
-- ON  T.timestamp=S.timestamp AND T.metric_type=S.metric_type
-- AND IFNULL(T.service_name,'')=IFNULL(S.service_name,'') AND T.project_id=S.project_id
-- WHEN NOT MATCHED THEN INSERT ROW;
