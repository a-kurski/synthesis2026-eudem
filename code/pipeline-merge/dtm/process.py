"""Shared raster creation, AOI masking and COG publication."""
from pathlib import Path

from osgeo import gdal, ogr

from .geo import project, srs
from .progress import gdal_progress

OPTIONS = ['TILED=YES', 'COMPRESS=DEFLATE', 'PREDICTOR=3', 'BIGTIFF=YES']
COG_OPTIONS = ['COMPRESS=DEFLATE', 'PREDICTOR=FLOATING_POINT', 'BIGTIFF=YES', 'BLOCKSIZE=512',
               'OVERVIEWS=IGNORE_EXISTING', 'OVERVIEW_RESAMPLING=AVERAGE']  # threads: GDAL_NUM_THREADS
VERTICAL_NOTE = 'Heights transformed to the pipeline vertical CRS where both source and target vertical CRS are configured.'


def create_raster(path, reference, nodata=-9999, vertical_note=VERTICAL_NOTE):
    ds = gdal.GetDriverByName('GTiff').Create(str(path), reference.RasterXSize, reference.RasterYSize, 1, gdal.GDT_Float32, OPTIONS)
    ds.SetGeoTransform(reference.GetGeoTransform())
    ds.SetProjection(reference.GetProjection())
    ds.GetRasterBand(1).SetNoDataValue(nodata)
    ds.SetMetadataItem('VERTICAL_DATUM_NOTE', vertical_note)
    ds.GetRasterBand(1).SetUnitType('m')
    return ds


def aoi_mask(geometry, reference, path, epsg=25832):
    geometry = project(geometry, srs(epsg))
    memory = ogr.GetDriverByName('Memory').CreateDataSource('')
    layer = memory.CreateLayer('aoi', srs(epsg), ogr.wkbUnknown)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(geometry)
    layer.CreateFeature(feature)
    ds = gdal.GetDriverByName('GTiff').Create(str(path), reference.RasterXSize, reference.RasterYSize, 1, gdal.GDT_Byte,
                                            ['TILED=YES', 'COMPRESS=DEFLATE', 'BIGTIFF=IF_SAFER'])
    ds.SetProjection(reference.GetProjection())
    ds.SetGeoTransform(reference.GetGeoTransform())
    ds.GetRasterBand(1).Fill(0)
    gdal.RasterizeLayer(ds, [1], layer, burn_values=[1])
    ds.FlushCache()
    return ds


def write_cog(source, destination):
    """Publish lossless Float32 terrain as a COG with internal overviews; replace only on success."""
    destination = Path(destination)
    temporary = destination.with_suffix('.cog.part.tif')
    if gdal.GetDriverByName('COG') is None:
        raise RuntimeError('This GDAL installation does not provide the COG driver.')
    with gdal_progress('Writing COG ' + destination.name) as callback:
        with gdal.Translate(str(temporary), str(source), format='COG',
                            creationOptions=COG_OPTIONS, callback=callback):
            pass
    with gdal.Open(str(temporary)) as check:
        if check.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE') != 'COG':
            raise RuntimeError(f'Output is not a Cloud Optimized GeoTIFF: {temporary}')
        if max(check.RasterXSize, check.RasterYSize) > 512 and check.GetRasterBand(1).GetOverviewCount() == 0:
            raise RuntimeError(f'COG output is missing internal overviews: {temporary}')
    temporary.replace(destination)
