-- Step 3b: PostgreSQL schema for the NVIDIA stock analysis (tested on PostgreSQL 16; needs 13 or later).
-- Rebuilt from scratch on every run by python/step3_db.py: the schema is dropped and recreated, then loaded
-- from data/clean/step3/load/*.csv. Values are numeric (exact decimals), never floating point.

\set ON_ERROR_STOP on
DROP SCHEMA IF EXISTS :"schema" CASCADE;
CREATE SCHEMA :"schema";
SET search_path = :"schema";

-- Companies and benchmarks (config/universe.yaml)
CREATE TABLE companies (
    ticker        text PRIMARY KEY,
    cik           char(10),
    role          text NOT NULL CHECK (role IN ('target', 'peer', 'benchmark')),
    fy_end_month  smallint CHECK (fy_end_month BETWEEN 1 AND 12),
    sec_name      text,
    CHECK (role = 'benchmark' OR (cik IS NOT NULL AND fy_end_month IS NOT NULL))
);

-- Line items (config/project.yaml + config/step3.yaml, including support items)
CREATE TABLE line_items (
    line_item     text PRIMARY KEY,
    statement     text NOT NULL CHECK (statement IN ('IS', 'BS', 'CF')),
    period_type   text NOT NULL CHECK (period_type IN ('duration', 'instant')),
    unit          text NOT NULL CHECK (unit IN ('USD', 'USD/shares', 'shares')),
    introduced_in text NOT NULL CHECK (introduced_in IN ('M1', 'Step2', 'Step3')),
    support_item  boolean NOT NULL
);

-- One value per company, line item, period and basis (data/clean/step3/facts_extended.csv)
CREATE TABLE facts (
    ticker                 text NOT NULL REFERENCES companies,
    line_item              text NOT NULL REFERENCES line_items,
    fiscal_year            integer NOT NULL CHECK (fiscal_year BETWEEN 2000 AND 2100),
    fiscal_period          text NOT NULL CHECK (fiscal_period IN ('FY', 'Q1', 'Q2', 'Q3', 'Q4', '6M', '9M')),
    value_basis            text NOT NULL CHECK (value_basis IN (
                               'reported_annual', 'reported_quarter', 'reported_ytd', 'reported_instant',
                               'derived_q4', 'derived_quarter', 'derived_component', 'derived_sum',
                               'declared_zero', 'manual_from_filing')),
    period_start           date,
    period_end             date NOT NULL,
    value                  numeric NOT NULL,
    unit                   text NOT NULL,
    display_value          numeric NOT NULL,          -- USD and shares in millions; per-share unchanged
    display_unit           text NOT NULL,
    concept                text,
    accn                   text,
    form                   text,
    filed                  date,
    restated               boolean,
    original_value         numeric,
    original_accn          text,
    derived_from_accns     text,
    transformation         text,
    entity_cik             text,
    support_item           boolean NOT NULL,
    split_factor           numeric CHECK (split_factor > 0),
    value_split_adjusted   numeric,
    display_split_adjusted numeric,
    snapshot_sha256        text,
    -- reported rows carry their filing; derived and declared rows do not
    CHECK ((value_basis IN ('reported_annual', 'reported_quarter', 'reported_ytd', 'reported_instant', 'manual_from_filing'))
           = (accn IS NOT NULL)),
    CHECK (period_start IS NULL OR period_start <= period_end)
);
CREATE UNIQUE INDEX facts_key ON facts (ticker, line_item, COALESCE(period_start, DATE '0001-01-01'), period_end, value_basis);
CREATE INDEX facts_lookup ON facts (ticker, line_item, fiscal_year, fiscal_period);

-- Stock splits confirmed against SEC share counts (Step 2 check P3)
CREATE TABLE split_factors (
    ticker      text NOT NULL REFERENCES companies,
    split_date  date NOT NULL,
    ratio       numeric NOT NULL CHECK (ratio > 0),
    PRIMARY KEY (ticker, split_date)
);

-- Daily prices to the cutoff (data/clean/step2/market/prices.csv)
CREATE TABLE prices (
    ticker           text NOT NULL REFERENCES companies,
    price_date       date NOT NULL,
    open             numeric NOT NULL CHECK (open > 0),
    high             numeric NOT NULL,
    low              numeric NOT NULL,
    close            numeric NOT NULL CHECK (close > 0),   -- split-adjusted (yfinance Close)
    adj_close        numeric NOT NULL,                     -- split- and dividend-adjusted
    volume           bigint NOT NULL CHECK (volume >= 0),
    dividend         numeric NOT NULL,
    split_ratio      numeric NOT NULL,
    close_as_traded  numeric NOT NULL,
    source_file      text NOT NULL,
    source_sha256    text NOT NULL,
    PRIMARY KEY (ticker, price_date),
    CHECK (high >= low)
);

-- Market inputs at the cutoff (data/clean/step2/market/market_inputs.csv)
CREATE TABLE market_inputs (
    ticker              text PRIMARY KEY,                  -- company/benchmark ticker or RISK_FREE_10Y
    cutoff_date         date NOT NULL,
    close               numeric,
    close_2dp           numeric,
    shares_outstanding  numeric,
    shares_as_of        date,
    shares_accn         text,
    shares_form         text,
    shares_filed        date,
    market_cap_usd      numeric,
    market_cap_basis    text,
    price_source        text,
    yfinance_shares_crosscheck numeric,
    shares_diff_pct     numeric
);

-- What was loaded: one row per load file, written by the loader
CREATE TABLE load_manifest (
    table_name  text PRIMARY KEY,
    source_file text NOT NULL,
    sha256      text NOT NULL,
    rows        integer NOT NULL
);
