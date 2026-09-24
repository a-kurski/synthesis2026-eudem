import osmnx as ox
import geopandas as gpd

countries = [
    "Germany", "France", "Netherlands", "Belgium",
    "Switzerland", "Austria", "Luxembourg", "Liechtenstein"
]

gdf = ox.geocode_to_gdf(countries)
gdf.to_file("borders.geojson", driver="GeoJSON")
print(f"Saved {len(gdf)} country borders to borders.geojson")