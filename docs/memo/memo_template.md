# NVIDIA (NVDA): {rating}, 12-month target ${target:,.0f} ({exp_return:+.1%} vs ${price:.2f} on {price_date_long})

{author} · {memo_date_long} · Priced at the {price_date_long} close; filings to the Q2 FY2027 10-Q, plus the {res_q} results release of 17 Nov (unaudited: the 10-Q is not yet filed); consensus fetched {consensus_date_long}. Updates the {prev_memo_date_long} memo ({prev_rating}, target ${prev_target:,.0f}). Numbers and sources: `data/clean/step9/memo_numbers.csv`.

**Question.** Does NVIDIA's position in AI computing justify the future cash flows its share price implies? **Answer:** yes on our Base case, which is worth ${base:.0f} a share ({base_up:+.0%}), and ${comps:.0f} ({comps_up:+.0%}) on peers' multiples; at ${price:.2f} the market is discounting the leadership change more than the business. We stay {rating} on relative value, cut the target to ${target:,.0f} and give the Bear case more weight; the {res_q} 10-Q, due {tenq_due}, is the near-term test.

## What changed since {prev_memo_date_long}

- **The CEO left.** {lead_event} ({lead_source}). {lead_inv}.
- **Q3 beat its guide; the 10-Q did not come with it.** Revenue ${res_rev_bn:.1f}bn against ${res_guide_rev_bn:.1f}bn guided (Data Center ${res_dc_bn:.1f}bn), gross margin {res_gm:.1%} against {res_guide_gm:.1%}. NVIDIA has filed every 10-Q with its results since 2024, but not this one.
- **The outlook rose, the price fell.** FY2028 consensus moved to ${cons_fy28_bn:,.1f}bn from ${prev_cons_fy28_bn:,.1f}bn, while the shares fell {price_fall:.0%} from ${prev_price:.2f} ({prev_price_date_long}).

## Thesis

1. **Data Center growth holds through FY2028.** Base Data Center revenue grows {dc_g1:.0%} in FY2027 (nine months reported plus the {guide_q} guide) and {dc_g2:.0%} in FY2028, for total revenue of ${rev_fy27_bn:,.1f}bn and ${rev_fy28_bn:,.1f}bn, within {cons_gap_max:.1%} of consensus (${cons_fy27_bn:,.1f}bn, ${cons_fy28_bn:,.1f}bn). *{res_q}: passed.* *Next test:* {guide_q} revenue at or above the ${guide_rev_bn:.1f}bn guide.
2. **Gross margin stays at or above {gm_floor:.1%} through FY2029 while Vera Rubin ramps.** Base gross margin is {gm_fy27:.1%} in FY2027, easing to {gm_fy29:.1%} by FY2029. Every 4 points lower in every year costs ${gm4_cost:.2f} a share. *{res_q}: passed* ({res_gm:.1%}). *Under pressure:* the {guide_q} guide of {guide_gm_lo:.0%}–{guide_gm_hi:.0%} already sits at our FY2029 floor. *Next test:* {guide_q} gross margin at or above {guide_gm_lo:.0%}.
3. **The discount to peers narrows.** NVIDIA trades at {nv_pe:.1f}× NTM P/E and {nv_eve:.1f}× NTM EV/EBITDA against peer medians of {med_pe:.1f}× and {med_eve:.1f}×, though its NTM revenue growth ({nv_growth:.0%}) and gross margin ({nv_gm:.0%}) are the highest of the six. *Failing so far* ({pe_rel:.0%} of the peer median NTM P/E, from {prev_pe_rel:.0%}). *Test:* that share rising once the 10-Q is filed.

## What the market is pricing in (our variant view)

At ${price:.2f}, the market prices in less than our Base case: our Base DCF (${base:.2f}) balances only at a discount rate of {rev_wacc:.2%} instead of our {wacc:.2%}, or FY2028 Data Center growth of {rev_dc:.0%} instead of {dc_g2:.0%}. The fall since {prev_memo_date_long} came with results above guidance and higher consensus, so we read it as a governance discount, not a weaker outlook: at {nv_pe:.1f}× NTM earnings NVIDIA is the cheapest of the six. We price the governance risk through the scenario weights (Bear {w_bear:.0%}) rather than the discount rate; on those weights the DCF is ${dcf_w:.2f} ({dcf_up:+.0%}). Our view: the discount is real but too wide while the business beats its guidance; a clean 10-Q would start to close it.

## Valuation

Target = {w_dcf:.0%} DCF + {w_comps:.0%} comps. **DCF:** probability-weighted ${dcf_w:.2f} (Bear ${bear:.2f} at {w_bear:.0%}, Base ${base:.2f} at {w_base:.0%}, Bull ${bull:.2f} at {w_bull:.0%}; WACC {wacc:.2%}, terminal growth {g:.0%}), rolled forward 12 months at the cost of equity ({ke:.2%}) less the dividend yield ({div_yield:.2%}) to ${dcf_fwd:.2f}. **Comps:** ${comps:.2f}, the mean of NVIDIA's value at the peer-median NTM P/E (${imp_pe:.0f}) and NTM EV/EBITDA (${imp_eve:.0f}); across NTM multiples the range is ${comps_lo:.0f}–${comps_hi:.0f}, and on growth-adjusted EV/revenue ${reg_price:.0f}. The comps carry no governance discount; the DCF half does. **Target** = {w_dcf:.1f} × {dcf_fwd:.2f} + {w_comps:.1f} × {comps:.2f} = ${target_raw:.2f}, rounded to ${target:,.0f}. Terminal value is {tv_share:.0%} of Base EV; the perpetuity implies {impl_x:.1f}× year-5 EV/EBITDA (peers {ltm_eve_med:.1f}× today). The two methods point in opposite directions (DCF {dcf_up:+.0%}, comps {comps_up:+.0%}); the rating rests on relative value.

**Scorecard:** {nv_score}/{score_max}, the highest of six (QCOM {qcom_score}); only FCF conversion misses full marks ({sc_fcf:.0%} vs {sc_fcf_pass:.0%}). It measures quality on FY2026 filings, not price or governance (QCOM's DCF: {qcom_up:+.0%}).

## Risks and what would change our mind

| Risk | What we watch | We would cut the rating if |
|---|---|---|
| Leadership and governance | The {res_q} 10-Q (due {tenq_due}); the independent investigation; the CEO search | The 10-Q is late, revises the 17 Nov figures or reports a material weakness: we would suspend the rating until the numbers are confirmed |
| AI capex slows | Data Center revenue each quarter; hyperscaler capex guidance | FY2028 revenue tracks the Bear case (${bear_rev28_bn:,.0f}bn vs Base ${rev_fy28_bn:,.0f}bn; Bear value ${bear:.0f}) |
| Custom chips at hyperscalers | Broadcom and Marvell AI revenue vs NVIDIA Data Center | NVIDIA's NTM revenue growth falls below Broadcom's ({avgo_growth:.0%} today vs NVIDIA {nv_growth:.0%}) |
| Memory costs and pricing | GAAP gross margin vs the {guide_gm_lo:.0%}–{guide_gm_hi:.0%} {guide_q} guide | Gross margin below {gm_floor_cut:.0%} for two quarters (−4 points ≈ −${gm4_cost:.0f} a share) |
| China export rules | China revenue disclosure; guidance exclusions (the {guide_q} guide assumes no China Data Center compute) | A guidance cut attributed to export rules |

## Catalysts

{catalysts}

Rating rule: Buy above {buy_above:+.0%} expected 12-month total return, Sell below {sell_below:+.0%}, else Hold. A portfolio project, not investment advice.

<div style="page-break-after: always;"></div>

## Exhibits

**Exhibit 1. Football field, USD per share** (price ${price:.2f} marked)

![Football field](exhibits/football_field.svg)

**Exhibit 2. Valuation summary**

{ex_valuation}

**Exhibit 3. Base-case DCF value per share: WACC (rows) × terminal growth (columns).** Bold: the cell closest to the price.

{ex_grid}

**Exhibit 4. Peers on NTM figures (calendarised to Nov 2026–Oct 2027)**

{ex_comps}

**Exhibit 5. Scenarios**

{ex_scen}

Sources: SEC 10-K and 10-Q filings (XBRL companyfacts, checked against the filings); Yahoo Finance consensus via yfinance, cross-checked with Nasdaq (19 Nov: FY2028 EPS outside the 5% tolerance, issue I-90); daily prices to the cutoff; NVIDIA's 8-Ks of 12 and 17 Nov 2026; press reports of the board's investigation (Constellation Research, 12 Nov 2026); project decision log S3–S9 and R-D1 to R-D7, issue log I-58 to I-70 and I-89.
