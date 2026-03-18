"""
Idempotent UptimeRobot monitor setup for the Contractor License Verification API.

Usage:
    python3 scripts/setup_uptimerobot.py \
        --api-key <UptimeRobot Main API Key> \
        --base-url https://your-service.up.railway.app

Where to find your API key:
    UptimeRobot dashboard → left sidebar → Integrations & API
    → API Settings → Main API Key (NOT the "My Profile" key)

Re-running the script is safe — it updates existing monitors rather than
creating duplicates.
"""
import argparse
import json
import time
import urllib.request
import urllib.parse
import urllib.error

UPTIMEROBOT_API = "https://api.uptimerobot.com/v2"

MONITORS = [
    {
        "name": "Contractor API — Health",
        "path": "/health",
        "keyword": "ok",
        "interval": 300,  # 5 minutes
        "description": "Confirms the API process is alive and all scrapers respond",
    },
    {
        "name": "Contractor API — Status",
        "path": "/status",
        "keyword": "states",  # structural key — always present, never a status value
        "interval": 300,  # 5 minutes
        "description": "Tracks per-state pipeline health based on live traffic",
    },
    {
        "name": "Contractor API — Probe (CA pipeline)",
        "path": "/probe",
        "keyword": "ok",
        "interval": 900,  # 15 minutes
        "description": "Live end-to-end scrape probe — confirms CA pipeline is functional",
    },
]


def post(endpoint, api_key, payload):
    payload["api_key"] = api_key
    payload["format"] = "json"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{UPTIMEROBOT_API}/{endpoint}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"stat": "fail", "error": {"message": f"HTTP {e.code}: {body}"}}


def get_alert_contacts(api_key):
    result = post("getAlertContacts", api_key, {})
    if result.get("stat") != "ok":
        print(f"  Warning: could not fetch alert contacts: {result.get('error')}")
        return []
    contacts = result.get("alert_contacts", {}).get("alert_contact", [])
    if isinstance(contacts, dict):
        contacts = [contacts]
    return contacts


def get_existing_monitors(api_key):
    result = post("getMonitors", api_key, {})
    if result.get("stat") != "ok":
        print(f"  Warning: could not fetch existing monitors: {result.get('error')}")
        return {}
    monitors = result.get("monitors", [])
    return {m["friendly_name"]: m["id"] for m in monitors}


def upsert_monitor(api_key, existing, name, url, keyword, interval, alert_contact_ids):
    payload = {
        "friendly_name": name,
        "url": url,
        "type": 2,               # keyword monitor
        "keyword_type": 2,       # keyword exists
        "keyword_value": keyword,
        "interval": interval,
        "http_method": 2,        # GET (NOT 1 — that's HEAD and is rejected)
        "alert_contacts": alert_contact_ids,
    }

    if name in existing:
        payload["id"] = existing[name]
        result = post("editMonitor", api_key, payload)
        action = "Updated"
    else:
        result = post("newMonitor", api_key, payload)
        action = "Created"

    if result.get("stat") == "ok":
        print(f"  {action}: {name}")
    else:
        err = result.get("error", result)
        print(f"  Failed ({action.lower()}): {name} — {err}")

    time.sleep(1)  # avoid UptimeRobot rate limiting (429)


def main():
    parser = argparse.ArgumentParser(description="Set up UptimeRobot monitors")
    parser.add_argument("--api-key", required=True, help="UptimeRobot Main API Key")
    parser.add_argument("--base-url", required=True, help="Deployed API base URL (no trailing slash)")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    api_key = args.api_key

    print("Fetching alert contacts...")
    contacts = get_alert_contacts(api_key)
    # Format: "id_threshold_recurrence" — notify immediately, no recurrence cap
    alert_contact_ids = "-".join(f"{c['id']}_0_0" for c in contacts) if contacts else ""
    if contacts:
        print(f"  Found {len(contacts)} contact(s): {[c.get('friendly_name', c['id']) for c in contacts]}")
    else:
        print("  No alert contacts found — monitors will be created without notifications")

    time.sleep(1)

    print("Fetching existing monitors...")
    existing = get_existing_monitors(api_key)
    print(f"  Found {len(existing)} existing monitor(s)")

    time.sleep(1)

    print("Upserting monitors...")
    for monitor in MONITORS:
        url = f"{base_url}{monitor['path']}"
        upsert_monitor(
            api_key=api_key,
            existing=existing,
            name=monitor["name"],
            url=url,
            keyword=monitor["keyword"],
            interval=monitor["interval"],
            alert_contact_ids=alert_contact_ids,
        )

    print("\nDone. Verify monitors at https://uptimerobot.com/dashboard")
    print("\nMonitor summary:")
    for monitor in MONITORS:
        print(f"  {monitor['name']}")
        print(f"    URL:     {base_url}{monitor['path']}")
        print(f"    Keyword: \"{monitor['keyword']}\"")
        print(f"    Every:   {monitor['interval'] // 60} min")
        print(f"    Note:    {monitor['description']}")


if __name__ == "__main__":
    main()
