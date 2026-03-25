import csv
import os
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote
import math


def read_input_csv(filepath):
    """
    Reads the input CSV, extracts necessary data, and validates it.
    Returns: list of dicts with 'url', 'Place_ID', 'Place_Name'
    """
    rows = []
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"الملف غير موجود (File not found): {filepath}")

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        # Validate columns
        if not set(['url', 'Place_ID']).issubset(reader.fieldnames):
            # Try lowercase just in case
            if 'url' in reader.fieldnames and 'place_id' in reader.fieldnames:
                pass
            else:
                raise ValueError("الملف يجب أن يحتوي على عمود 'url' وعمود 'Place_ID'")

        for row in reader:
            url = row.get("url", "")
            pid = row.get("Place_ID", row.get("place_id", "")).strip()
            name = extract_place_name(url)
            rows.append({
                "url": url,
                "Place_ID": pid,
                "Place_Name": name,
            })
            
    return rows


def extract_place_name(url: str) -> str:
    """Extract place name from Google Maps URL query parameter."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "query" in params:
            return unquote(params["query"][0])
    except Exception:
        pass
    return ""


def generate_output_filename(base_dir: str, mode_prefix: str) -> str:
    """Generate a timestamped output filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(base_dir, f"{mode_prefix}_{timestamp}.csv")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) in meters.
    """
    if None in (lat1, lon1, lat2, lon2):
        return None
        
    # Convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371000 # Radius of earth in meters
    return c * r
