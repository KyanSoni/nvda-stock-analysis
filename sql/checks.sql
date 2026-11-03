-- Step 3b integrity checks run inside the database after loading. One row per check: check, passed, detail.
\set ON_ERROR_STOP on
SET search_path = :"schema";
SELECT 'DB1_row_counts_match_load_files' AS check,
       bool_and(m.rows = t.n) AS passed,
       string_agg(m.table_name || ' ' || t.n || '/' || m.rows, '; ' ORDER BY m.table_name) AS detail
FROM load_manifest m
JOIN (SELECT 'companies' AS table_name, count(*) AS n FROM companies UNION ALL
      SELECT 'line_items', count(*) FROM line_items UNION ALL
      SELECT 'facts', count(*) FROM facts UNION ALL
      SELECT 'split_factors', count(*) FROM split_factors UNION ALL
      SELECT 'prices', count(*) FROM prices UNION ALL
      SELECT 'market_inputs', count(*) FROM market_inputs) t USING (table_name)
UNION ALL
SELECT 'DB2_annual_candidates_agree',
       count(*) FILTER (WHERE n_values > 1) = 0,
       count(*) FILTER (WHERE n_values > 1) || ' with conflicting values; ' ||
       count(*) FILTER (WHERE n_values = 1) || ' same-value duplicates (dates a few days apart), one kept'
FROM (SELECT u.ticker, u.line_item, u.fiscal_year, count(DISTINCT u.amount) AS n_values
      FROM v_facts_used u JOIN line_items li USING (line_item)
      WHERE (li.period_type = 'duration' AND u.fiscal_period = 'FY') OR (li.period_type = 'instant' AND u.fiscal_period = 'Q4')
      GROUP BY 1, 2, 3 HAVING count(*) > 1) d
UNION ALL
SELECT 'DB3_quarterly_candidates_agree',
       count(*) FILTER (WHERE n_values > 1) = 0,
       count(*) FILTER (WHERE n_values > 1) || ' with conflicting values; ' ||
       count(*) FILTER (WHERE n_values = 1) || ' same-value duplicates (dates a few days apart), one kept'
FROM (SELECT ticker, line_item, period_end, count(DISTINCT amount) AS n_values FROM v_facts_used
      WHERE fiscal_period IN ('Q1','Q2','Q3','Q4') AND value_basis <> 'reported_annual'
      GROUP BY 1, 2, 3 HAVING count(*) > 1) d
UNION ALL
SELECT 'DB4_every_company_has_annual_ratios',
       count(*) = (SELECT count(*) FROM companies WHERE role <> 'benchmark'),
       count(*) || ' companies with ratio rows'
FROM (SELECT DISTINCT ticker FROM v_ratios_annual) x
UNION ALL
SELECT 'DB5_single_cutoff_date', count(DISTINCT cutoff_date) = 1, 'cutoff ' || string_agg(DISTINCT cutoff_date::text, ',')
FROM market_inputs
UNION ALL
SELECT 'DB6_valuation_for_every_company',
       count(*) FILTER (WHERE market_cap IS NOT NULL AND enterprise_value IS NOT NULL AND ev_revenue_ltm IS NOT NULL)
         = (SELECT count(*) FROM companies WHERE role <> 'benchmark'),
       string_agg(ticker || ':' || CASE WHEN enterprise_value IS NULL THEN 'no EV' ELSE 'ok' END, ' ' ORDER BY ticker)
FROM v_valuation_cutoff;
