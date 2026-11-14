# Interview prep: defending the NVIDIA call

Answers to the eight practice questions in the build guide, with this project's numbers. Practise them out loud until each
takes under two minutes; the numbers are in `data/clean/step9/memo_numbers.csv` and the memo. Priced at the 2 Nov 2026
cutoff; refresh after the 17 Nov Q3 results.

**The 20-second version.** "I rate NVIDIA a Buy with a $260 target, about 29% upside. My DCF says the stock is fully
priced. It only works at a 12% discount rate against my 13.9%. But it trades at 14 times next year's earnings against 26
for its peers, despite growing faster with higher margins. I think the market's doubt about how long those earnings last
is too harsh, and I weighted DCF and comps 50/50."

## 1. Walk me through your DCF in two minutes

- **Cash flows:** unlevered free cash flow = EBIT × (1 − tax) + D&A − capex − increase in working capital, from my
  3-statement forecast for FY2027–FY2031. I don't add back stock-based compensation, because it's a real cost. Base case:
  $182bn, $308bn, $410bn, $464bn, $491bn.
- **Forecast:** anchored to consensus for two years. My FY2027 and FY2028 revenue are within 0.1% of it. Data Center growth
  then fades from 72% to 6% by FY2031, and gross margin from 74.5% to 71%.
- **Discount rate:** CAPM, with a 60-month beta of 2.2 against the S&P 500, Blume-adjusted to 1.81. Risk-free 4.91%, equity
  risk premium 5%, so cost of equity 13.95%. Debt is under 1% of capital, so WACC is 13.87%.
- **Timing:** I only count the part of FY2027 after the July balance sheet, because first-half cash is already in it.
  Mid-year discounting.
- **Terminal value:** 3% perpetuity growth. It's 67% of enterprise value and implies 7.2× year-5 EBITDA. As a check, peers
  trade at 26× today.
- **Bridge:** EV $4.02tn, plus cash, short-term investments and $42.8bn of listed equity stakes, less $33.4bn of debt,
  divided by 24.3bn diluted shares. Base $168.42; Bear $66, Bull $227; probability-weighted $157.47.

## 2. Why those peers? Why Marvell and not TSMC?

The five are US-listed chip *designers* competing for the same data-center and compute spending. AMD (GPUs and CPUs),
Broadcom and Marvell (custom AI chips and networking) are the direct AI substitutes. Qualcomm and Intel are mature
comparisons. TSMC is a supplier, not a competitor: it manufactures NVIDIA's chips, with a capital-heavy foundry model and
different margins. It also files as a foreign issuer under IFRS (20-F, 6-K), so its numbers aren't on the same US-GAAP SEC
basis as the rest. Marvell sells custom accelerators to the same hyperscalers, so it belongs (decision D1).

## 3. What growth is the market pricing in, and do you agree?

Reverse DCF, one lever at a time, everything else at my Base case:
- **Growth:** the price needs FY2028 Data Center growth of 110% instead of my 72%. That's $838bn of FY2028 revenue against
  $692bn.
- **Discount rate:** or a WACC of 12.05% instead of 13.87%.
- **Terminal growth:** or 5.35% instead of 3%.

I don't believe the growth version: 110% on that base is beyond consensus. The discount-rate version is plausible,
though. My 2.2 beta reflects the 2021–2026 swings, and a 12% cost of equity for the most profitable company in the group
isn't extreme. So the price is defensible if you think NVIDIA is less risky than its trailing volatility says.

## 4. What happens to your value if WACC rises 1 point?

Base value falls by about **$14 a share, from $168.42 to $154.44** (WACC 13.87% → 14.87%). It's asymmetric: 1 point lower
adds about $17. Terminal growth is similar, with 1 point higher adding $12 and 1 point lower taking off $10. The full grid
is Exhibit 3 of the memo; the cell nearest the price is 12% WACC and 3% growth.

## 5. How do the three statements link if depreciation rises by $10?

Take NVIDIA's 17% tax rate:
- **Income statement:** operating income −$10, pre-tax −$10, tax −$1.70, **net income −$8.30**.
- **Cash flow:** net income −$8.30, add back depreciation +$10, so **operating cash flow +$1.70** (the tax saving). No
  change to capex.
- **Balance sheet:** cash **+$1.70**; net PP&E **−$10** (more accumulated depreciation). Assets −$8.30, equity (retained
  earnings) −$8.30. It balances.

In a DCF, unlevered FCF rises by $1.70 (the tax shield), so value rises slightly.

## 6. Why EV/EBITDA rather than P/E, or both?

Both are in the headline, because each covers the other's weakness:
- **EV/EBITDA:** ignores capital structure and tax differences. That matters here, because Intel's and Qualcomm's tax
  rates are distorted.
- **P/E:** is what investors actually quote.

Both are on calendarised next-twelve-month figures. Fiscal years end in January, September, November and December across
the group, so trailing multiples would compare different periods. I show EV/revenue but leave it out of the headline,
because NVIDIA's 75% gross margin is far above every peer's and a revenue multiple undervalues it.

## 7. What is the biggest risk to your thesis, and how would you know it is happening?

The biggest risk is a slowdown in AI data-center spending. I'd see it first in NVIDIA's quarterly Data Center revenue
against guidance, which is $108.0bn for Q3 on 17 Nov, and in hyperscaler capex guidance in late January to early February.
If FY2028 revenue tracks my Bear case ($458bn against $692bn), the DCF is worth $66 and I'd cut the rating. Second is
margin pressure from memory costs: two quarters below 70% gross margin would cost about $12 a share and also cut the
rating.

## 8. The P/E test fails on your scorecard but you still rate it a Buy. Why?

The scorecard's P/E test uses *trailing* GAAP P/E: 25.2× against a 25× pass mark, a near miss. Trailing earnings
understate a company growing 107% next year. On next-twelve-month P/E, NVIDIA is 14.0×, the lowest of the six. Also, the
scorecard measures business quality, not price: NVIDIA scores 18/20, but so does Qualcomm, whose DCF shows −62%. The rating
comes from the valuation, not the scorecard.

## CV line

> Built an equity research valuation of NVIDIA (Buy, $260 target): 3-statement model with three scenarios, DCF with
> sensitivity and reverse-DCF analysis, and calendarised comps against 5 peers, from SEC XBRL data verified against the
> filings (Python, PostgreSQL, Excel).

## LinkedIn post (draft; attach the football-field chart)

> I valued NVIDIA two ways, and they disagree. My DCF says the stock is fully priced: it only works at a 12% discount rate
> against my 13.9%. On comparable companies, it trades at 14× next year's earnings against 26× for its peers, despite the
> highest growth and margins in the group. My call is Buy with a $260 target, because I think the market is too sceptical
> about how long NVIDIA's earnings last. Full model, code and two-page memo: [GitHub link]
