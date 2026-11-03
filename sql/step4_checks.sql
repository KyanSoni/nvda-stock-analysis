-- Step 4 integrity checks run inside the database. One row per check: check, passed, detail.
\set ON_ERROR_STOP on
SET search_path = :"schema";
SELECT 'SC1_ten_tests_per_company' AS check,
       bool_and(n = 10) AND count(*) = (SELECT count(*) FROM companies WHERE role <> 'benchmark') AS passed,
       string_agg(ticker || ':' || n, ' ' ORDER BY ticker) AS detail
FROM (SELECT ticker, count(*) AS n FROM v_scorecard_detail GROUP BY ticker) x
UNION ALL
SELECT 'SC2_points_valid_and_totals_add_up',
       bool_and(points IN (0, 1, 2)) AND (SELECT bool_and(total = coalesce(t1_revenue_cagr, 0) + coalesce(t2_pe, 0) + coalesce(t3_peg, 0)
            + coalesce(t4_roe, 0) + coalesce(t5_quick_ratio, 0) + coalesce(t6_gross_margin, 0) + coalesce(t7_fcf_conversion, 0)
            + coalesce(t8_net_debt_ebitda, 0) + coalesce(t9_roic_wacc, 0) + coalesce(t10_share_count, 0)
            AND total <= max_possible) FROM v_scorecard),
       count(*) || ' test rows; results ' || string_agg(DISTINCT result, '/')
FROM v_scorecard_detail
UNION ALL
SELECT 'SC3_beta_full_window',
       bool_and(months = (SELECT value FROM scorecard_params WHERE key = 'beta_months')) AND count(*) > 0,
       string_agg(ticker || '/' || benchmark || ' ' || months || 'm ' || first_month || '..' || last_month, '; ' ORDER BY ticker, benchmark)
FROM v_beta
UNION ALL
SELECT 'SC4_consensus_eps_for_every_company',
       bool_and(estimates_available),
       string_agg(ticker || ':' || CASE WHEN estimates_available THEN 'ok' ELSE 'MISSING' END, ' ' ORDER BY ticker)
FROM v_peg
UNION ALL
SELECT 'SC5_wacc_for_every_company',
       bool_and(wacc IS NOT NULL) AND count(*) = (SELECT count(*) FROM companies WHERE role <> 'benchmark'),
       string_agg(ticker || ':' || coalesce(round((wacc * 100)::numeric, 2)::text || '%', 'NULL'), ' ' ORDER BY ticker)
FROM v_wacc;
