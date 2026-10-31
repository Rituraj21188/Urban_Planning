import os
import urllib.request
import rasterio
from rasterio.warp import transform_bounds
import json

# Direct Gateway links
COGS = {
    "ortho": "https://ipfs.filebase.io/ipfs/QmYYCVqgQRJqT9Sea45wBYDp45yEZWUWQDFnQiCFqzcayv",
    "dem":   "https://ipfs.filebase.io/ipfs/QmaqJ549WgKjvprxxzMCufEHU8wfiD4Y381VFe1a5o9vg4"
}

print("=== READING COG METADATA & LOCATION ===")

# Configure GDAL for HTTP range requests
env = rasterio.Env(
    GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
    GDAL_HTTP_TIMEOUT=60
)

info_out = {}

with env:
    for name, url in COGS.items():
        print(f"\nOpening {name.upper()}...")
        try:
            with rasterio.open(url) as src:
                bounds_wgs84 = transform_bounds(src.crs, "EPSG:4326", *src.bounds) if src.crs != "EPSG:4326" else src.bounds
                center_lon = (bounds_wgs84[0] + bounds_wgs84[2]) / 2.0
                center_lat = (bounds_wgs84[1] + bounds_wgs84[3]) / 2.0

                info = {
                    "crs": str(src.crs),
                    "dimensions": [src.width, src.height],
                    "bounds_native": list(src.bounds),
                    "bounds_wgs84": list(bounds_wgs84),
                    "center": [center_lon, center_lat],
                    "nodata": src.nodata
                }
                info_out[name] = info
                print(f"-> Location Center: Lon {center_lon:.6f}, Lat {center_lat:.6f}")
                print(f"-> Bounds (WGS84): {bounds_wgs84}")
        except Exception as e:
            print(f"Error reading {name}: {e}")

# Save metadata so WebUI knows the real location
with open("cog_metadata.json", "w") as f:
    json.dump(info_out, f, indent=2)

print("\nSaved metadata to cog_metadata.json")
