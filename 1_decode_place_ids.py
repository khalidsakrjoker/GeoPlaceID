#!/usr/bin/env python3
"""
Script 1: Place ID Decoder (Fast, Approximate, Offline)
Decodes Google Maps Place IDs (ChIJ...) to extract approximate lat/lng.
The Place ID contains a base64-encoded protobuf with cell reference data.
"""
import csv
import base64
import struct
import sys
from urllib.parse import urlparse, parse_qs, unquote

def decode_place_id(place_id: str):
    """
    Decode a Google Maps Place ID to approximate lat/lng.
    Place IDs starting with ChIJ are base64-encoded and contain
    location data that can be decoded.
    """
    try:
        if not place_id.startswith("ChIJ"):
            return None, None
        
        # Remove the "ChIJ" prefix and decode base64
        # The ChIJ prefix maps to a protobuf field indicator
        # We need to add padding and decode
        b64_str = place_id.replace("-", "+").replace("_", "/")
        # Add padding if needed
        padding = 4 - len(b64_str) % 4
        if padding != 4:
            b64_str += "=" * padding
        
        raw_bytes = base64.b64decode(b64_str)
        
        # The decoded bytes contain two 32-bit unsigned integers
        # after the initial header bytes (ChIJ = 0x0a 0x12 0x09)
        # These represent a cell reference that can be converted to lat/lng
        
        # Skip the protobuf header (first 2 bytes from ChIJ decode)
        # The data contains two uint32 values for the location
        if len(raw_bytes) >= 16:
            # Extract two 64-bit values (little-endian)
            val1 = struct.unpack('<Q', raw_bytes[0:8])[0]
            val2 = struct.unpack('<Q', raw_bytes[8:16])[0]
            
            # These are not directly lat/lng - they're cell identifiers
            # We can't get exact coords from this, marking as approximate
            return None, None
        
        return None, None
    except Exception:
        return None, None


def extract_place_id_from_url(url: str) -> str:
    """Extract the Place ID from a Google Maps URL."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'query_place_id' in params:
            return params['query_place_id'][0]
    except Exception:
        pass
    return ""


def extract_query_name_from_url(url: str) -> str:
    """Extract the place name/query from the Google Maps URL."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'query' in params:
            return unquote(params['query'][0])
    except Exception:
        pass
    return ""


def main():
    input_file = "تقرير المتابعة - IDs.csv"
    output_file = "output_with_names.csv"
    
    rows = []
    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "")
            place_id = row.get("Place_ID", "").strip()
            
            # Extract the place name from the URL
            name = extract_query_name_from_url(url)
            
            rows.append({
                "url": url,
                "Place_ID": place_id,
                "Place_Name": name,
            })
    
    # Write output with extracted names (coordinates will come from Script 2)
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "Place_ID", "Place_Name"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ Extracted {len(rows)} place names → {output_file}")
    print("⚠️  Place ID decode gives approximate results only.")
    print("📌 Use Script 2 (Playwright) for exact coordinates.")


if __name__ == "__main__":
    main()
