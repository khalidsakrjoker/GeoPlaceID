#!/usr/bin/env python3
"""
Google Maps Coordinates Scraper
===============================
Extracts exact lat/lng for each Place ID using Playwright.
Uses direct /maps/place/?q=place_id:ID URL format + page.evaluate()
to read the internal browser URL which contains @lat,lng.

Usage:
    .venv/bin/python 2_scrape_coordinates.py

Features:
    - Saves progress after each batch (resume-safe)
    - Handles rate limiting with delays
    - Outputs results to CSV with lat/lng columns
"""
import csv
import re
import time
import json
import os
import sys
from urllib.parse import urlparse, parse_qs, unquote
from playwright.sync_api import sync_playwright

PROGRESS_FILE = "scrape_progress.json"
INPUT_FILE = "تقرير المتابعة - IDs.csv"
OUTPUT_FILE = "output_coordinates.csv"
BATCH_SAVE = 25

def extract_place_name(url: str) -> str:
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "query" in params:
            return unquote(params["query"][0])
    except Exception:
        pass
    return ""


def extract_coords_from_url(url: str):
    """Extract lat/lng from @lat,lng pattern in URL."""
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m:
        return float(m.group(1)), float(m.group(2))
    # Fallback: !3d !4d
    m3 = re.search(r"!3d(-?\d+\.\d+)", url)
    m4 = re.search(r"!4d(-?\d+\.\d+)", url)
    if m3 and m4:
        return float(m3.group(1)), float(m4.group(1))
    return None, None


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"📂 Loaded {len(data)} previously scraped results")
        return data
    return {}


def save_progress(data: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def write_output(rows, progress):
    output_rows = []
    found = 0
    for row in rows:
        pid = row.get("Place_ID", "").strip()
        url = row.get("url", "").strip()
        name = extract_place_name(url)
        data = progress.get(pid, {})
        lat = data.get("lat")
        lng = data.get("lng")
        if lat is not None:
            found += 1
        output_rows.append({
            "Place_ID": pid,
            "Place_Name": name,
            "Latitude": lat if lat else "",
            "Longitude": lng if lng else "",
            "Google_Maps_URL": url,
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Place_ID", "Place_Name", "Latitude", "Longitude", "Google_Maps_URL"
        ])
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\n{'='*50}")
    print(f"📁 Output: {OUTPUT_FILE}")
    print(f"✅ Found: {found}/{len(output_rows)}")
    print(f"⚠️  Missing: {len(output_rows) - found}")


def main():
    # Read input
    rows = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total = len(rows)
    print(f"📊 Total places: {total}")

    progress = load_progress()
    already = sum(1 for r in rows if r.get("Place_ID", "").strip() in progress)
    print(f"✅ Already done: {already}/{total}")

    if already >= total:
        print("🎉 All done! Writing output...")
        write_output(rows, progress)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(locale="en-US")
        page = ctx.new_page()

        for i, row in enumerate(rows):
            pid = row.get("Place_ID", "").strip()
            url = row.get("url", "").strip()
            name = extract_place_name(url)

            if pid in progress:
                continue

            print(f"[{i+1}/{total}] {name[:50]}...", end=" ", flush=True)

            try:
                # Use direct place_id URL - this triggers proper SPA navigation
                place_url = f"https://www.google.com/maps/place/?q=place_id:{pid}"
                page.goto(place_url, wait_until="commit", timeout=15000)

                # Wait for SPA to navigate and URL to update internally
                lat, lng = None, None
                for attempt in range(12):
                    time.sleep(1)
                    # Key trick: window.location.href has the real URL with coords
                    # even though page.url from Python doesn't update
                    try:
                        real_url = page.evaluate("() => window.location.href")
                        lat, lng = extract_coords_from_url(real_url)
                        if lat:
                            break
                    except Exception:
                        pass

                if lat:
                    progress[pid] = {"lat": lat, "lng": lng, "name": name}
                    print(f"✅ {lat}, {lng}")
                else:
                    progress[pid] = {"lat": None, "lng": None, "name": name}
                    print("⚠️ Not found")

            except Exception as e:
                progress[pid] = {"lat": None, "lng": None, "name": name}
                print(f"❌ {str(e)[:50]}")

            # Rate limiting
            time.sleep(0.5)

            # Save progress periodically
            if (i + 1) % BATCH_SAVE == 0:
                save_progress(progress)
                done_now = sum(1 for r in rows if r.get("Place_ID", "").strip() in progress)
                print(f"💾 Saved ({done_now}/{total})")

        browser.close()

    save_progress(progress)
    write_output(rows, progress)


if __name__ == "__main__":
    main()
