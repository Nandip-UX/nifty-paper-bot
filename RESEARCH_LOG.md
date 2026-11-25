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

## 2026-10-29

- Session status: ran normally, paper mode, 2/3 setups taken.
- Trades: net Rs 1,684 on 2 trades — 11:50 NIFTY03NOV22800CE LONG stop loss Rs -1,316 (-1.1R,
  FALSE BREAKOUT, price never moved our way); 13:25 NIFTY03NOV22800CE LONG target 2 Rs +3,000
  (+2.6R, TREND RUN to T2). 3 further LONGs rejected (risk ~Rs 1,561-1,620 vs Rs 1,500 budget).
- review.py --all (now 4 trades/2 days): net Rs -169, win rate 25%, worst day Rs -1,854, best
  day Rs 1,684. Too few trades for the pattern table.
- Real-price straddle: DTE 5 (expiry 11-03) strike 22700: +Rs 4,097/lot (CE stopped 10:05, PE
  held) → bucket now 1 day, net +4,097, green 1/1. DTE 11 (expiry 11-09) strike 22750: +Rs
  3,841/lot (CE stopped 10:25, PE held) → bucket now 1 day, net +3,841, green 1/1.
- Observation: every straddle day is still green (8 days across 8 DTE buckets), while the bot's
  own live trades are flat-to-slightly negative — same story as the 4.8-year backtest. Sample
  size: 1 day per DTE bucket, 2 trading days for the bot — not yet meaningful.

## 2026-10-30

- Session status: the bot never entered its trading loop today — all 4 scheduled checks logged
  "market closed for today" (the same false reading flagged as a one-off anomaly on 2026-10-28,
  which turns out to recur every weekday from here through 2026-11-20 — see later entries). No
  report.md was written, no journal entries, no rejections logged.
- Trades: none (bot loop never ran).
- Real-price straddle (collected independently of bot.py, unaffected by the bug): DTE 4 (expiry
  11-03) strike 22950: +Rs 1,343/lot (CE stopped 09:50, PE held) → bucket 1 day, net +1,343,
  green 1/1. DTE 10 (expiry 11-09) strike 22950: -Rs 1,216/lot (CE stopped 11:50, PE held) →
  bucket 1 day, net -1,216, green 0/1 — first red straddle day in the dataset.
- Observation: option-price collection keeps working even on days the bot's own market-hours
  check misfires, so the straddle research is unaffected. First loss appears at 10 days to
  expiry. Sample size: 1 day per DTE bucket — not yet meaningful.

## 2026-11-02

- Session status: same "market closed for today" bug as 2026-10-30 (4/4 checks). No trades.
- Real-price straddle: DTE 1 (expiry 11-03) strike 23250: -Rs 4,122/lot (CE stopped 09:45, PE
  stopped 13:05 — both legs stopped) → bucket 2 days, net +463, green 1/2. DTE 7 (expiry 11-09)
  strike 23300: +Rs 819/lot (both legs held) → bucket 2 days, net +5,240, green 2/2.
- Observation: the 1-day-to-expiry bucket takes its first loss, both legs stopped the same day —
  consistent with a large intraday swing close to expiry. Sample size: 2 days per bucket.

## 2026-11-03

- Session status: same bug continues (4/4 "market closed"). No trades.
- Real-price straddle: DTE 0, expiry day, strike 23550: +Rs 2,602/lot (CE stopped 09:25, PE
  held) → bucket 2 days, net +5,729, green 2/2. DTE 6 (expiry 11-09) strike 23550: +Rs 66/lot
  (CE stopped 10:30, PE held) → bucket 2 days, net +1,502, green 2/2.
- Observation: the expiry-day (DTE 0) bucket is now 2/2 and has the largest total Rs of any
  bucket so far — still only 2 days of data.

## 2026-11-04

- Session status: same bug continues (12th straight weekday without a bot session). No trades.
- Real-price straddle: DTE 5 (expiry 11-09) strike 23850: -Rs 4,694/lot (CE held, PE stopped
  12:10) → bucket 2 days, net -597/lot, green 1/2 — second red day. DTE 13, new far-expiry
  bucket (expiry 11-17), strike 23850: +Rs 2,376/lot (both legs held) → bucket 1 day, net
  +2,376, green 1/1.
- Observation: the DTE 5 bucket flips net negative; the small handful of losses so far are
  spread across both near- and mid-expiry buckets, not concentrated at expiry.

## 2026-11-05

- Session status: same bug continues. No trades.
- Real-price straddle: DTE 4 (expiry 11-09) strike 24350: +Rs 2,346/lot (CE stopped 09:50, PE
  held) → bucket 2 days, net +3,688, green 2/2. DTE 12 (expiry 11-17) strike 24350: +Rs 51/lot
  (CE stopped 13:00, PE held) → bucket 2 days, net +221, green 2/2.
- Observation: no new information — still far too few days per bucket to read anything into it.

## 2026-11-06

- Session status: same bug continues. No trades.
- Real-price straddle: DTE 3, new bucket (expiry 11-09), strike 24450: +Rs 5,171/lot (CE
  stopped 09:45, PE held) → bucket 1 day, net +5,171, green 1/1. DTE 11 (expiry 11-17) strike
  24500: +Rs 5,404/lot (CE stopped 09:45, PE held) → bucket 2 days, net +9,245, green 2/2.
- Observation: the CE leg keeps getting stopped early on most days collected so far while the
  PE leg rides — consistent with NIFTY trending up through this stretch rather than a
  directionless straddle edge.

## 2026-11-09

- Session status: same bug continues. No trades. (2026-11-10, the next trading day, is a known
  NSE holiday — Diwali-Balipratipada — so correctly has no session; not counted as missing.)
- Real-price straddle: DTE 0, expiry day, strike 24900: +Rs 3,810/lot (CE stopped 09:25, PE
  held) → bucket 3 days, net +9,539, green 3/3. DTE 8 (expiry 11-17) strike 24900: +Rs 3,056/lot
  (both legs held) → bucket 2 days, net +6,268, green 2/2.
- Observation: the expiry-day bucket is now the largest at 3/3 green — still nowhere near
  enough to call it an edge.

## 2026-11-11

- Session status: same "market closed for today" bug continues. No trades.
- Real-price straddle: DTE 6 (expiry 11-17) strike 25400: +Rs 1,865/lot (CE held, PE stopped
  13:10) → bucket 3 days, net +3,367, green 3/3. DTE 12, new far-expiry bucket (expiry 11-23),
  strike 25450: -Rs 398/lot (CE held, PE stopped 13:30) → bucket 3 days, net -177, green 2/3 —
  third red day, and the first where the PE leg (not CE) got stopped.
- Observation: first two-sided evidence (a PE-side stop) rather than every loss coming from the
  same direction — small positive sign the sample isn't just one-way luck, but still n=2-3.

## 2026-11-12

- Session status: same bug continues. No trades.
- Real-price straddle: DTE 5 (expiry 11-17) strike 25300: +Rs 3,913/lot (both legs held) →
  bucket 3 days, net +3,315, green 2/3. DTE 11 (expiry 11-23) strike 25300: +Rs 1,879/lot (both
  legs held) → bucket 3 days, net +11,124, green 3/3.
- Observation: nothing new; buckets still sit at 2-3 days each.

## 2026-11-13

- Session status: same bug continues. No trades.
- Real-price straddle: DTE 4 (expiry 11-17) strike 25100: -Rs 402/lot (CE stopped 09:45, PE
  held) → bucket 3 days, net +3,286, green 2/3. DTE 10 (expiry 11-23) strike 25150: +Rs 3,636/lot
  (both legs held) → bucket 2 days, net +2,420, green 1/2.
- Observation: no new information.

## 2026-11-16

- Session status: same bug continues. No trades.
- Real-price straddle: DTE 1 (expiry 11-17) strike 25250: -Rs 1,421/lot (CE stopped 09:45, PE
  held) → bucket 3 days, net -958, green 1/3 — the 1-day-to-expiry bucket is now net negative.
  DTE 7 (expiry 11-23) strike 25250: +Rs 1,706/lot (both legs held) → bucket 3 days, net +6,946,
  green 3/3.
- Observation: DTE 1 is the only bucket net red after 3 samples — worth watching since
  near-expiry behaviour is the open research question, but n=3 proves nothing yet.

## 2026-11-17

- Session status: same bug continues — the 15th weekday since 2026-10-30 affected (excluding
  the 2026-11-10 holiday). No trades.
- Real-price straddle: DTE 0, expiry day, strike 25350: -Rs 2,594/lot (CE stopped 10:15, PE
  stopped 09:30 — both legs stopped same day) → bucket 4 days, net +6,945, green 3/4, first
  expiry-day loss. DTE 6 (expiry 11-23) strike 25350: -Rs 2,074/lot (CE stopped 11:15, PE held)
  → bucket 4 days, net +1,293, green 3/4.
- Observation: both buckets lost on the same calendar day — a reminder that same-day straddle
  outcomes across different expiries are correlated, not independent draws.

## 2026-11-18

- Session status: same bug continues. No trades.
- Real-price straddle: DTE 5 (expiry 11-23) strike 25350: +Rs 696/lot (CE held, PE stopped
  09:40) → bucket 4 days, net +4,011, green 3/4. DTE 13, new far-expiry bucket (expiry 12-01),
  strike 25400: -Rs 1,854/lot (CE held, PE stopped 12:35) → bucket 2 days, net +522, green 1/2.
- Observation: no new information.

## 2026-11-19

- Session status: same bug continues. No trades.
- Real-price straddle: DTE 4 (expiry 11-23) strike 25200: -Rs 5,853/lot (CE stopped 09:50, PE
  stopped 09:25 — both legs stopped within 25 minutes of the open) → bucket 4 days, net -2,566,
  green 2/4, now net negative. DTE 12 (expiry 12-01) strike 25200: +Rs 4,174/lot (CE stopped
  10:50, PE held) → bucket 4 days, net +3,997, green 3/4.
- Observation: the worst single day in the whole dataset so far — a sharp two-way move stopped
  both legs almost immediately, exactly the scenario a short-straddle-at-the-open strategy is
  supposed to fear. Flagged for the final report.

## 2026-11-20

- Session status: same bug continues (last affected day before today's normal session — see
  2026-11-23 below). No trades.
- Real-price straddle: DTE 3 (expiry 11-23) strike 25450: +Rs 5,132/lot (CE stopped 10:45, PE
  held) → bucket 2 days, net +10,303, green 2/2. DTE 11 (expiry 12-01) strike 25450: +Rs
  3,286/lot (CE stopped 11:55, PE held) → bucket 4 days, net +14,410, green 4/4, the largest
  bucket total so far.
- Observation: no new information; bucket sizes still only 2-5 days.

## 2026-11-23

- Session status: ran normally again today — the first normal bot session since 2026-10-29. The
  "market closed for today" false-closed bug affected every weekday from 2026-10-30 through
  2026-11-20 (15 sessions, holiday on 2026-11-10 excluded); it is flagged here as an anomaly in
  the bot's own logs/market-hours logic, not fixed (out of scope for this analysis-only review).
  Paper mode, 1/3 setups taken.
- Trades: net Rs 485 on 1 trade — 13:15 NIFTY24NOV25500PE SHORT, Rs +485 (+0.3R, WORKED: hit
  T1, rest exited on trend fade, best +1.7R). 4 further SHORTs rejected (risk ~Rs 1,693-2,227 vs
  Rs 1,500 budget).
- review.py --all (now 5 trades/3 days): net Rs 316, win rate 40%, avg +0.07R, green days 2/3,
  worst day Rs -1,854, best day Rs 1,684. Still far short of the 30+ trades review.py says are
  needed before touching any rule.
- Real-price straddle: DTE 0, expiry day, strike 25850: +Rs 4,375/lot (CE held, PE stopped
  09:20) → bucket 5 days, net +11,320, green 4/5. DTE 8 (expiry 12-01) strike 25900: +Rs
  6,037/lot (CE held, PE stopped 09:25) → bucket 3 days, net +12,305, green 3/3.
- Full running totals, all 12 DTE buckets collected since 2026-10-26 (0,1,3,4,5,6,7,8,10,11,12,13
  days), 40 day×expiry samples: net +Rs 64,003/lot, 30/40 green (75%). Worst single day: -Rs
  5,853/lot (2026-11-19, DTE 4). Full write-up in FINAL_REPORT.md, written today since the
  test's nominal end date (20 Nov 2026) has passed.
- Observation: the bot's own breakout-buying trades still show no live edge (5 trades, net
  about flat). The straddle-selling side is broadly positive (11 of 12 DTE buckets net
  positive), but each bucket still has only 2-5 days — not nearly enough to call it an edge
  despite the encouraging aggregate. Sample size: 5 trades/3 days for the bot; 40 day×expiry
  samples, 2-5 per DTE bucket, for the straddle — not yet meaningful at the per-bucket level.

## 2026-11-24

- 2026-11-24: NSE holiday (Guru Nanak Jayanti) — bot correctly logged "no candles today", no options CSV, nothing new to review. FINAL_REPORT.md already filed on 2026-11-23; no change to its conclusions.

## 2026-11-25

- 2026-11-25: normal session, 0/3 setups taken (1 SHORT rejected, chart against the day's bullish bias) — journal.csv unchanged at 5 trades/3 days, review.py verdicts unchanged. Two new real-price straddle samples: DTE 6 (expiry 12-01) strike 25750 Rs -1,209/lot (CE stopped 10:35, PE held); DTE 13 (expiry 12-08) strike 25750 Rs -3,665/lot (CE stopped 10:40, PE held) — both red. Running total now 42 day×expiry samples, net +Rs 58,976/lot, 30/42 green (71%); worst day still -Rs 5,853 (2026-11-19, DTE 4). FINAL_REPORT.md already filed on 2026-11-23; these two extra samples don't change its "no reliable edge found" conclusion. Sample size still not meaningful per DTE bucket (2-5 days each).
