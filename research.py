"""2b. Research agent: one pre-market Claude call with live web search. It can veto the day or
pause trading around scheduled events; it can never create a trade. Without Anthropic
credentials (ANTHROPIC_API_KEY or `ant auth login`) it returns {} and the bot trades on price alone."""
import json
import logging
import re
from datetime import date

log = logging.getLogger("bot")

PROMPT = """Today is {today}. NSE opens at 09:15 IST. You are the research desk for an intraday
NIFTY index-options trader. Search the web now and find:
1. Scheduled events TODAY that can move Indian indices, with IST times: RBI policy, Union Budget,
   India CPI/GDP/IIP, US/Fed releases landing in Indian hours, results of heavyweight index stocks,
   election results, special sessions, exchange outages.
2. Overnight global cues: US close, Asian markets this morning, GIFT Nifty indication, crude, USD/INR.
3. Previous session FII/DII cash figures and any shock news.

Reply with ONLY this JSON object, no other text:
{{"skip_day": false, "reason": "", "blackout": [["HH:MM", "HH:MM"]], "bias": "bullish|bearish|neutral", "summary": ""}}
- skip_day: true only when the whole session is event-driven (Union Budget, election results,
  a market-wide shock). reason: one line why.
- blackout: IST windows from 15 min before to 30 min after each scheduled market-moving release
  between 09:15 and 15:30. Empty list if none.
- bias: your read of the opening direction.
- summary: at most 6 short lines with the key numbers and their sources."""

HHMM = re.compile(r"\d\d:\d\d")


def premarket(today: date) -> dict:
    try:
        import anthropic

        client = anthropic.Anthropic()
        messages = [{"role": "user", "content": PROMPT.format(today=today.strftime("%A %d %B %Y"))}]
        for _ in range(4):  # the server-side search loop may pause; resend to resume
            r = client.beta.messages.create(
                model="claude-opus-5",
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                tools=[{
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": 8,
                    "user_location": {"type": "approximate", "country": "IN", "timezone": "Asia/Kolkata"},
                }],
                messages=messages,
            )
            if r.stop_reason != "pause_turn":
                break
            messages = messages[:1] + [{"role": "assistant", "content": r.content}]
        if r.stop_reason == "refusal":
            raise RuntimeError("request declined")
        text = "".join(b.text for b in r.content if b.type == "text")
        raw = json.loads(text[text.index("{") : text.rindex("}") + 1])
        brief = {  # model output is untrusted input: keep only well-formed fields
            "skip_day": raw.get("skip_day") is True,
            "reason": str(raw.get("reason", ""))[:300],
            "blackout": [
                [s, e] for s, e in raw.get("blackout", [])
                if isinstance(s, str) and isinstance(e, str) and HHMM.fullmatch(s) and HHMM.fullmatch(e)
            ],
            "bias": str(raw.get("bias", "neutral")),
            "summary": str(raw.get("summary", ""))[:1500],
        }
        log.info("research: bias %s | skip %s | blackout %s\n%s",
                 brief["bias"], brief["skip_day"], brief["blackout"], brief["summary"])
        return brief
    except Exception as e:  # research is an extra filter, never a reason to crash the day
        log.warning("research unavailable (%s): trading on price action alone", e)
        return {}
