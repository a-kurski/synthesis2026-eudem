import os
import xdem
import geoutils as gu

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
    "Switzerland": "5129",
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

