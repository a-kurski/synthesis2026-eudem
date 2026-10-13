"""Official Hessen district selection, ZIP lifecycle, provenance and processing."""
from copy import deepcopy
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

import numpy as np
from osgeo import gdal, ogr
import requests

from dtm.acquire import sha256
from dtm.coordinator import execute, load_config
from dtm.countries.germany import hessen
from dtm.countries.germany.hessen import acquisition as acq
from dtm.countries.germany.hessen.processing import validate_native
from dtm.geo import rectangle, srs, verify_alignment, project
from dtm.paths import raw_directory, receipt_path, scoped_root
from dtm.target_grid import plan_grid, write_reference
from test_preparation import raster


class HessenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_hessen_official_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = load_config(Path(__file__).resolve().parents[1]/'config.germany.hessen.json')
        self.config.update(cache_root=str(self.root/'data'), output_root=str(self.root/'data'),
                           logs_dir=str(self.root/'logs'), download_attempts=1, block_size=2, request_pause_seconds=0)
        self.geometry = rectangle([498010,5554010,498020,5554020])
        self.geometry.AssignSpatialReference(srs(25832))
        self.boundaries([('411',[498000,5554000,499000,5555000]),('414',[600000,5554000,601000,5555000])])
        self.plan = hessen.plan(self.geometry,self.config)
        self.region = self.plan['regions'][0]
        self.log=self.root/'run_log'; self.log.mkdir()

    def boundaries(self, rows):
        path=self.root/'districts.gpkg'
        if path.exists(): path.unlink()
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(path)) as ds:
            layer=ds.CreateLayer('districts',srs(25832),ogr.wkbPolygon)
            layer.CreateField(ogr.FieldDefn('KREIS_NR',ogr.OFTString))
            for code,extent in rows:
                f=ogr.Feature(layer.GetLayerDefn());f.SetField('KREIS_NR',code);f.SetGeometry(rectangle(extent));layer.CreateFeature(f)
        self.config['source'].update(boundary_file=str(path),boundary_layer='districts')

    def raw(self,value=42,name='dgm1_32_498_5554_1_he.tif'):
        return raster(self.root/name,np.full((1000,1000),value,dtype='float32'),25832,(498000,1,0,5555000,0,-1))

    def package(self,region=None,entries=None):
        region=region or self.region
        directory,_=acq.locations(self.config,region)
        path=directory/f'PKT_{region["name"]}.zip'
        if entries is None:
            source=self.raw()
            entries=[('tiles/'+source.name,source.read_bytes()),('tiles/'+source.stem+'.tfw',b'1\n0\n0\n-1\n498000.5\n5554999.5\n'),('metadata.txt',b'official fixture'),('tiles/dgm1_32_600_5554_1_he.tif',b'outside AOI, never processed')]
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,data in entries:z.writestr(name,data)
        return path

    def response(self,body,status=200,headers=None):
        response=MagicMock();response.__enter__.return_value=response
        response.status_code=status;response.headers=headers or {'Content-Length':str(len(body))}
        response.iter_content.return_value=[body]
        return response

    def test_spatial_selection_mapping_reprojection_and_unknown_district(self):
        self.assertEqual([r['id'] for r in self.plan['regions']],['411'])
        projected=project(self.geometry,srs(4326))
        self.assertEqual(hessen.plan(projected,self.config)['regions'],self.plan['regions'])
        self.boundaries([('414',[498000,5554000,499000,5555000])])
        self.assertEqual(hessen.plan(self.geometry,self.config)['regions'][0]['name'],'Kreisfreie Stadt Wiesbaden')
        self.boundaries([('999',[498000,5554000,499000,5555000])])
        with self.assertRaisesRegex(ValueError,'999'):hessen.plan(self.geometry,self.config)

    def test_url_encoding_date_validation_and_legacy_config_rejection(self):
        region={'id':'431','name':'Landkreis Bergstraße'}
        url=acq.package_url(self.config['source'],region)
        self.assertIn('Landkreis%20Bergstra%C3%9Fe/PKT_Landkreis%20Bergstra%C3%9Fe.zip',url)
        for changes in ({'download_date':'20260230'},{'download_date':'today'},{'type':'tar'}):
            config=deepcopy(self.config);config['source'].update(changes)
            with self.assertRaises(ValueError):hessen.validate_config(config)

    def test_full_regional_extraction_tfw_preservation_and_aoi_only_processing(self):
        package=self.package()
        with patch('requests.Session.get') as get:
            paths=acq.download(self.config,self.plan,self.log);get.assert_not_called()
        self.assertEqual(len(paths),1)
        self.assertTrue(paths[0].name.startswith('he_20261013_411_'))
        root,index=acq.reusable_extraction(self.config,self.region)
        self.assertEqual(len(index['tiles']),2)
        self.assertTrue((root/'metadata.txt').exists())
        self.assertTrue(list(root.rglob('*.tfw')))
        self.assertEqual(len(list(raw_directory(self.config).iterdir())),1)
        package.unlink()
        with patch.object(acq,'cached_package') as fetch:
            self.assertEqual(acq.download(self.config,self.plan,self.log),paths);fetch.assert_not_called()
        with gdal.Open(str(root/index['tiles'][0]['name']),gdal.GA_Update) as ds:ds.GetRasterBand(1).Fill(3)
        with self.assertRaisesRegex(ValueError,'differs from its receipt'):acq.download(self.config,self.plan,self.log)

    def test_official_nested_package_preserves_zips_tfw_and_reuses_extraction(self):
        inner=io.BytesIO()
        source=self.raw()
        with zipfile.ZipFile(inner,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(source.name,source.read_bytes())
            z.writestr(source.stem+'.tfw',b'original world file')
        self.package(entries=[('Darmstadt - DGM1.zip',inner.getvalue()),('readme.txt',b'official package')])
        with patch('requests.Session.get') as get:
            paths=acq.download(self.config,self.plan,self.log)
            self.assertEqual(len(paths),1)
            root,index=acq.reusable_extraction(self.config,self.region)
            self.assertTrue((root/'Darmstadt - DGM1.zip').is_file())
            self.assertEqual(next(root.rglob('*.tfw')).read_bytes(),b'original world file')
            self.assertTrue(index['tiles'][0]['name'].startswith('_nested/'))
            with patch.object(acq,'extract_contents') as extract:
                self.assertEqual(acq.download(self.config,self.plan,self.log),paths)
                extract.assert_not_called()
            get.assert_not_called()

    def test_unsafe_or_tif_free_inner_zip_keeps_outer_archive_without_completion(self):
        for name in ('../bad.tif','only.tfw'):
            with self.subTest(name=name):
                inner=io.BytesIO()
                with zipfile.ZipFile(inner,'w') as z:z.writestr(name,b'x')
                archive=self.package(entries=[('Darmstadt - DGM1.zip',inner.getvalue())])
                _,records=acq.locations(self.config,self.region)
                (records/'archive.json').unlink(missing_ok=True)
                original=sha256(archive)
                with self.assertRaises(ValueError):acq.download(self.config,self.plan,self.log)
                self.assertEqual(sha256(archive),original)
                self.assertIsNone(acq.reusable_extraction(self.config,self.region))

    def test_incomplete_extraction_recovers_from_zip(self):
        self.package();acq.download(self.config,self.plan,self.log)
        root,index=acq.reusable_extraction(self.config,self.region)
        (root/'metadata.txt').unlink()
        self.assertIsNone(acq.reusable_extraction(self.config,self.region))
        with patch('requests.Session.get') as get:
            acq.download(self.config,self.plan,self.log);get.assert_not_called()
        self.assertTrue((root/'metadata.txt').exists())

    def test_interrupted_extraction_never_publishes_completion(self):
        self.package()
        original=zipfile.ZipFile.open
        def fail(package,member,*args,**kwargs):
            if isinstance(member,zipfile.ZipInfo) and member.filename=='metadata.txt':raise OSError('interrupted')
            return original(package,member,*args,**kwargs)
        # Validate/cache the ZIP first so the injected error targets extraction.
        acq.cached_package(MagicMock(),self.config,self.region)
        with patch.object(zipfile.ZipFile,'open',fail),self.assertRaises(OSError):
            acq.download(self.config,self.plan,self.log)
        self.assertIsNone(acq.reusable_extraction(self.config,self.region))
        acq.download(self.config,self.plan,self.log)
        self.assertIsNotNone(acq.reusable_extraction(self.config,self.region))

    def test_resume_zip_and_failed_refresh_preserves_existing_archive(self):
        archive=self.package();body=archive.read_bytes();archive.unlink()
        part=archive.with_name(archive.name+'.part');split=len(body)//2;part.write_bytes(body[:split])
        session=MagicMock();session.get.return_value=self.response(body[split:],206,{'Content-Range':f'bytes {split}-{len(body)-1}/{len(body)}'})
        path,_=acq.cached_package(session,self.config,self.region)
        self.assertEqual(session.get.call_args.kwargs['headers']['Range'],f'bytes={split}-')
        self.assertEqual(path.read_bytes(),body)
        self.config['reuse_cache']=False;session.get.return_value=self.response(b'not a ZIP')
        with self.assertRaises(RuntimeError):acq.cached_package(session,self.config,self.region)
        self.assertEqual(path.read_bytes(),body)

    def test_missing_date_package_fails_clearly_without_skipping_district(self):
        session=MagicMock();response=self.response(b'',404)
        response.raise_for_status.side_effect=requests.HTTPError('404',response=response)
        session.get.return_value=response
        with self.assertRaisesRegex(RuntimeError,'download_date'):acq.cached_package(session,self.config,self.region)

    def test_unsafe_empty_and_case_colliding_zip_members_rejected(self):
        for entries in [[('../outside.tif',b'x')],[('a.tif',b'x'),('A.tif',b'y')],[('only.tfw',b'x')]]:
            with self.subTest(entries=entries):
                package=self.package(entries=entries)
                with self.assertRaises(ValueError):acq.validate_zip(package)
        package=self.package()
        with zipfile.ZipFile(package,'a') as z:
            link=zipfile.ZipInfo('link.tif');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(link,'target')
        with self.assertRaisesRegex(ValueError,'Unsafe'):acq.validate_zip(package)

    def test_duplicate_district_tiles_are_deduplicated_only_if_equal(self):
        self.package(entries=[('tile.tif',self.raw().read_bytes())])
        second={'id':'414','name':'Kreisfreie Stadt Wiesbaden'}
        self.package(second,entries=[('tile.tif',self.raw().read_bytes())])
        plan={**self.plan,'regions':[self.region,second]}
        self.assertEqual(len(acq.download(self.config,plan,self.log)),1)
        self.package(second,entries=[('tile.tif',self.raw(value=50).read_bytes())])
        _,records=acq.locations(self.config,second)
        (records/'archive.json').unlink();(records/'extraction.json').unlink()
        with self.assertRaisesRegex(ValueError,'Conflicting official'):acq.download(self.config,plan,self.log)

    def test_legacy_mapterhorn_cache_is_never_used(self):
        old=scoped_root(self.config,'cache_root')/'source_archive/dehessen.tar'
        old.parent.mkdir(parents=True,exist_ok=True);old.write_bytes(b'legacy')
        self.package()
        paths=acq.download(self.config,self.plan,self.log)
        receipt=json.loads(receipt_path(paths[0],self.config).read_text())
        self.assertIn('gds.hessen.de',receipt['source']['url'])
        self.assertNotIn('mapterhorn',json.dumps(receipt).lower())
        self.assertEqual(old.read_bytes(),b'legacy')

    def test_selected_native_alternative_nodata_and_filename_bounds(self):
        source=self.raw()
        with gdal.Open(str(source),gdal.GA_Update) as ds:ds.GetRasterBand(1).SetNoDataValue(-1e10)
        self.package(entries=[(source.name,source.read_bytes())])
        paths=acq.download(self.config,self.plan,self.log)
        self.assertEqual(validate_native(paths[0])['nodata'], -1e10)
        with gdal.Open(str(source),gdal.GA_Update) as ds:
            ds.SetGeoTransform((498001,1,0,5555000,0,-1))
        self.package(entries=[(source.name,source.read_bytes())])
        _, records=acq.locations(self.config,self.region)
        (records/'archive.json').unlink(); (records/'extraction.json').unlink()
        with self.assertRaisesRegex(ValueError,'bounds differ'):
            acq.download(self.config,self.plan,self.log)

    def test_missing_or_alternative_nodata_masks_and_nonfinite_average(self):
        # Model the double-dot filename and missing NoData tag in district 431.
        for nodata in (None, -32768):
            with self.subTest(nodata=nodata):
                values=np.full((10,10),100,dtype='float32')
                values[:5,:5]=np.nan  # All-missing output cell.
                values[0,5]=np.inf
                values[0,6]=1e30
                values[0,7]=999  # Explicitly masked, must not affect the mean.
                values[0,8]=0  # A valid zero must remain in the mean.
                if nodata is not None: values[1,5]=nodata
                source=raster(self.root/f'source_{nodata}..tif',values,25832,
                              (498010,1,0,5554020,0,-1))
                with gdal.Open(str(source),gdal.GA_Update) as ds:
                    band=ds.GetRasterBand(1)
                    if nodata is None: band.DeleteNoDataValue()
                    else: band.SetNoDataValue(nodata)
                    band.CreateMaskBand(gdal.GMF_PER_DATASET)
                    mask=np.full((10,10),255,dtype='uint8');mask[0,7]=0
                    band.GetMaskBand().WriteArray(mask)
                original=sha256(source)
                self.assertEqual(validate_native(source)['nodata'],nodata)
                ref=write_reference(plan_grid(self.geometry,self.config['target']),
                                    self.root/f'reference_{nodata}.vrt')
                result=hessen.prepare([source],self.geometry,ref,self.root/f'run_{nodata}',self.config)
                count=22 if nodata is None else 21
                expected=np.array([[-9999,100*(count-1)/count],[100,100]],dtype='float32')
                with gdal.Open(result['prepared_raster']) as ds:
                    np.testing.assert_allclose(ds.ReadAsArray(),expected,rtol=0,atol=1e-5)
                    self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(),-9999)
                self.assertEqual(sha256(source),original)

    def test_missing_nodata_double_dot_filename_extraction(self):
        source=self.raw(name='dgm1_32_498_5554_1_he..tif')
        with gdal.Open(str(source),gdal.GA_Update) as ds:
            ds.GetRasterBand(1).DeleteNoDataValue()
        self.package(entries=[(source.name,source.read_bytes())])
        paths=acq.download(self.config,self.plan,self.log)
        self.assertEqual(len(paths),1)
        self.assertIsNone(validate_native(paths[0])['nodata'])

    def test_missing_crs_uses_verified_filename_grid_without_changing_source(self):
        source=self.raw(name='DGM1_32_498_5554_1_he.tif')
        with gdal.Open(str(source),gdal.GA_Update) as ds: ds.SetProjection('')
        self.package(entries=[(source.name,source.read_bytes())])
        paths=acq.download(self.config,self.plan,self.log)
        self.assertEqual(validate_native(paths[0])['crs'],'')
        original=sha256(paths[0])
        ref=write_reference(plan_grid(self.geometry,self.config['target']),self.root/'reference.vrt')
        result=hessen.prepare(paths,self.geometry,ref,self.root/'prepared',self.config)
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(),np.full((2,2),42,dtype='float32'))
            self.assertTrue(ds.GetSpatialRef().IsSame(srs(25832)))
        self.assertEqual(result['source_crs_assigned_from_config'],[str(paths[0])])
        self.assertEqual(sha256(paths[0]),original)
        with gdal.Open(str(source),gdal.GA_Update) as ds:
            ds.SetGeoTransform((498001,1,0,5555000,0,-1))
        with self.assertRaisesRegex(ValueError,'missing CRS'): validate_native(source)
        with gdal.Open(str(source),gdal.GA_Update) as ds:
            ds.SetGeoTransform((498000,1,0,5555000,0,-1))
            ds.SetProjection(srs(32632).ExportToWkt())
        with self.assertRaisesRegex(ValueError,'EPSG:25832'): validate_native(source)

    def test_coordinator_plan_and_complete_run(self):
        self.package()
        aoi=self.root/'aoi.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(aoi)) as ds:
            layer=ds.CreateLayer('hessen',srs(25832),ogr.wkbPolygon)
            f=ogr.Feature(layer.GetLayerDefn());f.SetGeometry(self.geometry);layer.CreateFeature(f)
        self.config['aoi']=str(aoi)
        with patch('requests.Session.get') as get:
            plan=execute(self.config,'plan');self.assertEqual(len(plan['source']['regions']),1)
            result=execute(self.config,'yes');get.assert_not_called()
        self.assertEqual(result['distributor'],'Hessen Geodaten online (HVBG)')
        self.assertTrue(Path(result['prepared_raster']).is_file())
        self.assertEqual(result['target_resolution_m'],5)
    def test_exact_average_seam_nodata_and_shared_reference(self):
        values = np.arange(100, dtype='float32').reshape(10, 10)
        values[:5, :5] = -9999
        values[0, 5] = -9999
        geometry = rectangle([498010, 5554010, 498020, 5554020])
        geometry.AssignSpatialReference(srs(25832))
        paths = [raster(self.root / 'left.tif', values[:, :5], 25832, (498010, 1, 0, 5554020, 0, -1)),
                 raster(self.root / 'right.tif', values[:, 5:], 25832, (498015, 1, 0, 5554020, 0, -1))]
        original = [sha256(p) for p in paths]
        # The shared reference extends beyond source coverage and AOI.
        larger = rectangle([498005, 5554005, 498025, 5554025])
        larger.AssignSpatialReference(srs(25832))
        ref = write_reference(plan_grid(larger, self.config['target']), self.root / 'target.vrt')
        result = hessen.prepare(paths, geometry, ref, self.root / 'prepared', self.config)
        expected = np.full((4, 4), -9999, dtype='float32')
        for row in range(2):
            for col in range(2):
                block = values[row*5:row*5+5, col*5:col*5+5]
                valid = block[block != -9999]
                if valid.size:
                    expected[row+1, col+1] = valid.mean()
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
            self.assertIn('unverified', ds.GetMetadataItem('VERTICAL_DATUM_NOTE'))
        verify_alignment(result['prepared_raster'], ref)
        self.assertEqual([sha256(p) for p in paths], original)
        self.assertIsNone(result['vertical_datum'])
        self.assertFalse(result['separate_alignment'])
