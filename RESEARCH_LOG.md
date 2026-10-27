# Research log: NIFTY paper-trading experiment (intraday, real option prices)

## 2026-10-23

- Session status: ran, paper mode, no entries (0/3 setups taken).
- Trades: no trades. All 3 candidate short-PE setups were rejected by the risk agent before entry:
  - 10:12 SHORT 22550PE: risked ~Rs 2,064 vs Rs 1,500 budget, cost Rs 10,940 vs Rs 75,000 cash limit
  - 11:00 SHORT 22500PE: risked ~Rs 2,117 vs Rs 1,500 budget, cost Rs 12,593 vs Rs 75,000 cash limit
  - 12:45 SHORT 22450PE: risked ~Rs 1,519 vs Rs 1,500 budget, cost Rs 11,138 vs Rs 75,000 cash limit
  - Net P&L Rs 0 (+0.00%).
- journal.csv: does not exist yet (no trades ever filled), so review.py has nothing to show.
- Real-price straddle (lab.py cloud): no options CSV collected for this date (option-price
  collection only started 26 Oct per README), so no straddle result for this day.
- Observation: all three rejections failed the same per-leg risk budget (~Rs 1,500), suggesting
  the risk agent is consistently sizing out single-lot NIFTY short-PE trades near current spot —
  not yet enough days to say if this is a pattern or a one-off vol/strike effect. Sample size: 1 day.

## 2026-10-26

- Session status: ran, paper mode, no entries (0/3 setups taken), no rejection detail logged in
  the day report (report shows only the summary line).
- Trades: no trades, net P&L Rs 0 (+0.00%).
- journal.csv: still does not exist (no trade has ever filled across the 2 sessions so far).
- Real-price straddle (lab.py cloud), ATM straddle 09:20 entry with 30% per-leg stop, real
  5-minute option prices:
  - expiry 2026-10-27 (1 day to expiry), strike 22500: +Rs 4,585/lot (CE leg stopped 09:50, PE held to close)
  - expiry 2026-11-03 (8 days to expiry), strike 22500: +Rs 3,212/lot (CE leg stopped 09:55, PE held to close)
  - Running totals: days-to-expiry 1 → 1 day, net +Rs 4,585/lot, green 1/1; days-to-expiry 8 → 1 day, net +Rs 3,212/lot, green 1/1.
- Observation: first real-price straddle day is a clean win on both expiries — the CE leg got
  stopped early and the PE leg carried the gain, consistent with a down/flat NIFTY move intraday.
  One day each for the 1-day and 8-day buckets is nowhere near meaningful; could easily reverse.
  Sample size: 1 day per bucket — not yet meaningful.
