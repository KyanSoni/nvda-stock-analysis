-- Q3 (build guide Step 3): Has NVIDIA's free cash flow kept pace with net income?
-- FCF = operating cash flow - capex; conversion = FCF / net income (NULL when net income <= 0 or capex is a gap).
SET search_path = :"schema";
SELECT r.fiscal_year, a.net_income, r.fcf, round(r.fcf_conversion * 100, 1) AS fcf_conversion_pct
FROM v_ratios_annual r JOIN v_annual a USING (ticker, fiscal_year)
WHERE r.ticker = 'NVDA' AND r.fiscal_year >= (SELECT max(fiscal_year) - 9 FROM v_annual WHERE ticker = 'NVDA' AND revenue IS NOT NULL)
ORDER BY r.fiscal_year;
