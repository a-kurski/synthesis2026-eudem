import os
import xdem
import numpy as np
import matplotlib.pyplot as plt
import geoutils as gu
import pandas as pd

#change to json files
# Source vertical CRS (fill these in later)
source_vcrs = {
    "NRW": "EPSG:7837", #https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/hoehenmodelle/digitale-gelaendemodelle/digitales-gelaendemodell
    "NiSa": "EPSG:7837", #https://ni-lgln-opengeodata.hub.arcgis.com/pages/digitales-gel-ndemodell-dgm1
    "RhPf": "EPSG:7837",#https://geoshop.rlp.de/digitale_gelaendemodelle/digitale_gelaendemodelle_dgm.html
    "Saar": "EPSG:7837", #https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1060&Itemid=475
    "BaWu": "EPSG:7837", #
    "Hessen": "EPSG:7837", #
    "Bay": "EPSG:7837", #
    "France": "EPSG:5720",
    "Luxembourg": "EPSG:5774",
    "Netherlands": "EPSG:5709",
    "Switzerland": "EPSG:5728",
}

#EPSG:5129
# Target vertical CRS
target_vcrs = {
    "NRW": "EPSG:5129", #https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/hoehenmodelle/digitale-gelaendemodelle/digitales-gelaendemodell
    "NiSa": "EPSG:5129", #https://ni-lgln-opengeodata.hub.arcgis.com/pages/digitales-gel-ndemodell-dgm1
    "RhPf": "EPSG:5129",#https://geoshop.rlp.de/digitale_gelaendemodelle/digitale_gelaendemodelle_dgm.html
    "Saar": "EPSG:5129", #https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1060&Itemid=475
    "BaWu": "EPSG:5129", #
    "Hessen": "EPSG:5129", #
    "Bay": "EPSG:5129", #
    "France": "EPSG:5129",
    "Luxembourg": "EPSG:5129",
    "Netherlands": "EPSG:5129",
    "Switzerland": "EPSG:5129",
}

def load_file(file_path):
    dtm = xdem.DEM(file_path)
    name = os.path.splitext(os.path.basename(file_path))[0]
    return dtm, name

def transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs):
    if country_name in target_vcrs:
        dem.to_vcrs(
            target_vcrs[country_name],
            force_source_vcrs=source_vcrs[country_name]
        )
    else:
        raise ValueError(f"Target vertical CRS for {country_name} not found.")

def save_dem(dem, country_name):
    dem.save(f"{country_name}_vcrs.tif")


def analyze_dem(dem_1, dem_2):
    """
    Coregister two DEMs and compute difference statistics.
    """

    # Coregistration
    coreg = (
        xdem.coreg.NuthKaab()
        + xdem.coreg.Deramp(poly_order=2)
    )

    coreg.fit(dem_1, dem_2)
    dem_2_aligned = coreg.apply(dem_2)

    # Elevation differences
    dh = dem_1 - dem_2_aligned

    # Convert to NumPy array and remove nodata
    dh_array = dh.data.filled(np.nan)
    valid = np.isfinite(dh_array)

    values = dh_array[valid]

    # Statistics
    mean = np.mean(values)
    median = np.median(values)
    std = np.std(values)
    rmse = np.sqrt(np.mean(values**2))
    mae = np.mean(np.abs(values))

    pd.DataFrame({
        "reference_dem": [dem_1.name],
        "comparison_dem": [dem_2.name],
        "mean": [mean],
        "median": [median],
        "std": [std],
        "rmse": [rmse],
        "mae": [mae]
        }).to_csv("dem_difference_statistics.csv", index=False)

    # Save difference raster
    dh.save("dh.tif")
    
    return {
        "coreg": coreg,
        "aligned_dem": dem_2_aligned,
        "dh": dh,
        "mean": mean,
        "median": median,
        "std": std,
        "rmse": rmse,
        "mae": mae,
    }