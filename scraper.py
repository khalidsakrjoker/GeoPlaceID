import csv
import json
import os
import re
import time
import subprocess
from playwright.sync_api import sync_playwright

def extract_coords_from_url(url: str):
    """Extract lat/lng from @lat,lng pattern in URL."""
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m:
        return float(m.group(1)), float(m.group(2))
    m3 = re.search(r"!3d(-?\d+\.\d+)", url)
    m4 = re.search(r"!4d(-?\d+\.\d+)", url)
    if m3 and m4:
        return float(m3.group(1)), float(m4.group(1))
    return None, None


def ensure_browser(progress_callback=None):
    """
    Ensure Playwright browser binaries are installed.
    Runs the playwright install command if needed.
    """
    try:
        if progress_callback:
            progress_callback(0, 1, "🔍 جاري التحقق من متصفح Playwright...", False)
            
        # Check if installed by trying to launch it briefly
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception as e:
        if progress_callback:
            progress_callback(0, 1, "⬇️ جاري تحميل المتصفح (قد يستغرق دقائق)...", False)
            
        try:
            # Run playwright install
            # In an EXE context, playwright install might be tricky,
            # but we assume the standard Python environment for now
            # PyInstaller users usually run `playwright install` beforehand
            import sys
            subprocess.check_call(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception as install_err:
            if progress_callback:
                progress_callback(0, 1, f"❌ فشل تحميل المتصفح: {install_err}", True)
            return False


def run_scrape_mode(rows: list, output_path: str, progress_callback, is_cancelled, progress_file="scrape_progress.json"):
    """
    Process all rows using Playwright to get 100% exact coordinates.
    Saves state to progress_file to allow resuming.
    """
    total = len(rows)
    
    # Load previous progress to resume
    progress = {}
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
            progress_callback(0, total, f"📂 تم استرجاع {len(progress)} موقع من جلسة سابقة.", False)
        except Exception:
            pass
            
    # Ensure browser is ready
    if not ensure_browser(progress_callback):
        return

    already_done = sum(1 for r in rows if r.get("Place_ID", "").strip() in progress)
    if already_done >= total:
        _write_output(rows, progress, output_path)
        progress_callback(total, total, f"🎉 كل الأماكن تم جلبها مسبقاً! تم الحفظ في: {output_path}", False)
        return

    success_count = 0
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            ctx = browser.new_context(locale="en-US")
            page = ctx.new_page()
            
            for i, row in enumerate(rows):
                if is_cancelled():
                    progress_callback(i, total, "⚠️ تم الإلغاء بواسطة المستخدم (Cancelled by user)", True)
                    break
                    
                pid = row.get("Place_ID", "").strip()
                name = row.get("Place_Name", "").strip()
                
                # Skip if already fetched
                if pid in progress:
                    if progress[pid].get("lat"):
                        success_count += 1
                    continue
                    
                try:
                    place_url = f"https://www.google.com/maps/place/?q=place_id:{pid}"
                    page.goto(place_url, wait_until="commit", timeout=20000)
                    
                    lat, lng = None, None
                    for _ in range(12):
                        time.sleep(1)
                        if is_cancelled():
                            break
                            
                        # Use window.location.href because SPA navigation doesn't update page.url in Python
                        try:
                            real_url = page.evaluate("() => window.location.href")
                            lat, lng = extract_coords_from_url(real_url)
                            if lat:
                                break
                        except Exception:
                            pass
                            
                    if lat:
                        success_count += 1
                        progress[pid] = {"lat": lat, "lng": lng, "name": name}
                        progress_callback(i + 1, total, f"✅ بنجاح: {name[:30]} ({lat:.5f}, {lng:.5f})", False)
                    else:
                        progress[pid] = {"lat": None, "lng": None, "name": name}
                        progress_callback(i + 1, total, f"⚠️ لم يتم العثور: {name[:30]}", True)
                        
                except Exception as e:
                    progress[pid] = {"lat": None, "lng": None, "name": name}
                    progress_callback(i + 1, total, f"❌ خطأ: {name[:30]}", True)
                    
                # Save progress every 10 rows
                if (i + 1) % 10 == 0:
                    with open(progress_file, "w", encoding="utf-8") as f:
                        json.dump(progress, f, ensure_ascii=False)
                        
                time.sleep(0.5)  # Rate limit
                
            browser.close()
            
    except Exception as main_err:
        progress_callback(0, total, f"❌ خطأ فادح في المتصفح: {main_err}", True)
        
    # Final save and write output
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False)
        
    _write_output(rows, progress, output_path)
    if not is_cancelled():
        progress_callback(total, total, f"🎉 اكتمل! تم العثور على إحداثيات {success_count} موقع. تم الحفظ: {output_path}", False)


def _write_output(rows, progress, output_path):
    """Write the scraper progress to the final CSV."""
    output_rows = []
    
    for row in rows:
        pid = row.get("Place_ID", "").strip()
        url = row.get("url", "").strip()
        name = row.get("Place_Name", "").strip()
        data = progress.get(pid, {})
        
        output_rows.append({
            "Place_ID": pid,
            "Place_Name": name,
            "Latitude": data.get("lat") or "",
            "Longitude": data.get("lng") or "",
            "Google_Maps_URL": url,
        })
        
    # Make sure output path directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Place_ID", "Place_Name", "Latitude", "Longitude", "Google_Maps_URL"])
        writer.writeheader()
        writer.writerows(output_rows)
