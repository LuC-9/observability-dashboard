-- SCD2-lite for llm_pricing: add active flag + surrogate id + updated_at, backfill existing.
ALTER TABLE `oa-apmena-observability-dv.config_ds.llm_pricing` ADD COLUMN IF NOT EXISTS id STRING;
ALTER TABLE `oa-apmena-observability-dv.config_ds.llm_pricing` ADD COLUMN IF NOT EXISTS active BOOL;
ALTER TABLE `oa-apmena-observability-dv.config_ds.llm_pricing` ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

UPDATE `oa-apmena-observability-dv.config_ds.llm_pricing` SET id = GENERATE_UUID()        WHERE id IS NULL;
UPDATE `oa-apmena-observability-dv.config_ds.llm_pricing` SET active = TRUE               WHERE active IS NULL;
UPDATE `oa-apmena-observability-dv.config_ds.llm_pricing` SET updated_at = CURRENT_TIMESTAMP() WHERE updated_at IS NULL;

-- Gold view must use only ACTIVE prices. In gold_trace.spans change the pricing join to:
--   LEFT JOIN `…config_ds.llm_pricing` p
--     ON STARTS_WITH(e.model, p.model_prefix) AND p.active
-- (the QUALIFY longest-prefix logic then picks the longest *active* prefix)
