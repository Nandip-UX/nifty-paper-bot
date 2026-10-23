# NIFTY Intraday Options Bot: Complete Guide

An automatic intraday trading bot for NIFTY index options. It runs from market open to market
close, researches the market, finds entries, sizes each trade from your live account balance,
manages the exit, takes **at most 3 trades a day**, and closes everything by 15:15.

**Contents**
1. [What the bot does](#1-what-the-bot-does)
2. [Read this first](#2-read-this-first)
3. [One-time setup on your Mac](#3-one-time-setup-on-your-mac)
4. [Get your broker API keys](#4-get-your-broker-api-keys) (Upstox, Zerodha, Dhan, Angel One)
5. [Optional: research key (Claude)](#5-optional-research-key-claude)
6. [Test the broker login](#6-test-the-broker-login)
7. [Every trading day](#7-every-trading-day)
8. [Results: where to look](#8-results-where-to-look) and [daily review](#daily-review-learn-from-every-trade)
9. [Backtest on past data](#9-backtest-on-past-data)
10. [Going live with real money](#10-going-live-with-real-money)
11. [Settings you can change](#11-settings-you-can-change)
12. [Troubleshooting](#12-troubleshooting)
13. [Files in this folder](#13-files-in-this-folder)

---

## 1. What the bot does

Six agents work together inside one program. The **Risk agent can veto any trade.**

| Agent | Job |
|---|---|
| Commander | Runs the day on the clock below |
| 1. Chart | 5-min candle closes beyond the last 30-min high/low, with trend (EMA 9/21/50), momentum (RSI), a strong candle, and no previous-day level in the way |
| 2. Market | Trades only in the day's direction (above/below the open and previous close). India VIX above 25 means no trades. Optional Claude web research can skip the day or block event times (RBI, Fed...) |
| 3. F&O | Buys a CE for up moves and a PE for down moves, 1 strike in the money, nearest expiry that is **not today** |
| 4. Risk | Max 3 entries a day, 1% of balance at risk per trade, stops the day at -3% or after 2 losses in a row |
| 5. Execution | Places limit orders (3 tries). In live mode it also places a safety stop-loss order at the broker |
| 6. Trade manager | Checks every 5 seconds: stop loss; at target 1, sells half and moves the stop to entry; target 2; exits when the trend fades; sells everything at 15:15 |

**The trading day (Indian time)**

| Time | What happens |
|---|---|
| 09:00 | Logs in, reads your balance, runs research, downloads the option list |
| 09:15 - 09:30 | Only watches (opening range). No trades |
| 09:30 - 14:30 | At every 5-min candle close: market → chart → option → risk → buy |
| Every 5 sec | Manages the open trade |
| 15:15 | Sells everything, writes the day report, stops |

---

## 2. Read this first

- **The current rules lose money. Do not trade them live.** The full bot was run in paper mode over
  58 real trading days (28 Jul - 21 Oct 2026), with options priced from India VIX so time decay is
  included. Result: **85 trades, 41% wins, -Rs 2.1k on Rs 1.5 lakh (-1.4%), worst drawdown
  Rs 15.3k, profit factor 0.96**. The simple backtest, which ignores time decay, showed about breakeven (+Rs 4.1k).
  The program works correctly; the strategy needs improving on 1-2 years of data first.
  SEBI found 87.7% of individual F&O traders lost money in FY26.
- **The safe order:** 1-year backtest → at least 4 weeks of paper trading → live with 1 lot.
- **Paper mode is the default.** It uses real prices and your real balance, but places no real orders.
- **The office network blocks all brokers** (Sophos firewall). Use home Wi-Fi, a phone hotspot or a cloud server.
- **Live orders need a static IP** (SEBI rule since 1 April 2026). See [section 10](#10-going-live-with-real-money).

---

## Strategy research: is there a consistently profitable intraday strategy?

Tested on 23 Oct 2026 with **4.8 years of 5-minute NIFTY + India VIX data** (Jan 2022 - Oct 2026,
~1,190 days, from Upstox's free public API) and **real prices of every listed NIFTY option** (last
4 months). Costs and slippage included. Rerun with `python lab.py buy | sell | real`.

| Strategy | Result | Verdict |
|---|---|---|
| Breakout option buying (this bot) | Lost in **every year 2022-2026**; -Rs 1.6L to -Rs 5.6L per Rs 1,500-risk-per-trade over 4.8 years (PF 0.56-0.85) | No edge |
| Same entry signal, no options (pure index points) | 1,879 trades, average **0.000R** | Signal predicts nothing |
| Morning-only / T1 at 1R / wider stop variants | All lose | No edge |
| Intraday momentum, first-hour trend, gap fade, yesterday's direction | All within noise (t-stat below 1.1), signs flip year to year | No edge |
| Intraday short straddle / iron fly at 09:20 or 09:45 (64 settings) | **0 of 64 profitable** under the model that matches real option prices, even at 0.1% slippage | No edge |

**What the real option prices showed:** an at-the-money straddle held 09:20-15:15 lost value
the way the "calendar" model predicts (real -Rs 8.4 vs model -Rs 8.9 per unit, 41 samples).
Most option time decay happens **overnight**, so an intraday seller collects only about a
quarter of each day's decay while still paying for every intraday swing.

**Still open:** options with 0-3 days to expiry behave differently, and expired contracts' real
prices aren't free. From 26 Oct the daily cloud session saves real weekly option prices
(`cloud/options/`), so near-expiry intraday selling can be tested on real prices at month end.

**The honest summary:** no intraday NIFTY strategy tested here has a consistent edge. The one
well-documented edge in index options (option sellers earning more than moves cost) is earned
mostly **overnight**, which the intraday-only rule excludes. Holding positions overnight brings
gap risk and needs more margin; that is your decision to make, not a code change.

---

## Quick start: paper trading with NO broker account

You can watch the bot paper trade with live market data today, before you have any broker keys:

```bash
cd ~/Desktop/T1 && source .venv/bin/activate
open -e .env                     # set BROKER=yahoo and save
caffeinate -i python bot.py      # start before 09:00 on a trading day
```

- **What it uses:** NIFTY and India VIX come live from Yahoo Finance (free, works even on the
  office network). Option prices are **calculated** with Black-Scholes from India VIX, not real
  quotes, so P&L is an estimate. Every other part runs exactly as it would with a broker.
- **Limits:** `BROKER=yahoo` can never place real orders (`--live` is refused). Use a real broker
  for accurate option prices.

---

## One-month paper test (runs by itself)

Set up on 22 Oct 2026: the Mac starts the bot automatically at **08:50 every Monday-Friday**
(`BROKER=yahoo`, paper only, no login needed). It trades until 15:15, then writes the day report.

**Your only job:** keep the MacBook **on, plugged in, lid open** on trading days. If it was asleep
at 08:50, the bot starts as soon as the Mac wakes and joins the day late. To wake it by itself
every weekday, run this once (asks for your Mac password):
```bash
sudo pmset repeat wakeorpoweron MTWRF 08:45:00
```

**Follow the month:**
- Each day: `reports/YYYY-MM-DD.md` shows the day's trades, why each worked or failed, and a
  running total since the test started.
- Any time: `python review.py --all` shows every trade and the patterns.
- If a day is missing: check `logs/autostart.log` and `logs/YYYY-MM-DD.log`.

**At the end of the month** (about 20 trading days, around 20 Nov 2026): run
`python review.py --all` and send me the output. Judge it against the 58-day replay
(-1.4%, 41% wins): one month alone can't prove an edge, but it shows whether live behaviour
matches the replay.

**Stop the automatic start:**
```bash
launchctl bootout gui/$(id -u)/com.t1.niftybot          # pause (until next login)
rm ~/Library/LaunchAgents/com.t1.niftybot.plist         # remove for good
```

---

## 3. One-time setup on your Mac

Open **Terminal** and run these one by one:

```bash
cd ~/Desktop/T1

# 1. Create the private Python environment (skip if the .venv folder already exists)
python3 -m venv .venv

# 2. Turn it on. Do this EVERY time you open a new terminal.
#    Your prompt will then start with (.venv)
source .venv/bin/activate

# 3. Install the package for YOUR broker (only one line)
pip install requests                                                  # Upstox or Dhan
pip install kiteconnect                                               # Zerodha
pip install smartapi-python pyotp logzero websocket-client requests   # Angel One

# 4. Optional: the news research agent
pip install anthropic

# 5. Fix the SSL certificates of this Mac's Python (one time)
open "/Applications/Python 3.14/Install Certificates.command"

# 6. Create your settings file (skip if .env already exists)
cp .env.example .env

# 7. Safety checks: all 7 lines must say "ok"
python test_core.py
```

---

## 4. Get your broker API keys

You only need **one** broker. Open the settings file with `open -e .env`, fill in your broker's
lines, set `BROKER=` to its name and save. **Never share `.env` or paste keys into any chat.**

| Broker | Cost of API | Daily login | `BROKER=` |
|---|---|---|---|
| Upstox | Free | Click a link and paste the URL back (once a day) | `upstox` |
| Zerodha | Rs 500/month (Connect plan) | Click a link and paste the URL back (once a day) | `zerodha` |
| Dhan | Data API Rs 499/month + GST | Paste a token from the website (once a day) | `dhan` |
| Angel One | Free | Automatic | `angel` |

You need a trading account with the **F&O segment activated** at that broker.

### Upstox

1. Log in at **account.upstox.com/developer/apps**. In the Upstox web app this is Profile → **My Apps**.
2. Click **New App** and fill in:
   - **App name:** anything, e.g. `nifty-bot`
   - **Redirect URL:** `https://127.0.0.1`
   - **Postback URL:** leave empty
   - Accept the terms and confirm. Upstox allows **one API app per person**.
3. Open the app and copy the **API Key** and **API Secret**.
4. In `.env`:
   ```
   BROKER=upstox
   UPSTOX_API_KEY=paste-api-key-here
   UPSTOX_API_SECRET=paste-api-secret-here
   UPSTOX_REDIRECT_URI=https://127.0.0.1
   ```
   The redirect URI must be **exactly** the same as in step 2.
- The login lasts until 03:30 the next morning.
- Static IP (for live only): add it in the app settings. You can change it only once a week, and changing it logs you out.

### Zerodha (Kite Connect)

1. Go to **developers.kite.trade** and sign up / log in with your Zerodha account.
2. Click **Create new app**:
   - **Type:** **Connect** (Rs 500/month). The free "Personal" type has no market data, and the bot needs data.
   - **App name:** anything; **Zerodha Client ID:** yours
   - **Redirect URL:** `https://127.0.0.1`; **Postback URL:** leave empty
3. Add credits to pay for the app. Then open it and copy the **API key** and **API secret**.
4. In `.env`:
   ```
   BROKER=zerodha
   KITE_API_KEY=paste-api-key-here
   KITE_API_SECRET=paste-api-secret-here
   ```
- The login lasts until 06:00 the next morning.
- Start the bot after 08:30, when Zerodha publishes the day's option list.
- Static IP (for live only): developers.kite.trade → Profile → **IP Whitelist**.

### Dhan

1. Log in at **web.dhan.co** → Profile → **Access DhanHQ APIs**.
2. Your **Client ID** is shown there. Subscribe to the **Data API** (Rs 499/month + GST). The bot needs it for prices and candles.
3. In `.env`:
   ```
   BROKER=dhan
   DHAN_CLIENT_ID=paste-client-id-here
   DHAN_ACCESS_TOKEN=
   ```
   Leave `DHAN_ACCESS_TOKEN` **empty**. Dhan tokens last only 24 hours, so each morning the bot asks
   you to paste a fresh token. Generate it on the same **Access DhanHQ APIs** page. If TOTP is
   enabled on your Dhan account, you can type the TOTP code instead, and the bot then asks for your PIN.
- Static IP (for live only): set it on the same web.dhan.co page. It is then locked for 7 days.

### Angel One (SmartAPI)

1. Go to **smartapi.angelone.in** → sign up / log in → **Create an App**:
   - **App name:** anything; **Redirect URL:** `https://127.0.0.1`
   - Enter your Angel **Client ID**, and your static IPv4 if you have one (required for live orders)
   - Copy the **API Key**.
2. Turn on TOTP at **smartapi.angelbroking.com/enable-totp**: enter your Client ID and PIN, then the OTP.
   A QR code appears. **The text key written under the QR code is your TOTP secret.**
3. In `.env`:
   ```
   BROKER=angel
   ANGEL_API_KEY=paste-api-key-here
   ANGEL_CLIENT_CODE=your-client-id
   ANGEL_PIN=your-4-digit-pin
   ANGEL_TOTP_SECRET=paste-the-text-key-under-the-QR
   ```
- Login is fully automatic, so you never type anything in the morning. The session ends at midnight.

---

## 5. Optional: research key (Claude)

Without this key the bot still trades, on price action alone. With it, every morning at 09:00
Claude searches the web for:
- scheduled events with their times (RBI, Fed, Budget, CPI, big results)
- global cues
- FII/DII flows

It can then **skip the whole day** or **block trading around event times**. It can never start a trade.

1. Go to **console.anthropic.com** → sign up → **Settings → API Keys → Create Key**.
2. Add a little billing credit (one research call a day costs well under $1).
3. Run `pip install anthropic`, then add to `.env`:
   ```
   ANTHROPIC_API_KEY=paste-key-here
   ```

---

## 6. Test the broker login

Do this from home Wi-Fi or a phone hotspot, not the office. It is **read-only** and places no orders.

```bash
cd ~/Desktop/T1
source .venv/bin/activate
python -m brokers.upstox        # or: brokers.zerodha / brokers.dhan / brokers.angel
```

**Upstox / Zerodha:**
1. The terminal prints a long login link. Open it in your browser and log in.
2. The browser then shows a **"can't connect" page at 127.0.0.1. That is expected.**
3. Copy the **full URL from the address bar** (it contains `code=` or `request_token=`).
4. Paste it into the terminal and press Enter. Do it within a minute; the code expires fast.

**Dhan:** paste the token from web.dhan.co when asked.

**Angel One:** nothing to do.

**Success looks like:**
- your balance
- the NIFTY and India VIX prices
- the last 3 candles
- an at-the-money call option with its price

The login is saved for the rest of the day in `.tokens.json`, so the bot won't ask again.

---

## 7. Every trading day

1. Use home Wi-Fi or a hotspot, keep the MacBook **plugged in with the lid open**, and run:
   ```bash
   cd ~/Desktop/T1
   source .venv/bin/activate
   caffeinate -i python bot.py
   ```
2. Start it **between 08:40 and 09:00**. Log in if asked (same as section 6).
3. Leave the window open. It works by itself until about 15:15, then prints the day's report and stops.

- `caffeinate -i` stops the Mac from sleeping while the bot runs.
- On weekends, after 15:15 and on market holidays, the bot exits by itself.

**Emergency stop (kill switch).** In a second terminal window:
```bash
touch ~/Desktop/T1/STOP      # sells any open position at once and stops trading for today
```
**Delete it before the next trading day**, or the bot will stop immediately:
```bash
rm ~/Desktop/T1/STOP
```

---

## 8. Results: where to look

| File | What's inside |
|---|---|
| Terminal window | Live log: each 5-min check, why a setup was taken or skipped, entries, exits |
| `reports/YYYY-MM-DD.md` | Day summary: balance, trades, P&L, research notes, setups the agents turned down |
| `journal.csv` | Every exit ever made. Open it in Numbers or Excel to track performance over weeks |
| `logs/YYYY-MM-DD.log` | Full log of the day, same as the terminal |

---

## Daily review: learn from every trade

Every trade saves its entry conditions and how far price moved for and against it. The day
report (`reports/YYYY-MM-DD.md`) then explains each trade, like this:

```
- 11:20 NIFTY13OCT22500CE LONG: Rs -1,283 (-0.9R) FALSE BREAKOUT: price never moved our way
  (best +0.1R), the breakout failed at once (entry stretched 2.5 ATR past EMA21 (chasing))
- 12:50 NIFTY13OCT22450CE LONG: Rs 2,796 (+2.5R) TREND RUN: broke out and ran to T2 (3R)
```

R means "result in units of the planned risk": -1R is a full stop-out, +2R is twice the risk won.

| Verdict | Meaning | What it teaches |
|---|---|---|
| TREND RUN | Ran to target 2 | The ideal trade. Note its conditions |
| WORKED | Hit T1, rest exited when the trend faded | Good trade, normal exit |
| FALSE BREAKOUT | Never moved our way (best below +0.3R) | Entry filter let a bad breakout through |
| REVERSED BEFORE T1 | Was in profit, came back to the stop | Target too far, or protect profit earlier |
| SCRATCH | Half booked at T1, rest out at entry | Fine: risk was removed |
| OPTION DECAY | Option fell faster than the index | Time decay or volatility drop |
| NO FOLLOW-THROUGH | Still open at 15:15 | Late or weak setup |

**The routine:**

1. **Every day, after 15:15:** read the day report and look at the NIFTY chart for each trade.
   Do you agree with the verdict? What did the chart show that the rules missed?
2. **Every week:** run `python review.py --all`. It shows win rate and average R by condition
   (entry time, trend strength, RSI, VIX, how stretched the entry was, days to expiry), and marks
   losing and strong patterns.
3. **Change a rule only when** a pattern has 30+ trades, it makes sense (not just a number), and
   the 1-year backtest improves in both halves of the data. Change one rule at a time.

**Example: the 58-day replay** (85 trades) already shows:
- **Biggest leaks:** 28 trades "reversed before T1" (-Rs 28.9k) and 19 false breakouts (-Rs 21.6k).
- **Morning entries** (09:30-11:00) averaged +0.25R; **afternoon entries** averaged -0.17R.
- **RSI 62-68 looks bad** (-0.33R) while 55-62 and 68-75 are both positive. That is probably
  noise, not a real pattern: a real effect would rise or fall steadily. This is exactly the
  kind of "pattern" not to trade on.

---

## 9. Backtest on past data

This replays the exact same rules on past candles. It's the best way to judge the strategy before risking money.

```bash
python backtest.py --yahoo                        # last 60 days, no broker account needed
python backtest.py --broker upstox --days 365     # 1 year of data through your broker (needs login)
python backtest.py --broker upstox --days 365 -v  # also print every trade
```

It shows trades, win rate, average R (profit in units of risk), net Rs, profit factor
(above 1.3 is good), max drawdown, and green days.
Rs figures are estimates: they assume the option moves 0.6 x the index move and ignore time decay.

---

## 10. Going live with real money

Only go live when **all** of these are true:

- [ ] The 1-year backtest is clearly positive (profit factor above about 1.3)
- [ ] You paper traded at least 4 weeks and `journal.csv` is positive
- [ ] You have a **static IP** registered with your broker (see below)
- [ ] `MAX_LOTS = 1` is set in `config.py` for the first weeks

**Static IP.** Since 1 April 2026 brokers reject API orders that don't come from your registered
static IP. Two ways to get one:
1. Ask your internet provider for a static IP add-on, then register it with your broker (section 4).
2. Rent a small cloud server in the **Mumbai** region with a fixed IP (AWS, Google Cloud,
   DigitalOcean...), copy this folder there, register that IP, and run the bot over SSH.

**Start live trading:**
```bash
caffeinate -i python bot.py --live     # it asks you to type LIVE to confirm
```

---

## 11. Settings you can change

All in `config.py`. Change one thing at a time, and re-run the backtest after each change.

| Setting | Default | Meaning |
|---|---|---|
| `MAX_TRADES` | 3 | Entries per day (the code refuses more than 4) |
| `RISK_PCT` | 0.01 | Max loss per trade = 1% of the morning balance |
| `DAILY_LOSS_PCT` | 0.03 | Stop for the day at -3% |
| `MAX_CONSEC_LOSSES` | 2 | Stop after this many losses in a row |
| `MAX_LOTS` | 10 | Hard cap on lots per trade (use 1 when you start live) |
| `VIX_MAX` | 25 | No trading above this India VIX |
| `ENTRY_START` / `ENTRY_END` | 09:30 / 14:30 | Window for new entries |
| `SQUARE_OFF` | 15:15 | Everything sold by this time |
| `INDICES` | `["NIFTY"]` | Add `"BANKNIFTY"` to also scan Bank Nifty (monthly expiry only) |
| `PAPER_CAPITAL` (in `.env`) | not set | Paper mode: use this balance instead of your real one |

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `zsh: command not found: pip` or `python` | Run `source .venv/bin/activate` first (in every new terminal) |
| `CERTIFICATE_VERIFY_FAILED` | Run `open "/Applications/Python 3.14/Install Certificates.command"` once |
| Connection errors / timeouts at the office | The office firewall blocks brokers. Use home Wi-Fi or a hotspot |
| Login link has an empty `client_id`, or `KeyError: 'UPSTOX_API_KEY'` | `.env` is not filled in. See section 4 |
| "Invalid token" / asks to log in again | Delete the saved login with `rm .tokens.json` and run again |
| Bot exits right after starting | Weekend, after 15:15, market holiday, or a `STOP` file exists (`rm STOP`) |
| `research unavailable` in the log | No Anthropic key or package. That's fine; it trades on price only |
| Live orders rejected | Static IP not registered or wrong, or not enough funds |
| `EXIT INCOMPLETE` in the log | Open your broker app **now** and check the position. The bot keeps retrying |

---

## 13. Files in this folder

| File | What it is |
|---|---|
| `bot.py` | The commander: runs the trading day |
| `brain.py` | Chart, market and F&O agents, plus the exit rules |
| `risk.py` | Risk agent: limits and position size |
| `research.py` | Optional Claude web research before the open |
| `review.py` | Explains each trade and finds winning / losing patterns |
| `config.py` | All settings |
| `backtest.py` | Test the rules on past data |
| `test_core.py` | Safety checks |
| `brokers/` | One connection file per broker, plus `paper.py` for paper trading |
| `.env` | Your keys (private, never share) |
| `.tokens.json` | Today's saved login (created automatically) |
