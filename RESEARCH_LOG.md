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

## 2026-10-27

- Session status: ran, paper mode, 2/3 setups taken (first fills since the journal started).
- Trades (review.py --all): net Rs -1,854 on 2 trades, 1 day, win rate 0%, avg -0.75R.
  - 12:00 NIFTY03NOV22750CE LONG: Rs -1,245 (-1.04R), FALSE BREAKOUT — price never moved our
    way (best +0.1R), breakout failed immediately.
  - 13:30 NIFTY03NOV22750PE SHORT: Rs -609 (-0.47R), SCRATCH — reached T1 then stopped back at
    entry; costs/decay turned it red.
  - Rejected: 10:07 LONG (chasing, +12.3pts from signal), 10:55 LONG 22750CE (risk ~Rs 1,609 vs
    Rs 1,500 budget), 13:15 SHORT (against mixed-day chart read).
  - Pattern tables (outcome/side/time/trend/stretch/RSI/VIX/DTE) all 1 trade per bucket — far too
    few (review.py: need 30+ trades before touching any rule).
- Real-price straddle (lab.py cloud), ATM 09:20 entry, 30% per-leg stop:
  - expiry 2026-10-27 (0 days to expiry), strike 22650: +Rs 3,126/lot (CE stopped 09:20, PE held)
  - expiry 2026-11-03 (7 days to expiry), strike 22700: +Rs 4,422/lot (both legs held to close)
  - Running totals: DTE 0 → 1 day, net +Rs 3,126/lot, green 1/1; DTE 1 → 1 day, net +Rs
    4,585/lot, green 1/1; DTE 7 → 1 day, net +Rs 4,422/lot, green 1/1; DTE 8 → 1 day, net
    +Rs 3,212/lot, green 1/1.
- Observations: (1) the bot's first two live fills both lost, one a clean false breakout and one
  a scratch eaten by costs — exactly the kind of outcome the 4.8-year backtest predicts for this
  entry rule, no new information yet. (2) The straddle-selling side now has a 0-days-to-expiry
  data point (+Rs 3,126/lot) in addition to 1, 7, and 8 days — every bucket is still green, but
  each bucket has only 1 day of data. Sample size: 2 trades / 1 day for the bot, 1 day per DTE
  bucket for the straddle — not yet meaningful.

## 2026-10-28

- Session status: ran, paper mode, 0/3 setups taken. Day report: net P&L Rs 0 (+0.00%).
  Log shows a risk-gate rejection ("outside entry window") at 09:38, then "market closed for
  today" logged twice (10:02, 10:39). This "market closed" message looks like a false reading
  by the bot's own market-hours check, not a real holiday: cloud/options/2026-10-28.csv has full
  5-minute bars from 09:15 to 15:35 for both tracked expiries (2026-11-03, 2026-11-09), i.e. the
  market was open and trading normally all day. Flagging as an anomaly in the bot's own
  logs/market-hours logic (not fixed here — out of scope for this analysis-only review).
- Trades: no trades; journal.csv unchanged (still the 2 trades from 2026-10-27). review.py --all
  output is identical to the 2026-10-27 entry above (net Rs -1,854, 2 trades, 1 day) — nothing
  new to report there.
- Real-price straddle (lab.py cloud), ATM 09:20 entry, 30% per-leg stop:
  - expiry 2026-11-03 (6 days to expiry), strike 22550: +Rs 1,436/lot (CE stopped 12:45, PE held)
  - expiry 2026-11-09 (12 days to expiry), strike 22600: +Rs 170/lot (CE stopped 12:55, PE held)
  - Running totals (all days collected so far): DTE 0 — 1 day, net +Rs 3,126/lot, green 1/1;
    DTE 1 — 1 day, net +Rs 4,585/lot, green 1/1; DTE 6 — 1 day, net +Rs 1,436/lot, green 1/1;
    DTE 7 — 1 day, net +Rs 4,422/lot, green 1/1; DTE 8 — 1 day, net +Rs 3,212/lot, green 1/1;
    DTE 12 — 1 day, net +Rs 170/lot, green 1/1.
- Observations: (1) every straddle day collected so far (6 days now, across 6 different DTE
  buckets) has been green, but each bucket still has only a single day — one bad move
  on any of these buckets would flip it red, so this is not yet evidence of an edge either way.
  (2) The newest, closer-to-expiry day (6 DTE, +Rs 1,436/lot) is the smallest win so far, which
  is also consistent with plain noise given n=1 per bucket. Sample size: 1 day per DTE bucket —
  not yet meaningful.
