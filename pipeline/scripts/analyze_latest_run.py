"""Read-only raster audit; write analysis artifacts alongside a completed run."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap

def main():
    import json
    import numpy as np
    from osgeo import gdal
    from dtm.geo import windows, verify_alignment, read_aoi, project, srs
    root = Path(__file__).resolve().parents[1]
    r = json.loads((root / 'logs/preparation/netherlands/latest_run.json').read_text())
    run = Path(r['ahn_stitched']).parent
    out = Path(r['processed_tiles']['directory']) / 'analysis'
    out.mkdir(exist_ok=True)
    logdir = Path(r['log_directory'])
    cfg = json.loads((logdir / 'config.json').read_text())
    manifest = json.loads((logdir / 'source_manifest.json').read_text())
    a = {k: 0 for k in ['aoi_cells','before','after','new_valid','lost_valid','outside_valid','fraction_mask_mismatch','nonfinite','influenced','changed_existing','uninfluenced_changed']}
    a.update(min_height=float('inf'), max_height=-float('inf'), max_existing_change=0.)
    paths = [r[k] for k in ['prepared_raster','comparison_ready_raster','fill_fraction','aoi_mask']]
    for p in paths:
        verify_alignment(p,r['target_reference'])
    datasets = [gdal.Open(p) for p in paths]
    differences = []
    for w in windows(datasets[0],512):
        b,f,q,m = [ds.ReadAsArray(*w) for ds in datasets]
        bv,fv = b!=-9999,f!=-9999
        a['aoi_cells'] += int((m!=0).sum())
        for key,mask in [('before',bv),('after',fv),('new_valid',fv&~bv),('lost_valid',bv&~fv),('outside_valid',fv&(m==0)),('fraction_mask_mismatch',fv!=(q!=-9999)),('nonfinite',fv&~np.isfinite(f)),('influenced',fv&(q>0)),('changed_existing',bv&fv&(b!=f)),('uninfluenced_changed',bv&fv&(q==0)&(b!=f))]:
            a[key]+=int(mask.sum())
        if fv.any():
            a['min_height']=min(a['min_height'],float(f[fv].min()))
            a['max_height']=max(a['max_height'],float(f[fv].max()))
        common=bv&fv
        changed=common&(b!=f)
        if changed.any(): differences.append(np.abs(f[changed]-b[changed]))
        if common.any(): a['max_existing_change']=max(a['max_existing_change'],float(np.abs(f[common]-b[common]).max()))
    a['source_tiles']=len(manifest['tiles'])
    a['empty_source_tiles']=sum(t['receipt']['valid_cells']==0 for t in manifest['tiles'])
    a['new_raw_tiles']=len(list(Path(r['raw_ahn_tiles']).glob('*.tif')))
    a['run_size_bytes']=sum(p.stat().st_size for p in run.rglob('*') if p.is_file())
    a['stitched_sizes_bytes']={p.name:p.stat().st_size for p in Path(r['ahn_stitched']).glob('*.tif')}
    log=(logdir/'processing.log').read_text()
    a['warnings']=[line for line in log.splitlines() if 'warning' in line.lower() or 'error' in line.lower()]
    aoi,_,_=read_aoi(cfg['aoi'])
    nl,_,_=read_aoi(root/'netherlands.gpkg')
    ao=project(aoi,srs(28992)); nl=project(nl,srs(28992))
    a['polygon_area_km2']=ao.GetArea()/1e6
    a['area_intersecting_netherlands_gpkg_km2']=ao.Intersection(nl).GetArea()/1e6
    if differences:
        delta=np.concatenate(differences)
        a['changed_existing_absolute_difference_percentiles_m']=dict(zip(['median','p95','p99'],map(float,np.percentile(delta,[50,95,99]))))
    from dtm.process import aoi_mask
    with aoi_mask(nl.Intersection(ao),datasets[1],out/'netherlands_intersection_mask.tif') as country_mask:
        a['netherlands_aoi_cells']=a['netherlands_valid_after']=a['outside_netherlands_valid_after']=0
        for w in windows(datasets[1],512):
            inside=country_mask.ReadAsArray(*w)!=0
            valid=datasets[1].ReadAsArray(*w)!=-9999
            a['netherlands_aoi_cells']+=int(inside.sum())
            a['netherlands_valid_after']+=int((inside&valid).sum())
            a['outside_netherlands_valid_after']+=int((~inside&valid).sum())
    # Audit the actual interpolation grid, including historical native runs.
    filling = r['hole_filling']
    change_key = 'target_original_changes' if filling.get('stage') == 'after_resampling' else 'native_original_changes'
    a[change_key]=0
    filled_path = filling.get('filled_raster') or filling['filled_native']
    with gdal.Open(filling['source']) as orig, gdal.Open(filled_path) as filled:
        for w in windows(orig,1024):
            b,f=orig.ReadAsArray(*w),filled.ReadAsArray(*w)
            a[change_key]+=int(((b!=-9999)&(b!=f)).sum())
    (out/'audit.json').write_text(json.dumps(a,indent=2))
    print(json.dumps(a,indent=2),flush=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    b,f,q,m=[ds.ReadAsArray(buf_xsize=1200,buf_ysize=646) for ds in datasets]
    cat=np.where(m==0,0,np.where(f==-9999,1,np.where(b==-9999,3,2)))
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    fig,ax=plt.subplots(figsize=(12,7))
    colors=['#ffffff','#c9cdd2','#287d8e','#f1a340']
    ax.imshow(cat,cmap=ListedColormap(colors),vmin=0,vmax=3,interpolation='nearest')
    ax.set_title('AHN coverage after 20 m hole filling — small study area')
    ax.axis('off')
    ax.legend(handles=[Patch(color=c,label=t) for c,t in zip(colors,['Outside study area','Still NoData','Previously valid','Newly valid'])],loc='lower center',ncol=4,bbox_to_anchor=(.5,-.08))
    fig.savefig(out/'coverage.png',dpi=150,bbox_inches='tight')
    plt.close(fig)

if __name__=='__main__':
    bootstrap(__file__,'config.netherlands.json')
    main()
