-- Q2 (build guide Step 3): How far is NVIDIA's gross margin above the peer median?
-- Latest fiscal year of each company (own fiscal labels, S3-D8); median over the five peers, NVIDIA excluded.
SET search_path = :"schema";
WITH latest AS (
    SELECT DISTINCT ON (ticker) ticker, fiscal_year, gross_margin
    FROM v_ratios_annual WHERE gross_margin IS NOT NULL ORDER BY ticker, fiscal_year DESC
), peers AS (
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY gross_margin) AS peer_median
    FROM latest JOIN companies USING (ticker) WHERE role = 'peer'
)
SELECT l.ticker, l.fiscal_year, round(l.gross_margin * 100, 1) AS gross_margin_pct,
       round(p.peer_median::numeric * 100, 1) AS peer_median_pct,
       round((l.gross_margin - p.peer_median::numeric) * 100, 1) AS gap_vs_peer_median_pp
FROM latest l CROSS JOIN peers p
ORDER BY l.gross_margin DESC;
