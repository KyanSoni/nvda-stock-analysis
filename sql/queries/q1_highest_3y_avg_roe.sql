-- Q1 (build guide Step 3): Which company has the highest 3-year average ROE?
-- Latest fiscal year per company; ROE = net income / average equity (S3-D3). NULL where equity <= 0.
SET search_path = :"schema";
SELECT DISTINCT ON (ticker) ticker, fiscal_year AS latest_fiscal_year, round(roe_3y_avg * 100, 1) AS roe_3y_avg_pct
FROM v_ratios_annual
WHERE revenue IS NOT NULL
ORDER BY ticker, fiscal_year DESC;
