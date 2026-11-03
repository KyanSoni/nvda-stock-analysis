-- Step 4: beta, provisional WACC, forward PEG and the 20-point scorecard (decisions S4-D1 to S4-D8).
-- Built on the Step 3 views; every threshold and assumption comes from the tables scorecard_rules / scorecard_params.
\set ON_ERROR_STOP on
SET search_path = :"schema";

-- Latest fiscal year per company (own fiscal labels, D5), with the inputs the WACC needs
CREATE VIEW v_latest_annual AS
SELECT DISTINCT ON (r.ticker)
       r.*, a.interest_expense, a.total_debt AS fy_total_debt,
       (SELECT p.total_debt FROM v_annual p WHERE p.ticker = r.ticker AND p.fiscal_year = r.fiscal_year - 1) AS prev_total_debt
FROM v_ratios_annual r
JOIN v_annual a USING (ticker, fiscal_year)
WHERE r.revenue IS NOT NULL
ORDER BY r.ticker, r.fiscal_year DESC;

-- Beta: monthly total returns (adj_close at each month's last trading day), the last N months before the cutoff month,
-- slope of company on benchmark (regr_slope = covar_pop / var_pop)
CREATE VIEW v_beta AS
WITH cutoff AS (SELECT max(cutoff_date) AS d FROM market_inputs),
months AS (SELECT value::int AS n FROM scorecard_params WHERE key = 'beta_months'),
me AS (
    SELECT DISTINCT ON (p.ticker, date_trunc('month', p.price_date))
           p.ticker, date_trunc('month', p.price_date)::date AS month, p.adj_close
    FROM prices p, cutoff c
    WHERE p.price_date < date_trunc('month', c.d)
    ORDER BY p.ticker, date_trunc('month', p.price_date), p.price_date DESC),
ret AS (
    SELECT ticker, month, adj_close / lag(adj_close) OVER (PARTITION BY ticker ORDER BY month) - 1 AS r FROM me),
win AS (
    SELECT r.* FROM ret r, months n, (SELECT max(month) AS last FROM me) m
    WHERE r.r IS NOT NULL AND r.month > (m.last - make_interval(months => n.n))::date)
SELECT s.ticker, b.ticker AS benchmark,
       regr_slope(s.r, b.r) AS beta, corr(s.r, b.r) AS correlation,
       count(*) AS months, min(s.month) AS first_month, max(s.month) AS last_month
FROM win s
JOIN win b ON b.month = s.month
JOIN companies cs ON cs.ticker = s.ticker AND cs.role <> 'benchmark'
JOIN companies cb ON cb.ticker = b.ticker AND cb.role = 'benchmark'
GROUP BY s.ticker, b.ticker;

-- Provisional WACC (CAPM; book debt, market equity), revisited in Step 6
CREATE VIEW v_wacc AS
WITH p AS (SELECT max(value) FILTER (WHERE key = 'equity_risk_premium') AS erp FROM scorecard_params),
k AS (
    SELECT v.ticker, v.cutoff_date, v.risk_free_10y_pct / 100 AS risk_free, b.beta, b.months AS beta_months, p.erp,
           v.risk_free_10y_pct / 100 + b.beta * p.erp AS cost_of_equity,
           l.fiscal_year, l.interest_expense, l.fy_total_debt, l.prev_total_debt,
           CASE WHEN l.fy_total_debt + l.prev_total_debt > 0
                THEN l.interest_expense / ((l.fy_total_debt + l.prev_total_debt) / 2) END AS cost_of_debt_pretax,
           l.tax_rate_used, v.market_cap, v.total_debt AS debt_at_bs_date, v.bs_date
    FROM v_valuation_cutoff v
    JOIN v_latest_annual l USING (ticker)
    JOIN v_beta b ON b.ticker = v.ticker AND b.benchmark = (SELECT 'SPY'::text)
    CROSS JOIN p)
SELECT k.*,
       debt_at_bs_date / (debt_at_bs_date + market_cap) AS debt_weight,
       CASE WHEN debt_at_bs_date = 0 THEN cost_of_equity
            WHEN cost_of_debt_pretax IS NULL THEN NULL
            ELSE market_cap / (debt_at_bs_date + market_cap) * cost_of_equity
                 + debt_at_bs_date / (debt_at_bs_date + market_cap) * cost_of_debt_pretax * (1 - tax_rate_used) END AS wacc
FROM k;

-- Forward PEG: trailing P/E / (100 x consensus EPS growth, next fiscal year over current fiscal year)
CREATE VIEW v_peg AS
SELECT v.ticker, v.pe_ltm,
       e0.avg AS eps_current_fy, e1.avg AS eps_next_fy, e0.analysts AS analysts_current_fy, e1.analysts AS analysts_next_fy,
       CASE WHEN e0.avg > 0 THEN e1.avg / e0.avg - 1 END AS fwd_eps_growth,
       CASE WHEN v.pe_ltm > 0 AND e0.avg > 0 AND e1.avg / e0.avg - 1 > 0
            THEN v.pe_ltm / (100 * (e1.avg / e0.avg - 1)) END AS peg_forward,
       (e0.avg IS NOT NULL AND e1.avg IS NOT NULL) AS estimates_available,
       e0.snapshot_id, e0.fetched_at_utc
FROM v_valuation_cutoff v
LEFT JOIN estimates e0 ON e0.ticker = v.ticker AND e0.kind = 'eps' AND e0.period = '0y'
LEFT JOIN estimates e1 ON e1.ticker = v.ticker AND e1.kind = 'eps' AND e1.period = '+1y';

-- One value per company and test; null_fails = a missing value counts as a scored fail
CREATE VIEW v_scorecard_metrics AS
WITH l AS (SELECT * FROM v_latest_annual),
gm AS (SELECT ticker, gross_margin FROM l)
SELECT ticker, fiscal_year, 1 AS test_no, revenue_cagr_5y AS value, false AS null_fails FROM l
UNION ALL
SELECT v.ticker, l.fiscal_year, 2, v.pe_ltm, coalesce(v.ltm_net_income <= 0, false) FROM v_valuation_cutoff v JOIN l USING (ticker)
UNION ALL
SELECT g.ticker, l.fiscal_year, 3, g.peg_forward, g.estimates_available FROM v_peg g JOIN l USING (ticker)
UNION ALL
SELECT ticker, fiscal_year, 4, roe_5y_avg, false FROM l
UNION ALL
SELECT ticker, fiscal_year, 5, quick_ratio, false FROM l
UNION ALL
SELECT l.ticker, l.fiscal_year, 6,
       l.gross_margin - (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY o.gross_margin)
                         FROM gm o WHERE o.ticker <> l.ticker AND o.gross_margin IS NOT NULL)::numeric,
       false FROM l
UNION ALL
SELECT ticker, fiscal_year, 7, fcf_conversion, coalesce(net_income <= 0, false) FROM l JOIN v_annual USING (ticker, fiscal_year)
UNION ALL
SELECT ticker, fiscal_year, 8, net_debt_to_ebitda, coalesce(ebitda <= 0, false) FROM l
UNION ALL
SELECT l.ticker, l.fiscal_year, 9, l.roic - w.wacc, false FROM l LEFT JOIN v_wacc w USING (ticker)
UNION ALL
SELECT ticker, fiscal_year, 10, shares_change_5y, false FROM l;

CREATE VIEW v_scorecard_detail AS
SELECT m.ticker, m.fiscal_year, m.test_no, r.name, r.metric, m.value, r.direction, r.pass_value, r.near_value,
       pts.points,
       CASE WHEN m.value IS NULL AND NOT m.null_fails THEN 'not scored'
            WHEN m.value IS NULL THEN 'fail'
            WHEN pts.points = 2 THEN 'pass' WHEN pts.points = 1 THEN 'near miss' ELSE 'fail' END AS result,
       CASE WHEN m.value IS NULL AND m.null_fails THEN r.fail_when_null
            WHEN m.value IS NULL THEN 'input missing' ELSE '' END AS reason
FROM v_scorecard_metrics m
JOIN scorecard_rules r USING (test_no)
CROSS JOIN LATERAL (SELECT CASE
        WHEN m.value IS NULL THEN 0
        WHEN r.direction = 'higher' AND m.value > r.pass_value THEN 2
        WHEN r.direction = 'higher' AND m.value >= r.near_value THEN 1
        WHEN r.direction = 'lower' AND m.value < r.pass_value THEN 2
        WHEN r.direction = 'lower' AND m.value <= r.near_value THEN 1
        ELSE 0 END AS points) pts;

CREATE VIEW v_scorecard AS
SELECT ticker, fiscal_year,
       max(points) FILTER (WHERE test_no = 1 AND result <> 'not scored')  AS t1_revenue_cagr,
       max(points) FILTER (WHERE test_no = 2 AND result <> 'not scored')  AS t2_pe,
       max(points) FILTER (WHERE test_no = 3 AND result <> 'not scored')  AS t3_peg,
       max(points) FILTER (WHERE test_no = 4 AND result <> 'not scored')  AS t4_roe,
       max(points) FILTER (WHERE test_no = 5 AND result <> 'not scored')  AS t5_quick_ratio,
       max(points) FILTER (WHERE test_no = 6 AND result <> 'not scored')  AS t6_gross_margin,
       max(points) FILTER (WHERE test_no = 7 AND result <> 'not scored')  AS t7_fcf_conversion,
       max(points) FILTER (WHERE test_no = 8 AND result <> 'not scored')  AS t8_net_debt_ebitda,
       max(points) FILTER (WHERE test_no = 9 AND result <> 'not scored')  AS t9_roic_wacc,
       max(points) FILTER (WHERE test_no = 10 AND result <> 'not scored') AS t10_share_count,
       sum(points) AS total,
       2 * count(*) FILTER (WHERE result <> 'not scored') AS max_possible,
       count(*) FILTER (WHERE result <> 'not scored') AS tests_scored
FROM v_scorecard_detail
GROUP BY ticker, fiscal_year;
