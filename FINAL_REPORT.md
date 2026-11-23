# Final report: one-month NIFTY paper-trading experiment (as of 2026-11-23)

Covers the cloud paper-trading sessions from 2026-10-23 through 2026-11-23. The test's nominal
end date (2026-11-20) has passed; this report is written now per the standing instructions and
uses all data collected up to today. Everything below is paper trading / simulated real-price
data — no real money or broker was involved.

## (a) The bot's own paper-trading results (breakout option buying)

`python review.py --all cloud/journal.csv`, verbatim:

```
## 2026-10-27  (day net Rs -1,854)
- 12:00 NIFTY03NOV22750CE LONG: Rs -1,245 (-1.0R) FALSE BREAKOUT: price never moved our way (best +0.1R), the breakout failed at once (no warning sign at entry)
- 13:30 NIFTY03NOV22750PE SHORT: Rs -609 (-0.5R) SCRATCH: reached T1, then stopped at the entry level; costs and time decay made it red

## 2026-10-29  (day net Rs 1,684)
- 11:50 NIFTY03NOV22800CE LONG: Rs -1,316 (-1.1R) FALSE BREAKOUT: price never moved our way (best +0.3R), the breakout failed at once (no warning sign at entry)
- 13:25 NIFTY03NOV22800CE LONG: Rs 3,000 (+2.6R) TREND RUN: broke out and ran to T2 (3R); worst point -0.7R

## 2026-11-23  (day net Rs 485)
- 13:15 NIFTY24NOV25500PE SHORT: Rs 485 (+0.3R) WORKED: hit T1, rest exited when the trend faded; best +1.7R

## Patterns so far
5 trades on 3 days, win rate 40%, avg +0.07R, net Rs 316, green days 2/3, max drawdown Rs 1,854, best day Rs 1,684, worst day Rs -1,854
Fewer than 30 trades: too few to change any rule yet. Keep collecting.
```

(Pattern-breakdown tables by outcome/side/time/trend/stretch/RSI/VIX/DTE all exist in the
review.py output but every bucket has 1-3 trades — not included again here since review.py
itself says they are too thin to use.)

**Operational note:** the bot only produced fills on 3 of the roughly 22 trading days this
period. On 15 consecutive weekdays (2026-10-30 through 2026-11-20, excluding the 2026-11-10
NSE holiday) the bot's own market-hours check logged "market closed for today" on every poll
and never entered its trading loop, so no report, trades or rejections exist for those days —
see RESEARCH_LOG.md for each date. This looks like a bug in bot.py's own clock/market-hours
logic, not a real market closure (the option-price collector ran normally and captured full
5-minute data on those same days). Not fixed here — analysis only, out of scope. This means the
bot-trading sample (5 trades) is smaller than it should be for a full month and should not be
read as "22 days of a strategy producing almost no signals."

## (b) Real-price straddle results (`python lab.py cloud`), by days to expiry

Selling the ATM straddle at 09:20 with a 30% per-leg stop, on real 5-minute NIFTY weekly option
prices collected daily since 2026-10-26:

```
days to expiry 0:  5 days, net Rs +11,320/lot, green 4/5
days to expiry 1:  3 days, net Rs    -958/lot, green 1/3
days to expiry 3:  2 days, net Rs +10,303/lot, green 2/2
days to expiry 4:  4 days, net Rs  -2,566/lot, green 2/4
days to expiry 5:  4 days, net Rs  +4,011/lot, green 3/4
days to expiry 6:  4 days, net Rs  +1,293/lot, green 3/4
days to expiry 7:  3 days, net Rs  +6,946/lot, green 3/3
days to expiry 8:  3 days, net Rs +12,305/lot, green 3/3
days to expiry 10: 2 days, net Rs  +2,420/lot, green 1/2
days to expiry 11: 4 days, net Rs +14,410/lot, green 4/4
days to expiry 12: 4 days, net Rs  +3,997/lot, green 3/4
days to expiry 13: 2 days, net Rs    +522/lot, green 1/2
```

Aggregate across all buckets: **40 day×expiry samples (20 calendar days × 2 tracked expiries
each), net +Rs 64,003/lot, 30/40 green (75%)**.

**Worst day:** 2026-11-19, 4 days to expiry, strike 25200 — **-Rs 5,853/lot**. Both the CE and
PE legs were stopped within 25 minutes of the open on a sharp two-way move — exactly the
scenario this strategy is most exposed to.

Near-expiry buckets specifically (the open question for this month, DTE 0-3): DTE 0 is the
strongest bucket (+11,320/lot, 4/5 green); DTE 1 is the only bucket that is net negative overall
(-958/lot, 1/3 green); DTE 3 is strongly positive but only 2 samples.

## (c) What is, and isn't, statistically meaningful

- **Bot trades (5 trades, 3 days):** nowhere near meaningful. review.py's own rule is 30+
  trades before touching anything, and this period produced one-sixth of that. The two losses
  (false breakouts) and one scratch look identical to what the 4.8-year backtest in README.md
  already predicts for this entry rule — no new information.
- **Straddle buckets (2-5 days each):** also not meaningful individually. A single bad day (like
  2026-11-19's -5,853/lot) is enough to flip any one bucket's sign, and several of the apparent
  "trends" in RESEARCH_LOG.md (e.g. DTE 0 going 4/4 then losing once) are consistent with plain
  noise at this sample size.
- **Aggregate straddle result (40 samples, +64,003/lot, 75% green):** more interesting than any
  single bucket, but still a small, non-independent sample — same-day straddles across the two
  tracked expiries are correlated (both legs of both expiries moved together on 2026-11-17 and
  2026-11-19), so this is closer to ~20 independent days than 40. Twenty days is still far short
  of what would be needed to distinguish a real edge from a lucky stretch, especially given the
  4.8-year backtest already found 0/64 settings of this family profitable under a matching
  model.
- The 15-session bot-scheduling gap reduced the bot-trading sample for the month but did **not**
  affect the straddle data, which is collected independently.

## (d) Recommendation

- **Breakout option buying (the bot's live strategy):** no reliable edge found. Consistent with
  the pre-existing 4.8-year backtest (README.md) and the 5 live paper trades collected this
  month. No change recommended.
- **Intraday short-straddle selling at 09:20, especially near expiry:** the real-price data
  collected so far is **promising but not statistically meaningful** — a positive aggregate
  (+64,003/lot, 75% green over ~20 days) with every near-expiry bucket positive except the
  1-day-to-expiry bucket, but each individual days-to-expiry bucket still has only 2-5 samples
  and the worst single day (-5,853/lot) shows the real tail risk. This is not enough evidence to
  call it a trading edge, and not enough to act on with real capital. Recommendation: keep
  collecting real option prices for each days-to-expiry bucket (ideally toward 20-30 days per
  bucket, which would need several more months at the current pace of ~1-2 expiries tracked per
  day) before drawing a conclusion either way.
- Separately, flag the bot's "market closed for today" false-reading bug (15 missed sessions
  this month) to whoever maintains bot.py — it silently cost a month of bot-trading data
  collection even though the market was open and trading normally on every one of those days.

No change was made to any strategy code, settings, or files under `cloud/` in producing this
report.
