-- Step 3b: analytical views. All amounts in USD millions (display values); EPS in USD per share,
-- shares in millions, both split-adjusted to the cutoff share basis (S3-D2). Ratio definitions: S3-D3 in
-- docs/decision_log.md. A ratio is NULL, never guessed, when an input is missing or its rule does not apply.

\set ON_ERROR_STOP on
SET search_path = :"schema";

-- --------------------------------------------------------------------------------------------------------
-- v_facts_used: the one value per company, line item and period that the views use
CREATE VIEW v_facts_used AS
SELECT f.ticker, f.line_item, f.fiscal_year, f.fiscal_period, f.period_start, f.period_end, f.value_basis,
       CASE WHEN f.line_item IN ('eps_diluted', 'shares_diluted') THEN f.display_split_adjusted ELSE f.display_value END AS amount,
       f.concept, f.accn
FROM facts f
WHERE NOT f.support_item
  AND f.value_basis <> 'reported_ytd';

-- Annual values: flows for the fiscal year (FY); balance-sheet items at fiscal year end (Q4 instant)
-- Early filings sometimes tag one value under two dates a few days apart (same value; DB2 fails if values differ):
-- one row per company, item and fiscal year, the latest period end and start winning.
CREATE VIEW v_annual_long AS
SELECT DISTINCT ON (u.ticker, u.line_item, u.fiscal_year) u.*
FROM v_facts_used u
JOIN line_items li USING (line_item)
WHERE (li.period_type = 'duration' AND u.fiscal_period = 'FY')
   OR (li.period_type = 'instant' AND u.fiscal_period = 'Q4')
ORDER BY u.ticker, u.line_item, u.fiscal_year, u.period_end DESC, u.period_start DESC NULLS LAST;

-- One quarterly row per company, item and quarter end (DB3 fails if duplicates disagree)
CREATE VIEW v_quarterly_long AS
SELECT DISTINCT ON (ticker, line_item, period_end) *
FROM v_facts_used
WHERE fiscal_period IN ('Q1', 'Q2', 'Q3', 'Q4') AND value_basis <> 'reported_annual'
ORDER BY ticker, line_item, period_end, period_start DESC NULLS LAST;

CREATE VIEW v_annual AS
SELECT ticker, fiscal_year,
       max(period_end) FILTER (WHERE line_item = 'revenue')              AS period_end,
       max(amount) FILTER (WHERE line_item = 'revenue')                  AS revenue,
       max(amount) FILTER (WHERE line_item = 'gross_profit')             AS gross_profit,
       max(amount) FILTER (WHERE line_item = 'operating_income')         AS operating_income,
       max(amount) FILTER (WHERE line_item = 'net_income')               AS net_income,
       max(amount) FILTER (WHERE line_item = 'eps_diluted')              AS eps_diluted_adj,
       max(amount) FILTER (WHERE line_item = 'shares_diluted')           AS shares_diluted_adj,
       max(amount) FILTER (WHERE line_item = 'income_tax')               AS income_tax,
       max(amount) FILTER (WHERE line_item = 'pretax_income')            AS pretax_income,
       max(amount) FILTER (WHERE line_item = 'interest_expense')         AS interest_expense,
       max(amount) FILTER (WHERE line_item = 'depreciation_amortization') AS depreciation_amortization,
       max(amount) FILTER (WHERE line_item = 'sbc')                      AS sbc,
       max(amount) FILTER (WHERE line_item = 'operating_cash_flow')      AS operating_cash_flow,
       max(amount) FILTER (WHERE line_item = 'capex')                    AS capex,
       max(amount) FILTER (WHERE line_item = 'total_assets')             AS total_assets,
       max(amount) FILTER (WHERE line_item = 'total_liabilities')        AS total_liabilities,
       max(amount) FILTER (WHERE line_item = 'stockholders_equity')      AS stockholders_equity,
       max(amount) FILTER (WHERE line_item = 'cash_and_equivalents')     AS cash_and_equivalents,
       max(amount) FILTER (WHERE line_item = 'st_investments')           AS st_investments,
       max(amount) FILTER (WHERE line_item = 'current_assets')           AS current_assets,
       max(amount) FILTER (WHERE line_item = 'current_liabilities')      AS current_liabilities,
       max(amount) FILTER (WHERE line_item = 'inventory')                AS inventory,
       max(amount) FILTER (WHERE line_item = 'total_debt')               AS total_debt
FROM v_annual_long
GROUP BY ticker, fiscal_year;

-- Quarterly values: 3-month flows (reported or derived) and balance-sheet items at each quarter end
CREATE VIEW v_quarterly AS
SELECT ticker, period_end,
       max(fiscal_year)   AS fiscal_year,
       max(fiscal_period) AS fiscal_period,
       max(amount) FILTER (WHERE line_item = 'revenue')                  AS revenue,
       max(amount) FILTER (WHERE line_item = 'gross_profit')             AS gross_profit,
       max(amount) FILTER (WHERE line_item = 'operating_income')         AS operating_income,
       max(amount) FILTER (WHERE line_item = 'net_income')               AS net_income,
       max(amount) FILTER (WHERE line_item = 'income_tax')               AS income_tax,
       max(amount) FILTER (WHERE line_item = 'pretax_income')            AS pretax_income,
       max(amount) FILTER (WHERE line_item = 'depreciation_amortization') AS depreciation_amortization,
       max(amount) FILTER (WHERE line_item = 'sbc')                      AS sbc,
       max(amount) FILTER (WHERE line_item = 'operating_cash_flow')      AS operating_cash_flow,
       max(amount) FILTER (WHERE line_item = 'capex')                    AS capex,
       max(amount) FILTER (WHERE line_item = 'total_assets')             AS total_assets,
       max(amount) FILTER (WHERE line_item = 'stockholders_equity')      AS stockholders_equity,
       max(amount) FILTER (WHERE line_item = 'cash_and_equivalents')     AS cash_and_equivalents,
       max(amount) FILTER (WHERE line_item = 'st_investments')           AS st_investments,
       max(amount) FILTER (WHERE line_item = 'total_debt')               AS total_debt
FROM v_quarterly_long
GROUP BY ticker, period_end;

-- LTM (D5): sum of the four latest 3-month quarters at each quarter end. A flow is NULL unless all four
-- quarters exist and they span one year (first to last quarter end 250-300 days apart).
CREATE VIEW v_ltm AS
WITH w AS (
    SELECT q.*,
           period_end - lag(period_end, 3) OVER p AS span_days,
           sum(revenue) OVER p4 AS s_revenue, count(revenue) OVER p4 AS n_revenue,
           sum(gross_profit) OVER p4 AS s_gross_profit, count(gross_profit) OVER p4 AS n_gross_profit,
           sum(operating_income) OVER p4 AS s_operating_income, count(operating_income) OVER p4 AS n_operating_income,
           sum(net_income) OVER p4 AS s_net_income, count(net_income) OVER p4 AS n_net_income,
           sum(depreciation_amortization) OVER p4 AS s_da, count(depreciation_amortization) OVER p4 AS n_da,
           sum(operating_cash_flow) OVER p4 AS s_ocf, count(operating_cash_flow) OVER p4 AS n_ocf,
           sum(capex) OVER p4 AS s_capex, count(capex) OVER p4 AS n_capex
    FROM v_quarterly q
    WINDOW p AS (PARTITION BY ticker ORDER BY period_end),
           p4 AS (PARTITION BY ticker ORDER BY period_end ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)
)
SELECT ticker, period_end, fiscal_year, fiscal_period,
       CASE WHEN ok AND n_revenue = 4 THEN s_revenue END                   AS ltm_revenue,
       CASE WHEN ok AND n_gross_profit = 4 THEN s_gross_profit END         AS ltm_gross_profit,
       CASE WHEN ok AND n_operating_income = 4 THEN s_operating_income END AS ltm_operating_income,
       CASE WHEN ok AND n_net_income = 4 THEN s_net_income END             AS ltm_net_income,
       CASE WHEN ok AND n_da = 4 THEN s_da END                             AS ltm_depreciation_amortization,
       CASE WHEN ok AND n_ocf = 4 THEN s_ocf END                           AS ltm_operating_cash_flow,
       CASE WHEN ok AND n_capex = 4 THEN s_capex END                       AS ltm_capex,
       total_debt, cash_and_equivalents, st_investments, stockholders_equity
FROM (SELECT w.*, COALESCE(span_days BETWEEN 250 AND 300, false) AS ok FROM w) x;

-- --------------------------------------------------------------------------------------------------------
-- Annual ratios (S3-D3)
CREATE VIEW v_ratios_annual AS
WITH a AS (
    SELECT v.*,
           lag(fiscal_year) OVER y          AS prev_year,
           lag(revenue) OVER y              AS prev_revenue,
           lag(stockholders_equity) OVER y  AS prev_equity,
           lag(fiscal_year, 5) OVER y       AS year_5,
           lag(revenue, 5) OVER y           AS revenue_5,
           lag(shares_diluted_adj, 5) OVER y AS shares_5,
           lag(fiscal_year, 3) OVER y       AS year_3,
           lag(net_income, 3) OVER y        AS net_income_3,
           lag(total_debt) OVER y           AS prev_debt,
           lag(cash_and_equivalents) OVER y AS prev_cash,
           lag(st_investments) OVER y       AS prev_st
    FROM v_annual v
    WINDOW y AS (PARTITION BY ticker ORDER BY fiscal_year)
), b AS (
    SELECT a.*,
           CASE WHEN prev_year = fiscal_year - 1 AND prev_revenue > 0 THEN revenue / prev_revenue - 1 END AS revenue_growth,
           CASE WHEN year_5 = fiscal_year - 5 AND revenue_5 > 0 AND revenue > 0
                THEN power(revenue / revenue_5, 1.0 / 5) - 1 END                                   AS revenue_cagr_5y,
           CASE WHEN revenue > 0 THEN gross_profit / revenue END                                    AS gross_margin,
           CASE WHEN revenue > 0 THEN operating_income / revenue END                                AS operating_margin,
           CASE WHEN revenue > 0 THEN net_income / revenue END                                      AS net_margin,
           CASE WHEN prev_year = fiscal_year - 1 THEN (stockholders_equity + prev_equity) / 2 END   AS avg_equity,
           CASE WHEN current_liabilities > 0 THEN (current_assets - inventory) / current_liabilities END AS quick_ratio,
           operating_cash_flow - capex                                                              AS fcf,
           total_debt - cash_and_equivalents - st_investments                                       AS net_debt,
           operating_income + depreciation_amortization                                             AS ebitda,
           CASE WHEN pretax_income > 0 AND income_tax / pretax_income BETWEEN 0 AND 1
                THEN income_tax / pretax_income END                                                 AS effective_tax_rate,
           total_debt + stockholders_equity - cash_and_equivalents - st_investments                 AS invested_capital,
           CASE WHEN prev_year = fiscal_year - 1
                THEN prev_debt + prev_equity - prev_cash - prev_st END                              AS prev_invested_capital,
           CASE WHEN year_5 = fiscal_year - 5 AND shares_5 > 0 THEN shares_diluted_adj / shares_5 - 1 END AS shares_change_5y,
           CASE WHEN year_3 = fiscal_year - 3 AND net_income_3 > 0 AND net_income > 0
                THEN power(net_income / net_income_3, 1.0 / 3) - 1 END                             AS net_income_cagr_3y
    FROM a
), c AS (
    SELECT b.*,
           CASE WHEN avg_equity > 0 THEN net_income / avg_equity END                                AS roe,
           CASE WHEN net_income > 0 THEN fcf / net_income END                                       AS fcf_conversion,
           CASE WHEN ebitda > 0 THEN net_debt / ebitda END                                          AS net_debt_to_ebitda,
           COALESCE(effective_tax_rate, 0.21)                                                       AS tax_rate_used,
           CASE WHEN effective_tax_rate IS NULL AND operating_income IS NOT NULL
                THEN 'statutory 21% used: effective rate unavailable or outside 0-100%' END         AS tax_rate_note,
           CASE WHEN invested_capital IS NOT NULL AND prev_invested_capital IS NOT NULL
                THEN (invested_capital + prev_invested_capital) / 2 END                             AS avg_invested_capital
    FROM b
)
SELECT ticker, fiscal_year, period_end, revenue, revenue_growth, revenue_cagr_5y,
       gross_margin, operating_margin, net_margin, roe,
       CASE WHEN count(roe) OVER r5 = 5 THEN avg(roe) OVER r5 END AS roe_5y_avg,
       CASE WHEN count(roe) OVER r3 = 3 THEN avg(roe) OVER r3 END AS roe_3y_avg,
       quick_ratio, fcf, fcf_conversion, net_debt, ebitda, net_debt_to_ebitda,
       effective_tax_rate, tax_rate_used, tax_rate_note,
       operating_income * (1 - tax_rate_used) AS nopat,
       invested_capital, avg_invested_capital,
       CASE WHEN avg_invested_capital > 0 THEN operating_income * (1 - tax_rate_used) / avg_invested_capital END AS roic,
       shares_diluted_adj, shares_change_5y, eps_diluted_adj, net_income_cagr_3y
FROM c
WINDOW r5 AS (PARTITION BY ticker ORDER BY fiscal_year ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
       r3 AS (PARTITION BY ticker ORDER BY fiscal_year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW);

-- LTM ratios at each quarter end
CREATE VIEW v_ratios_ltm AS
SELECT l.ticker, l.period_end, l.fiscal_year, l.fiscal_period,
       l.ltm_revenue,
       CASE WHEN lag(l.ltm_revenue, 4) OVER q > 0 THEN l.ltm_revenue / lag(l.ltm_revenue, 4) OVER q - 1 END AS ltm_revenue_growth,
       CASE WHEN l.ltm_revenue > 0 THEN l.ltm_gross_profit / l.ltm_revenue END     AS ltm_gross_margin,
       CASE WHEN l.ltm_revenue > 0 THEN l.ltm_operating_income / l.ltm_revenue END AS ltm_operating_margin,
       CASE WHEN l.ltm_revenue > 0 THEN l.ltm_net_income / l.ltm_revenue END       AS ltm_net_margin,
       l.ltm_net_income,
       l.ltm_operating_cash_flow - l.ltm_capex                                     AS ltm_fcf,
       l.ltm_operating_income + l.ltm_depreciation_amortization                    AS ltm_ebitda,
       l.total_debt - l.cash_and_equivalents - l.st_investments                    AS net_debt
FROM v_ltm l
WINDOW q AS (PARTITION BY l.ticker ORDER BY l.period_end);

-- --------------------------------------------------------------------------------------------------------
-- Valuation at the cutoff (D12): market cap from market_inputs; latest complete LTM; latest balance sheet.
-- LTM EBITDA falls back to the latest fiscal year when quarterly D&A is incomplete (S3-D11).
CREATE VIEW v_valuation_cutoff AS
WITH latest_ltm AS (
    SELECT DISTINCT ON (ticker) *
    FROM v_ratios_ltm
    WHERE ltm_revenue IS NOT NULL AND ltm_net_income IS NOT NULL
    ORDER BY ticker, period_end DESC
), latest_bs AS (
    SELECT DISTINCT ON (ticker) ticker, period_end AS bs_date, total_debt, cash_and_equivalents, st_investments
    FROM v_quarterly
    WHERE total_debt IS NOT NULL AND cash_and_equivalents IS NOT NULL AND st_investments IS NOT NULL
    ORDER BY ticker, period_end DESC
), latest_fy AS (
    SELECT DISTINCT ON (ticker) ticker, fiscal_year, ebitda, net_income_cagr_3y
    FROM v_ratios_annual
    WHERE revenue IS NOT NULL
    ORDER BY ticker, fiscal_year DESC
)
SELECT c.ticker, c.role, m.cutoff_date, m.close_2dp AS price,
       m.shares_outstanding / 1000000 AS shares_outstanding_m, m.shares_as_of,
       m.market_cap_usd / 1000000      AS market_cap,
       l.period_end AS ltm_period_end, l.ltm_revenue, l.ltm_net_income, l.ltm_fcf,
       COALESCE(l.ltm_ebitda, f.ebitda) AS ebitda_used,
       CASE WHEN l.ltm_ebitda IS NOT NULL THEN 'LTM ' || l.period_end
            WHEN f.ebitda IS NOT NULL THEN 'latest fiscal year FY' || f.fiscal_year || ' (quarterly D&A incomplete)' END AS ebitda_basis,
       b.bs_date, b.total_debt, b.cash_and_equivalents, b.st_investments,
       m.market_cap_usd / 1000000 + b.total_debt - b.cash_and_equivalents - b.st_investments AS enterprise_value,
       CASE WHEN l.ltm_net_income > 0 THEN m.market_cap_usd / 1000000 / l.ltm_net_income END AS pe_ltm,
       CASE WHEN l.ltm_revenue > 0 THEN (m.market_cap_usd / 1000000 + b.total_debt - b.cash_and_equivalents - b.st_investments) / l.ltm_revenue END AS ev_revenue_ltm,
       CASE WHEN COALESCE(l.ltm_ebitda, f.ebitda) > 0
            THEN (m.market_cap_usd / 1000000 + b.total_debt - b.cash_and_equivalents - b.st_investments) / COALESCE(l.ltm_ebitda, f.ebitda) END AS ev_ebitda,
       CASE WHEN l.ltm_net_income > 0 AND f.net_income_cagr_3y > 0
            THEN (m.market_cap_usd / 1000000 / l.ltm_net_income) / (100 * f.net_income_cagr_3y) END AS peg_historical_3y,
       (SELECT close_2dp FROM market_inputs WHERE ticker = 'RISK_FREE_10Y') AS risk_free_10y_pct
FROM companies c
JOIN market_inputs m USING (ticker)
LEFT JOIN latest_ltm l USING (ticker)
LEFT JOIN latest_bs b USING (ticker)
LEFT JOIN latest_fy f USING (ticker)
WHERE c.role <> 'benchmark';

-- Peer summary: latest fiscal year ratios + valuation, one row per company
CREATE VIEW v_peer_summary AS
SELECT DISTINCT ON (r.ticker)
       r.ticker, c.role, r.fiscal_year, r.revenue, r.revenue_growth, r.revenue_cagr_5y, r.gross_margin, r.operating_margin,
       r.net_margin, r.roe, r.roe_5y_avg, r.roic, r.quick_ratio, r.fcf_conversion, r.net_debt_to_ebitda, r.shares_change_5y,
       v.market_cap, v.enterprise_value, v.pe_ltm, v.ev_revenue_ltm, v.ev_ebitda, v.peg_historical_3y
FROM v_ratios_annual r
JOIN companies c USING (ticker)
LEFT JOIN v_valuation_cutoff v USING (ticker)
WHERE r.revenue IS NOT NULL
ORDER BY r.ticker, r.fiscal_year DESC;
