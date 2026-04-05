import base64
import struct
import s2sphere
import csv

def decode_place_id(place_id: str):
    """
    Decode a Google Maps Place ID to approximate lat/lng using s2sphere.
    Returns (lat, lng) or (None, None) if format is unknown or invalid.
    """
    try:
        if not place_id or not place_id.startswith("ChIJ"):
            return None, None
            
        b64_str = place_id.replace("-", "+").replace("_", "/")
        padding = 4 - len(b64_str) % 4
        if padding != 4:
            b64_str += "=" * padding
            
        raw_bytes = base64.b64decode(b64_str)
        
        # Expected protobuf format: 0x0a 0x12 0x09 [8-byte uint64 s2 cell id]
        # In some cases the cell id is at an offset, but usually starts at byte 3
        if raw_bytes[0] == 0x0a and raw_bytes[2] == 0x09:
            cell_id_int = struct.unpack("<Q", raw_bytes[3:11])[0]
            cell_id = s2sphere.CellId(cell_id_int)
            lat_lng = cell_id.to_lat_lng()
            return lat_lng.lat().degrees, lat_lng.lng().degrees
            
        return None, None
    except Exception:
        return None, None


def run_decode_mode(rows: list, output_path: str, progress_callback, is_cancelled):
    """
    Process all rows using the offline decoder.
    progress_callback(current_idx, total, message, is_error)
    is_cancelled() -> bool
    """
    total = len(rows)
    results = []
    success_count = 0
    
    for i, row in enumerate(rows):
        if is_cancelled():
            progress_callback(i, total, "⚠️ Cancelled by user", True)
            break
            
        pid = row.get("Place_ID", "")
        name = row.get("Place_Name", "")
        url = row.get("url", "")
        
        lat, lng = decode_place_id(pid)
        
        if lat and lng:
            success_count += 1
            progress_callback(i + 1, total, f"✅ Decoded: {name[:30]} ({lat:.5f}, {lng:.5f})", False)
        else:
            progress_callback(i + 1, total, f"❌ Decode failed: {name[:30]}", True)
            
        results.append({
            "Place_ID": pid,
            "Place_Name": name,
            "Latitude": lat if lat else "",
            "Longitude": lng if lng else "",
            "Google_Maps_URL": url,
        })
        
    # Write output
    if results:
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Place_ID", "Place_Name", "Latitude", "Longitude", "Google_Maps_URL"])
            writer.writeheader()
            writer.writerows(results)
            
        progress_callback(len(results), total, f"🎉 Completed! Extracted {success_count} locations. Saved: {output_path}", False)
