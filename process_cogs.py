import os
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.windows import from_bounds
import geopandas as gpd
from shapely.geometry import shape

# IPFS Gateways for your uploaded COGs
ORTHO_URL = "https://ipfs.io/ipfs/QmYYCVqgQRJqT9Sea45wBYDp45yEZWUWQDFnQiCFqzcayv"
DEM_URL   = "https://ipfs.io/ipfs/QmaqJ549WgKjvprxxzMCufEHU8wfiD4Y381VFe1a5o9vg4"

print("Connecting to DEM COG stream...")

# Enable GDAL HTTP range-reading configuration
gdal_env = rasterio.Env(
    GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES',
    GDAL_HTTP_MULTIPLEX='YES'
)

with gdal_env:
    with rasterio.open(DEM_URL) as src:
        profile = src.profile
        crs = src.crs
        transform = src.transform
        bounds = src.bounds

        # Read elevation raster
        dem = src.read(1)
        nodata = src.nodata

        # Compute relative elevation above local baseline (nDHM proxy)
        from scipy.ndimage import minimum_filter
        valid = (dem != nodata) if nodata is not None else ~np.isnan(dem)
        ground_approx = minimum_filter(np.where(valid, dem, np.nanmin(dem)), size=31)
        rel_height = dem - ground_approx

        # Target elevated structural surfaces (between 2.5m and 35m)
        structure_mask = (rel_height >= 2.5) & (rel_height <= 35.0) & valid

        print("Vectorizing contours into polygons...")
        raw_shapes = shapes(rel_height.astype(np.float32), mask=structure_mask, transform=transform)

        features = []
        count = 1
        for geom_dict, val in raw_shapes:
            poly = shape(geom_dict)
            
            # Filter noise and tiny fragments (approx > 25 m^2 in degree units)
            if poly.area > 0.0000025:
                # Regularize geometry (orthogonal snap / simplify)
                clean_poly = poly.simplify(0.00002, preserve_topology=True)
                
                features.append({
                    "geometry": clean_poly,
                    "id": f"BLDG-{count:04d}",
                    "height_m": round(float(val), 2),
                    "area_m2": round(clean_poly.area * (111320 ** 2), 1)
                })
                count += 1

print(f"Total building structures identified: {len(features)}")

# Build GeoDataFrame
if features:
    gdf = gpd.GeoDataFrame(features, crs=crs)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    
    output_path = "buildings.geojson"
    gdf.to_file(output_path, driver="GeoJSON")
    print(f"Wrote {len(gdf)} features to {output_path}")
else:
    print("No features met the area/elevation threshold.")
