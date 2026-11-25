# DTM harmonization pipeline: midterm-report writing brief

Prepared from the project documentation, current implementation, configurations and saved run records on **1 October 2026**.

## 1. Instructions for the report writer

Use this document as the factual basis for a technical midterm-report section on DTM preparation and harmonization for the Rhine-catchment project. Write at **medium technical depth**: describe processing operations, their sequence, assumptions, engineering choices and consequences. Explain the pipeline as a whole, with the Netherlands filling process as a necessary detailed example and Germany restricted to **North Rhine-Westphalia (NRW)**. Avoid a country-by-country narrative that repeats the shared stages.

Turn the material into connected academic prose, accompanied by a workflow diagram, pseudocode and a country/region processing table. The pseudocode below is a reusable skeleton; shorten its wording for the final report without changing the processing order. The table is partly populated with verified facts and includes placeholders for later additions.

Distinguish **implemented behavior**, **engineering rationale**, **recorded validation**, and **future work**. Rationales below explain the implications of the design; do not imply that every choice resulted from a formal optimization experiment. Do not invent acquisition dates, AHN release numbers, vertical corrections, country coverage, accuracy results or completed national runs. Use `[TO COMPLETE: ...]` for missing evidence. Internal source references at the end provide traceability; they are not substitutes for external methodological references if the final report requires those.

Suggested report structure:

1. Objective and scope of harmonization.
2. Common target grid and source preparation.
3. Transformation, aggregation and boundary treatment.
4. Netherlands gap filling and provenance.
5. Output verification, reproducibility and engineering choices.
6. Current validation, limitations and next steps.

## 2. Objective, scope and current state

The pipeline prepares heterogeneous national terrain rasters on a common horizontal grid so they can be used in subsequent terrain comparison or catchment analysis. Each invocation processes one country or region for a supplied area of interest (AOI). Shared coordination, grid definition, validation and output publication surround source-specific acquisition and processing rules.

The implemented sources are Dutch AHN terrain and the NRW terrain model. Germany is accessed through a regional selection mechanism, currently containing **NRW only**. Other German states and other countries require their own source and processing rules; they must not be described as already implemented.

The current standard output is a **5 m × 5 m, north-up raster in EPSG:25832 (ETRS89 / UTM zone 32N)**, with elevations in metres, Float32 storage and `-9999` for NoData. Horizontal CRS transformation, cell size and grid placement are harmonized. **Vertical datums are retained:** AHN remains in NAP and NRW remains in DHHN2016/NHN. Acquisition epochs and provider production methods are also not harmonized here.

This stage produces prepared terrain, coverage information and provenance. It does not calculate cross-source elevation differences or comparison statistics. Those operations must later select common valid coverage and explicitly address the vertical-datum difference. A file described as “comparison-ready” is geometrically prepared, not evidence that all scientific comparability issues are resolved.

Current configurations select separate AOI files: `country_masks/Netherlands.gpkg` and `country_masks/Germany_NRW_catchment.gpkg`. Saved September validation runs also used `small_study_area.gpkg`. The configured AOI determines clipping; selecting a country does not independently apply a national boundary. Do not infer identical output extents from the current country configurations.

## 3. End-to-end processing sequence

```text
Configuration + AOI polygon + source specification
    -> validate inputs and select country/region processing rules
    -> define the common target lattice and exact output extent
    -> plan native source chunks with boundary/donor context
    -> acquire or reuse validated native rasters
    -> clean invalid source values in working copies
    -> mosaic the selected cleaned rasters at native resolution
    -> create the unfilled 5 m surface:
         Netherlands: one combined horizontal reprojection and average resampling
         NRW: exact aggregation of aligned 1 m cells into 5 m cells
    -> Netherlands only, if enabled: fill remaining target-grid gaps
         retain unfilled baseline + filled alternative + fill-status raster
    -> remove temporary context and apply the original AOI mask
    -> verify grid geometry, validity and nonempty selected coverage
    -> cut finished output tiles and stitch them without resampling
    -> verify pixel equality; save result metadata and successful-run pointer
```

### 3.1 Input validation and target-grid definition

The AOI is checked and transformed into the target CRS, then used to define a grid that covers the study area and aligns with the common 5 m grid.

Three distinct requirements must be explained:

- **Common CRS:** coordinates refer to the same horizontal system.
- **Common lattice:** resolution, orientation and cell-edge placement agree, allowing matching cells in overlapping areas.
- **Identical raster geometry:** extent, row count and column count also agree, enabling direct cell-by-cell array operations.

**Design implication:** fixing the grid before terrain processing makes the output independent of arbitrary source-tile extents and supports reproducible cross-source alignment. Five metres is the adopted project scale, balancing detail and data volume; no resolution-optimization study was found. A 5 m surface cannot retain all sub-cell terrain structure present at 0.5 or 1 m. NRW currently requires 5 m output; the Dutch path supports other explicitly configured resolutions, but 5 m is the current shared standard.

### 3.2 Acquisition planning and boundary context

Download requests use a stable chunk lattice in each source's native CRS and resolution. Only chunks intersecting the buffered acquisition geometry are selected. Current source chunks are 1 km square for AHN and 2 km square for NRW. These are acquisition units, separate from the final output tiles.

The acquisition area is larger than the final AOI because a retained output cell can have its centre inside the polygon while part of its footprint lies outside. Its average should use available terrain across that footprint. With Dutch filling enabled, nearby donor cells outside the AOI must also be available.

For output cell width `r` and Dutch search distance `R`, the implemented context is:

| Context | Rule | Current value |
| --- | --- | --- |
| Basic acquisition buffer | Half the target-cell diagonal, `r / sqrt(2)` | Approximately 3.536 m |
| Dutch acquisition buffer with filling | Basic buffer + `R` + another half-cell diagonal for donor footprints | Approximately 27.071 m in the target CRS |
| Additional Dutch native margin | Add one native cell after transforming the buffered polygon to EPSG:28992 | 0.5 m |
| Temporary Dutch target-grid margin with filling | `ceil(R / r) + 1` cells on every side | 5 cells = 25 m per side |

NRW uses the basic footprint buffer only. The acquisition buffer and the temporary target-grid margin serve different purposes and need not have the same numerical width. Neither changes the final AOI or target extent. Extra context can increase download and storage requirements, but reduces artificial truncation at processing boundaries.

### 3.3 Acquisition, caching and source validation

Native-resolution terrain is obtained from Web Coverage Services (WCS). Previously downloaded tiles are reused. Validation checks readable raster data, expected CRS, resolution, bounds and raster structure. 

### 3.4 Cleaning and mosaicking

Cleaning operates on derived copies and preserves raw downloaded files. Masked pixels, declared NoData, nonfinite values and extreme sentinel values are converted into the common NoData representation **before averaging**. The extreme-value rule is a numerical safeguard, not a terrain-based outlier filter; ordinary finite elevations are not smoothed or removed here.

**Design implication:** operating on the shared mosaic makes source-tile borders irrelevant to neighboring contributions during resampling and filling. Materializing native mosaics and retaining intermediate products aid inspection but increase disk use.

### 3.5 Horizontal transformation and average resampling

For AHN, native **0.5 m EPSG:28992 (Amersfoort / RD New)** terrain is transformed directly into the 5 m target grid in one combined reprojection-and-average operation. The exact target extent and dimensions constrain the output. Transformation approximation is disabled, and automatic vertical shifting is explicitly disabled. “Exact” here describes the transformation calculation settings, not a claim of error-free source geolocation.

There is **no intermediate 1 m surface**, and no later resampling for output tiling. Combining reprojection and resolution change avoids repeated resampling. Average resampling represents the valid contributing source elevations within a target footprint; because the grids are transformed relative to each other, AHN aggregation is not a simple fixed 10 × 10 array reduction.

For NRW, native **1 m EPSG:25832** cells already lie on an integer-metre grid that nests exactly in the target lattice. The pipeline verifies this and computes the arithmetic mean of valid elevations in each **5 × 5 block**. Missing source coverage is padded with NoData. No terrain reprojection, grid shift or separate alignment resampling is performed.

For both sources, invalid contributors are excluded from averaging. A target cell with some valid source support can become valid even if its footprint is only partly observed; a cell with no valid contribution remains NoData.

**Tradeoff:** averaging provides a consistent coarse terrain representation and reduces output volume, but can suppress narrow embankments, channels and local extremes. No preservation of hydrological connectivity or breaklines is enforced. The two adapters share the averaging principle while using processing paths appropriate to their different native grids.

## 4. Netherlands filling: complete sequence and interpretation

### 4.1 Placement and rationale

The current order is **clean native data -> mosaic -> reproject/average to 5 m -> fill remaining gaps -> final crop/mask -> publish**.

Post-resampling filling addresses gaps in the product that will actually be used. Some native gaps cease to be NoData after averaging because neighboring valid native samples contribute to the same target cell. Only target cells still invalid are considered for interpolation.

This placement preserves every valid unfilled target elevation exactly, makes the provenance flag binary, and operates on far fewer cells than native 0.5 m filling. For equal mapped area, 5 m cells are roughly 100 times fewer than 0.5 m cells; this is a grid-size comparison, not a measured runtime or memory improvement.

The tradeoff is that native gap shapes and fine terrain detail have already been reduced by aggregation. Partly observed but valid target cells are left unchanged. Filling at 5 m is therefore a different estimator from filling the native surface and then averaging it; historical accuracy results cannot be transferred directly.

### 4.2 Algorithm and eligibility

Filling is enabled by default for the Netherlands, with a **20 m maximum search distance**, inverse-distance interpolation and **zero smoothing**. The search distance is converted from metres to target pixels: 20 m corresponds to 4 pixels at 5 m resolution. The extra temporary margin is five pixels per side to retain context.

Valid donors outside the AOI can contribute. The donor mask is based on terrain validity rather than polygon membership, so valid terrain in polygon-excluded areas can also provide surrounding context. Estimates outside the AOI or inside polygon holes are not retained in the final products.

The selection policy does not classify gaps by cause, use building footprints, exclude water, impose a connected-hole area cutoff, or use NRW as an interpolation source. A 20 m search limit is a donor-distance parameter, not a maximum hole diameter or a guarantee of reconstruction. Large gaps may be filled only at their margins. The retained IDW method provides a simple local baseline within the existing software stack; it is not established as the best terrain estimator for every landscape.

### 4.3 Products and scientific limits

| Dutch product | Interpretation |
| --- | --- |
| `ahn.tif` | Selected final terrain: filled when filling is enabled, unfilled otherwise. |
| `ahn_unfilled.tif` | Baseline before gap interpolation, retained when filling is enabled. |
| `ahn_fill_fraction.tif` | Despite the legacy name, current output is **binary target-cell status**: 0 = valid before filling; 1 = newly interpolated; NoData = unresolved or excluded. |
| Filling report | Candidate, accepted and remaining counts and areas; settings, grid information and timing. |

Interpolation estimates missing terrain. It cannot establish the real surface beneath buildings, measured bathymetry, or water levels. Distance-based interpolation can connect terrain across rivers or embankments because no physical barriers are supplied. The 20 m setting is a selected default, not a nationally optimized threshold. Keeping the baseline and fill status allows later analysis to separate unchanged and estimated cells and assess sensitivity to interpolation.

## 5. Final masking, publication and reproducibility

Final masking uses **cell-centre polygon membership**, preserving polygon holes. The full rectangular target grid is retained; excluded cells are assigned NoData. Delaying the final mask preserves useful neighboring terrain during aggregation and interpolation. This is an AOI mask, not the intersection of valid coverage from two countries.

The selected prepared surface must contain valid AOI coverage. If it is entirely NoData, the run fails while preserving diagnostic output and the previous successful-run pointer. CRS, dimensions, transform and extent are checked against the target reference. The default coordinate comparison tolerance is `1e-8 m`; this is a numerical alignment check, not a statement of terrain accuracy.

The documented runtime uses Python and GDAL, with NumPy and HTTP acquisition support. Windows uses the available QGIS/OSGeo4W environment; the Linux environment record describes Python GDAL bindings matched to the installed GDAL library. Record the actual runtime versions for the runs cited in the report rather than treating one environment record as universal.

## 6. Pseudocode skeleton

The operations below are conceptual, not repository function names. `G` denotes the final grid; `G+` is a temporary extension of the same lattice. “Valid” includes the common mask, NoData and finite-value rules.

### Algorithm 1: common preparation workflow

```text
INPUT: AOI polygon A, source S, target specification T, processing settings P
OUTPUT: prepared DTM H, grid/provenance records, optional baseline B and status F

1  Validate A, S and P; select supported country/region rules.
2  Transform A for planning, preserving polygon holes and boundary shape.
3  Define G from a validated reference, or snap the AOI bounds outward
   to the 5 m EPSG:25832 lattice.
4  Buffer acquisition geometry for target-cell footprints and, where enabled,
   interpolation donors; select intersecting native source chunks.
5  Save the plan, configuration and AOI identity.
6  Retrieve source metadata; reuse validated cached chunks or download them.
   Validate every selected source and save the ordered source manifest.
7  Clean invalid samples in copies; assemble a native-resolution mosaic M.

8  IF S is Netherlands AHN:
       G+ <- G extended by ceil(search_distance / cell_width) + 1 cells
             if filling is enabled; otherwise G
       B+ <- transform and average M directly from native 0.5 m to G+
             using one horizontal resampling operation and no vertical shift
       IF filling is enabled:
           (H+, F+, report) <- target-grid filling procedure(B+, A, P)
           H, F <- pixel-copy crop H+, F+ to G
       ELSE:
           H <- pixel-copy crop B+ to G
       B <- pixel-copy crop B+ to G

9  ELSE IF S is Germany / NRW:
       Verify native 1 m cells nest exactly in G.
       B <- mean of valid native samples in each exact 5 x 5 footprint;
            use NoData where the contributor count is zero
       H <- B
       Do not reproject terrain or perform gap filling.

10 Apply the original AOI cell-centre mask and final validity rules
   to H and any retained B and F.
11 Verify output grid geometry; fail if H has no valid AOI cells.
12 Cut H into exact target-grid windows; stitch the explicit tile list.
13 Verify stitched geometry and pixel-for-pixel equality with H.
14 Save output paths, coverage counts, datum notes and optional fill report.
   Update the successful-run pointer only after all required checks pass.
```

### Algorithm 2: Netherlands target-grid filling

```text
INPUT: unfilled extended-grid surface B+, original AOI A, radius R = 20 m
OUTPUT: filled surface H+, binary status F+, filling statistics

1  D <- fixed validity mask of B+ before interpolation
2  I <- original AOI rasterized by cell centres on the grid of B+
3  C <- I AND NOT D                         # eligible missing target cells
4  E <- bounded inverse-distance estimates from B+ using D as donor mask,
        search distance R / cell_width, and zero smoothing
5  K <- C AND valid(E)                      # accepted estimates
6  H+ <- copy B+
7  H+[K] <- E[K]
8  Preserve H+[D] = B+[D] exactly; leave other missing cells as NoData.
9  F+ <- NoData everywhere; F+[D] <- 0; F+[K] <- 1
10 Record original-valid, candidate, accepted and residual counts inside I,
   corresponding raster areas, parameters and timing.
11 Return products for lossless cropping and final AOI masking.
```

Algorithm 2 can use valid contextual donors outside `I`; `I` limits accepted estimates. Its masks remain fixed during estimation. Additional countries must supply an explicit supported branch rather than automatically inheriting either existing country's processing assumptions.

## 7. Country/region processing-table skeleton

Use one row per distinct source/processing regime. Split Germany into state-level rows when their inputs or rules differ. The verified rows below can be retained; add further rows only when their workflow is established. In a typeset report this is suited to landscape orientation or two linked tables if space is limited.

| Country / region and status | Source / release / epoch | Native horizontal CRS; cell size | Vertical datum and treatment | Acquisition / context | Invalid-data and mosaic treatment | Horizontal transformation and resampling | Gap filling: stage, method, parameters | Final mask, grid and products | Evidence / unresolved items |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Netherlands — implemented | AHN WCS, coverage `dtm_05m`; [TO COMPLETE: release and local acquisition epoch] | EPSG:28992; 0.5 m | NAP retained; no vertical conversion | Native 1 km chunks; footprint + donor context when filling | Common validity cleaning in copies; native shared mosaic | One direct horizontal reprojection and average resampling to 5 m EPSG:25832 | After resampling; IDW; 20 m; zero smoothing; all AOI NoData eligible; preserve valid target cells | Original AOI centre mask; common lattice; selected DTM + unfilled baseline + binary fill status when enabled | Synthetic checks and saved small-AOI run; current-order accuracy evaluation pending |
| Germany / NRW only — implemented | NRW WCS, coverage `nw_dgm`; [TO COMPLETE: release and local acquisition epoch] | EPSG:25832; 1 m, integer-metre edges | DHHN2016/NHN retained; no vertical conversion | Native 2 km chunks; target-footprint context | Common validity cleaning in copies; native shared mosaic | Exact valid-sample 5 × 5 mean; no terrain reprojection or grid shift | None in this pipeline | Original AOI centre mask; common lattice; selected DTM | Synthetic checks, documented real-data pilots and saved small-AOI run; regional performance evaluation pending |
| [Country / region — planned or implemented] | [Provider, product, release, epoch] | [EPSG; resolution; grid origin] | [Datum; retained or specified conversion] | [Access method; chunking; context] | [Validity rules; mosaic decisions] | [Transformation; target grid; method; number of resampling stages] | [None, or eligibility, placement, method, radius and provenance] | [AOI policy; outputs; coverage rules] | [Run/test evidence; limitations; citation] |

Table notes: common output is 5 m EPSG:25832, Float32, metres, NoData `-9999`. “No filling” means no additional filling performed by this pipeline; it does not describe how the provider originally produced its DTM. Shared lattice does not imply identical extents or complete coverage. Retain separate evidence for processing correctness and elevation accuracy.

## 8. Validation evidence and claims that remain open

### 8.1 Available implementation checks

The current test source covers target-grid placement, invalid reference rejection, boundary context, direct AHN native-to-5 m baseline equivalence, a single warp before Dutch filling, preservation of valid target values, binary fill status, outside-AOI donor context, polygon holes, unsupported gaps, tile-seam consistency, exact NRW block means, raw-source immutability and lossless stitching. Acquisition tests cover concurrency, ordering, pacing, retries, cache reuse and interruption behavior.

The prepared documentation reports successful test suites at several development dates. Those totals describe different revisions and must not be presented as a fresh test result for the complete current code. This handoff was prepared by inspecting source and saved records; it did not rerun the processing or test suite.

### 8.2 Saved 5 m runs: evidence of execution, not accuracy

The following values are recorded in saved results, not newly computed raster audits:

| Saved run | Recorded scope and result |
| --- | --- |
| Netherlands `2026-09-29_21-50-42` | `small_study_area.gpkg`; 2585 × 1393 cells at 5 m; filling explicitly recorded as `after_resampling`; 1,212,803 valid baseline cells and 1,322,212 valid filled cells; 109,409 cells filled and 2,083,421 residual AOI NoData cells. |
| NRW `2026-09-29_09-52-46` | The same small-study AOI and recorded grid geometry; 3,006,951 valid cells; no pipeline filling. |

### 8.3 Future work / report placeholders

- `[TO COMPLETE: source releases, spatially varying acquisition epochs and authoritative data citations.]`
- `[TO COMPLETE: accuracy assessment for the current post-resampling filling order, using withheld valid terrain and suitable independent observations where available.]`
- `[TO COMPLETE: sensitivity to search distance, slope, gap size and landscape type; explicitly assess water and coverage boundaries.]`
- `[TO COMPLETE: decisions on vertical-datum harmonization before interpreting cross-source elevation differences.]`
- `[TO COMPLETE: full-AOI runtime, peak RAM, disk demand, completeness and acceptance criteria.]`
- `[TO COMPLETE: additional countries/German states and their verified processing-table rows.]`

Future cross-source comparison should report the common-valid mask and distinguish unchanged from interpolated cells. Smaller disagreement with another DTM is not, by itself, proof of better terrain accuracy.

## 9. Source map and reconciliation of older documentation

All paths below are relative to this Markdown file. The handoff is self-contained; the links allow project members to check provenance.

| Source | Used for / qualification |
| --- | --- |
| [Workflow overview](README.md) | Shared architecture, outputs and acquisition behavior. Its opening native-fill ordering is stale; use the current order documented here. |
| [Netherlands preparation](NETHERLANDS_PREPARATION.md) | Grid definition, Dutch processing and current filling settings. Some legacy product wording still describes a continuous fill fraction; current status is binary. |
| [Germany / NRW preparation](GERMANY_NRW_PREPARATION.md) | Regional scope, exact aggregation, validation and extension rules. Its example AOI is older than the current config. |
| [Historical filling plan](AHN_HOLE_FILLING_PLAN.md) | Original design intent, gap-selection policy and interpolation limitations. Native filling, initial defaults and fractional provenance are historical. |
| [Historical filling validation](HOLE_FILLING_VALIDATION.md) | Exploratory native-grid pilot and explicit warning about changed production order. |
| [Generated pilot summary](../data/old_runs/netherlands/pilots/hole_filling/20260926T221031Z/PILOT_REPORT.md) | Historical natural-gap and withheld-patch results; not a national or current-order benchmark. |
| [27 September run review](../data/old_runs/netherlands/20260927T184910Z_df2e71a3/analysis/REVIEW.md) | Historical 1 m coverage audit; demonstrates why processing version and AOI matter. |
| [Server environment record](DTM_server_environment_setup.md) | Documented Linux setup and version compatibility. |
| [Netherlands configuration](../config.netherlands.json), [NRW configuration](../config.germany.nrw.json) | Current AOI selection, source specifications and configured defaults. |
| [Target-grid logic](../dtm/target_grid.py), [geometry and validity rules](../dtm/geo.py), [shared raster operations](../dtm/process.py) | Exact grid contract, cleaning, mosaicking and horizontal warp behavior. The shared file also contains comparison routines that are not invoked by current preparation. |
| [Dutch source planning](../dtm/countries/netherlands/__init__.py), [Dutch processing](../dtm/countries/netherlands/processing.py), [Dutch filling](../dtm/countries/netherlands/hole_filling.py) | Authoritative current stage order, context, donor masks, baseline preservation and binary status. |
| [NRW planning](../dtm/countries/germany/nrw/__init__.py), [NRW processing](../dtm/countries/germany/nrw/processing.py) | Native-grid restrictions and exact 5 × 5 aggregation. |
| [Acquisition validation](../dtm/acquire.py), [download coordination](../dtm/downloads.py), [publication](../dtm/publication.py), [coordinator](../dtm/coordinator.py) | Cache integrity, download concurrency, lossless output assembly and successful-run bookkeeping. |
| [5 m tests](../tests/test_five_metre.py), [filling tests](../tests/test_hole_filling.py), [NRW tests](../tests/test_nrw.py) | Implemented numerical and structural checks; source inspection alone is not a new test pass. |
| [Saved Dutch result](../data/old_runs/netherlands/2026-09-29_21-50-42/result.json), [Dutch plan](../logs/preparation/netherlands/2026-09-29_21-50-42/plan.json), [saved NRW result](../data/old_runs/germany/nrw/2026-09-29_09-52-46/result.json), [NRW plan](../logs/preparation/germany/nrw/2026-09-29_09-52-46/plan.json) | Run-specific evidence for the recorded 5 m small-AOI outputs and scope. |

When sources disagree, use current code/configuration to describe intended current behavior and each run's own records to describe what was executed. In particular, do not copy the older “fill at 0.5 m before warping,” “continuous fill fraction,” “current 1 m output,” or “both configurations use the small study area” descriptions into the present methodology.
