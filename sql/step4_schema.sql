-- Step 4: tables added to the Step 3 schema (python/step4_db.py). Step 3 must have been built first:
-- `run_step3.py db` drops and recreates the whole schema, so `run_step4.py db` always follows it.
\set ON_ERROR_STOP on
SET search_path = :"schema";

DROP VIEW IF EXISTS v_scorecard, v_scorecard_detail, v_scorecard_metrics, v_wacc, v_peg, v_beta, v_latest_annual CASCADE;
DROP TABLE IF EXISTS scorecard_rules, scorecard_params, estimates CASCADE;
DELETE FROM load_manifest WHERE table_name IN ('scorecard_rules', 'scorecard_params', 'estimates');

-- The ten tests and their thresholds (config/scorecard.yaml)
CREATE TABLE scorecard_rules (
    test_no        smallint PRIMARY KEY CHECK (test_no BETWEEN 1 AND 10),
    name           text NOT NULL,
    metric         text NOT NULL,
    direction      text NOT NULL CHECK (direction IN ('higher', 'lower')),
    pass_value     numeric NOT NULL,
    near_value     numeric NOT NULL,
    fail_when_null text,                    -- why a missing value is a scored fail (else: not scored)
    CHECK ((direction = 'higher' AND near_value <= pass_value) OR (direction = 'lower' AND near_value >= pass_value))
);

-- Analyst assumptions used by the views, each labelled (config/scorecard.yaml)
CREATE TABLE scorecard_params (
    key   text PRIMARY KEY,
    value numeric NOT NULL,
    note  text NOT NULL
);

-- Consensus estimates snapshot (data/clean/step4/estimates.csv), provenance on every row
CREATE TABLE estimates (
    ticker          text NOT NULL REFERENCES companies,
    kind            text NOT NULL CHECK (kind IN ('eps', 'revenue')),
    period          text NOT NULL CHECK (period IN ('0q', '+1q', '0y', '+1y')),
    avg             numeric,
    low             numeric,
    high            numeric,
    analysts        numeric CHECK (analysts >= 0),
    year_ago        numeric,
    growth_reported numeric,
    fetched_at_utc  timestamptz NOT NULL,
    snapshot_id     text NOT NULL,
    raw_file        text NOT NULL,
    raw_sha256      text NOT NULL,
    PRIMARY KEY (ticker, kind, period),
    CHECK (low IS NULL OR high IS NULL OR low <= high)
);
