import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape, Polygon
import numpy as np
import json

# Your Filebase IPFS COG URLs
ORTHO_URL = "https://ipfs.io/ipfs/QmYYCVqgQRJqT9Sea45wBYDp45yEZWUWQDFnQiCFqzcayv"
DEM_URL   = "https://ipfs.io/ipfs/QmaqJ549WgKjvprxxzMCufEHU8wfiD4Y381VFe1a5o9vg4"

print("Connecting to IPFS COG streams via GDAL /vsicurl/...")

# Open the DEM raster stream
with rasterio.open(DEM_URL) as dem_src:
    dem_data = dem_src.read(1)
    transform = dem_src.transform
    crs = dem_src.crs

    # Mask nodata
    valid_mask = (dem_data != dem_src.nodata) if dem_src.nodata is not None else np.ones_like(dem_data, dtype=bool)
    
    # Calculate baseline terrain vs elevated structures
    # Using local morphological baseline to isolate raised structures
    from scipy.ndimage import minimum_filter
    ground_est = minimum_filter(dem_data, size=25)
    relative_height = dem_data - ground_est

    # Threshold: structures elevated between 2.5m and 25m
    bldg_mask = (relative_height >= 2.5) & (relative_height <= 25.0) & valid_mask

    print("Extracting vector geometries from raster mask...")
    extracted_shapes = shapes(dem_data, mask=bldg_mask, transform=transform)

    records = []
    idx = 1
    for geom_dict, val in extracted_shapes:
        poly = shape(geom_dict)
        
        # Filter slivers and small vegetation patches
        if poly.area > 0.000002: # Area filter in degrees (~20-25 sq meters)
            # Simplify and regularize edges to snap clean building corners
            clean_poly = poly.simplify(0.00002, preserve_topology=True)
            
            records.append({
                "geometry": clean_poly,
                "id": f"BLDG-{idx:04d}",
                "height_m": round(float(val - np.min(ground_est)), 2),
                "area_m2": round(clean_poly.area * (111320 ** 2), 1)
            })
            idx += 1

print(f"Total building structures isolated: {len(records)}")

# Create GeoDataFrame with GeoPandas
gdf = gpd.GeoDataFrame(records, crs=crs)

# Reproject to WGS84 (EPSG:4326) for standard Web mapping
if gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs(epsg=4326)

# Export directly to buildings.geojson for the WebUI
gdf.to_file("buildings.geojson", driver="GeoJSON")
print("Saved clean vector polygons to buildings.geojson!")
