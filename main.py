import requests
import schedule
import time
from datetime import datetime, timedelta
import pytz

# ══════════════════════════════════════════════════
#   PASTE YOUR KEYS HERE — only thing you need to change
# ══════════════════════════════════════════════════
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1502599070131425393/3KVYRXw-TPp3YjGRqJcQY5k58ZALu02EXQnggFa3VbPBPWwL7wWyXg7NYaCeUAV-VMx_"
FINNHUB_API_KEY     = "d7vfof9r01qldb7frch0d7vfof9r01qldb7frchg"
# ══════════════════════════════════════════════════

MOUNTAIN_TZ = pytz.timezone("America/Denver")
EASTERN_TZ  = pytz.timezone("America/New_York")

HIGH_PRIORITY_KEYWORDS = [
    "fomc", "federal reserve", "fed rate", "interest rate decision",
    "cpi", "consumer price index",
    "pce", "personal consumption",
    "nonfarm", "non-farm", "nfp", "payroll",
    "gdp",
    "ppi", "producer price",
    "retail sales",
    "unemployment", "jobless claims",
    "inflation",
    "jerome powell", "powell speaks",
    "ism manufacturing", "ism services",
    "jolts",
    "durable goods",
    "housing starts", "existing home",
]

DAY_EMOJIS = {
    "Monday":    "1️⃣",
    "Tuesday":   "2️⃣",
    "Wednesday": "3️⃣",
    "Thursday":  "4️⃣",
    "Friday":    "5️⃣",
}


def is_high_impact(event):
    if event.get("impact", "").lower() == "high":
        return True
    name = event.get("event", "").lower()
    return any(kw in name for kw in HIGH_PRIORITY_KEYWORDS)


def convert_to_et(time_str, date_str):
    if not time_str or time_str.strip() == "":
        return "All Day"
    try:
        dt_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        dt_utc = pytz.utc.localize(dt_utc)
        dt_et  = dt_utc.astimezone(EASTERN_TZ)
        return dt_et.strftime("%-I:%M %p ET")
    except Exception:
        return time_str


def fetch_week_events():
    now_mt  = datetime.now(MOUNTAIN_TZ)
    monday  = now_mt - timedelta(days=now_mt.weekday())
    friday  = monday + timedelta(days=4)

    from_str = monday.strftime("%Y-%m-%d")
    to_str   = friday.strftime("%Y-%m-%d")

    url = (
        f"https://finnhub.io/api/v1/calendar/economic"
        f"?from={from_str}&to={to_str}&token={FINNHUB_API_KEY}"
    )

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        all_events = resp.json().get("economicCalendar", [])
    except Exception as e:
        print(f"[ERROR] Finnhub fetch failed: {e}")
        return {}

    grouped = {day: [] for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]}

    for event in all_events:
        if not is_high_impact(event):
            continue

        date_str = event.get("time", "")[:10]
        time_str = event.get("time", "")[11:16]

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d")
            day_name   = event_date.strftime("%A")
        except Exception:
            continue

        if day_name not in grouped:
            continue

        grouped[day_name].append({
            "name":    event.get("event", "Unknown Event"),
            "country": event.get("country", "").upper(),
            "time_et": convert_to_et(time_str, date_str),
        })

    return grouped


def build_discord_message(grouped):
    now_mt  = datetime.now(MOUNTAIN_TZ)
    monday  = now_mt - timedelta(days=now_mt.weekday())
    friday  = monday + timedelta(days=4)
    week_str = f"{monday.strftime('%b %d')} – {friday.strftime('%b %d, %Y')}"

    lines = []
    has_any = False

    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        events = grouped.get(day, [])
        emoji  = DAY_EMOJIS[day]
        lines.append(f"\n{emoji} **{day}**")

        if not events:
            lines.append("　　— No high-impact events")
        else:
            has_any = True
            for e in events:
                country = f"[{e['country']}] " if e["country"] else ""
                lines.append(f"　　• {country}{e['name']} — `{e['time_et']}`")

    if not has_any:
        lines.append("\n*No high-impact events found for this week.*")

    description = "\n".join(lines)

    return {
        "embeds": [
            {
                "title":       f"📅  High-Impact Economic Events  |  {week_str}",
                "description": description,
                "color":       0xF4A733,
                "footer":      {"text": "Source: Finnhub  •  Times in ET  •  Trade safe 🤙"},
                "timestamp":   datetime.utcnow().isoformat() + "Z",
            }
        ]
    }


def post_to_discord():
    print(f"[{datetime.now(MOUNTAIN_TZ).strftime('%Y-%m-%d %H:%M MT')}] Posting weekly events...")

    grouped = fetch_week_events()
    payload = build_discord_message(grouped)

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            print("[OK] Posted to Discord successfully.")
        else:
            print(f"[ERROR] Discord returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Discord post failed: {e}")


# ══════════════════════════════════════════════════
#   SCHEDULE — Every Monday at 6:00 AM MT (13:00 UTC)
# ══════════════════════════════════════════════════
schedule.every().monday.at("13:00").do(post_to_discord)

print("✅ Bot is running. Will post every Monday at 6:00 AM MT.")
print("   To test it RIGHT NOW, uncomment the line below and run the file.")
post_to_discord()   # ← remove the # at the start of this line to test immediately

while True:
    schedule.run_pending()
    time.sleep(30)
