"""
Google Play app monitor.
Checks each package in apps.txt and records the exact time an app
goes DOWN (unpublished/removed -> 404) and comes back UP (200).

Output files (committed to the repo automatically):
  history.csv  -> every DOWN / UP event with time and downtime duration
  STATUS.md    -> current status of every app and since when
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Africa/Casablanca")  # change if you want another timezone
STATE_FILE = "state.json"
HISTORY_FILE = "history.csv"
STATUS_FILE = "STATUS.md"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def check(pkg):
    """Return 'UP', 'DOWN', or None (unknown: network error, rate limit...)."""
    url = f"https://play.google.com/store/apps/details?id={pkg}&hl=en&gl=US"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return "UP" if r.status == 200 else None
    except urllib.error.HTTPError as e:
        return "DOWN" if e.code == 404 else None
    except Exception:
        return None


def status_of(pkg):
    s = check(pkg)
    if s == "DOWN":  # double-check to avoid false alarms
        time.sleep(15)
        s = check(pkg)
    return s


def fmt_duration(seconds):
    seconds = int(seconds)
    d, seconds = divmod(seconds, 86400)
    h, seconds = divmod(seconds, 3600)
    m = seconds // 60
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def main():
    with open("apps.txt") as f:
        apps = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    state = {"apps": {}}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)

    now = datetime.now(TZ)
    stamp = now.strftime("%Y-%m-%d %H:%M")
    rows = []

    for pkg in apps:
        s = status_of(pkg)
        if s is None:
            print(f"{pkg}: unknown (skipped this run)")
            continue
        print(f"{pkg}: {s}")
        prev = state["apps"].get(pkg)
        if prev is None:
            rows.append(f"{stamp},{pkg},FIRST CHECK {s},")
            state["apps"][pkg] = {"status": s, "since": now.isoformat()}
        elif prev["status"] != s:
            since = datetime.fromisoformat(prev["since"])
            dur = fmt_duration((now - since).total_seconds())
            rows.append(f"{stamp},{pkg},{s},was {prev['status']} for {dur}")
            state["apps"][pkg] = {"status": s, "since": now.isoformat()}

    # Changes once a day -> keeps the repo "active" so GitHub
    # doesn't disable the scheduled workflow after 60 days.
    state["heartbeat"] = now.date().isoformat()

    if rows:
        new_file = not os.path.exists(HISTORY_FILE)
        with open(HISTORY_FILE, "a") as f:
            if new_file:
                f.write("time,package,event,previous\n")
            f.write("\n".join(rows) + "\n")

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    lines = ["| App | Status | Since |", "|---|---|---|"]
    for pkg, info in sorted(state["apps"].items()):
        icon = "🟢" if info["status"] == "UP" else "🔴"
        since = datetime.fromisoformat(info["since"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"| `{pkg}` | {icon} {info['status']} | {since} |")
    with open(STATUS_FILE, "w") as f:
        f.write("# App status\n\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
