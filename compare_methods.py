#!/usr/bin/env python3
"""
Compare Google Maps Place ID decoding vs Playwright exact scraping.
Runs on the first 20 rows.
"""
import csv
import base64
import struct
import s2sphere
import json
import time
from urllib.parse import urlparse, parse_qs, unquote
from playwright.sync_api import sync_playwright

INPUT_FILE = "تقرير المتابعة - IDs.csv"
OUTPUT_FILE = "comparison_first_20.csv"


def decode_place_id(place_id: str):
    """Decode a Google Maps Place ID to lat/lng using s2sphere."""
    try:
        if not place_id.startswith("ChIJ"):
            return None, None
            
        b64_str = place_id.replace("-", "+").replace("_", "/")
        padding = 4 - len(b64_str) % 4
        if padding != 4:
            b64_str += "=" * padding
            
        raw_bytes = base64.b64decode(b64_str)
        # Expected format: 0x0a 0x12 0x09 [8-byte uint64 s2 cell id]
        if raw_bytes[0] == 0x0a and raw_bytes[2] == 0x09:
            cell_id_int = struct.unpack("<Q", raw_bytes[3:11])[0]
            cell_id = s2sphere.CellId(cell_id_int)
            lat_lng = cell_id.to_lat_lng()
            return lat_lng.lat().degrees, lat_lng.lng().degrees
        return None, None
    except Exception:
        return None, None


def extract_coords_url(url: str):
    import re
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def main():
    rows = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 20:
                break
            rows.append(row)
            
    print(f"Comparing first {len(rows)} places...")
    
    results = []
    
    # 1. First get decoded coords (instant)
    for row in rows:
        pid = row.get("Place_ID", "").strip()
        url = row.get("url", "").strip()
        
        name = ""
        try:
            name = unquote(parse_qs(urlparse(url).query).get("query", [""])[0])
        except Exception:
            pass
            
        dec_lat, dec_lng = decode_place_id(pid)
        
        results.append({
            "Name": name,
            "Place_ID": pid,
            "Decoded_Lat": dec_lat,
            "Decoded_Lng": dec_lng,
            "Scraped_Lat": None,
            "Scraped_Lng": None,
            "Difference_Meters": None
        })

    # 2. Now run Playwright to get exact coords
    print("Running Playwright to get exact coords...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(locale="en-US")
        page = ctx.new_page()
        
        for i, res in enumerate(results):
            pid = res["Place_ID"]
            print(f"Scraping [{i+1}/20]: {res['Name'][:40]}...", end=" ", flush=True)
            
            try:
                place_url = f"https://www.google.com/maps/place/?q=place_id:{pid}"
                page.goto(place_url, wait_until="commit", timeout=15000)
                
                lat, lng = None, None
                for _ in range(12):
                    time.sleep(1)
                    try:
                        real_url = page.evaluate("() => window.location.href")
                        lat, lng = extract_coords_url(real_url)
                        if lat:
                            break
                    except Exception:
                        pass
                        
                res["Scraped_Lat"] = lat
                res["Scraped_Lng"] = lng
                print(f"✅ {lat}, {lng}")
                
            except Exception as e:
                print(f"❌ Error")
                
            # Calculate rough distance difference if both available
            if res["Decoded_Lat"] and res["Scraped_Lat"]:
                # Rough approximation: 1 degree diff ~ 111km
                lat_diff = abs(res["Decoded_Lat"] - res["Scraped_Lat"])
                lng_diff = abs(res["Decoded_Lng"] - res["Scraped_Lng"])
                # Cartesian distance approximation in meters
                dist = ((lat_diff * 111139)**2 + (lng_diff * 111139 * 0.93)**2)**0.5
                res["Difference_Meters"] = round(dist, 1)

        browser.close()

    # Write comparison CSV
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Name", "Place_ID", "Decoded_Lat", "Decoded_Lng", 
            "Scraped_Lat", "Scraped_Lng", "Difference_Meters"
        ])
        writer.writeheader()
        writer.writerows(results)
        
    print(f"\n✅ Comparison saved to {OUTPUT_FILE}")
    
    # Print summary
    print("\n--- Summary of differences ---")
    for r in results:
        if r["Difference_Meters"] is not None:
            print(f"{r['Name'][:30]:<30} | Diff: {r['Difference_Meters']} meters")

if __name__ == "__main__":
    main()
