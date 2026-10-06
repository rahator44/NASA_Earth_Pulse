#!/usr/bin/env python3
"""
STEP 12 — NISAR Real Flood/Wetland Showcase Pipeline
Streams real NISAR GCOV HDF5 over 19x20 km Atchafalaya AOI,
runs classical radar differencing, and outputs all UI products.
NO synthetic fallback. Traceable to NASA NISAR ASF DAAC.
"""
import io, json, sys, logging
import numpy as np
import h5py, fsspec, earthaccess, pyproj
from datetime import datetime, timezone
from pathlib import Path
from scipy import ndimage
from PIL import Image
from rasterio.features import shapes as raster_shapes
from rasterio.transform import Affine
from rasterio.warp import transform_geom

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("showcase")

ROOT        = Path(__file__).resolve().parents[2]
PROCESSED   = ROOT / "data" / "real" / "flood_showcase" / "processed"
STATIC_REAL = ROOT / "app" / "static" / "real"
for d in (PROCESSED, STATIC_REAL): d.mkdir(parents=True, exist_ok=True)

BEFORE_UR = "NISAR_L2_PR_GCOV_024_033_A_017_4005_DHDH_A_20260628T112725_20260628T112800_P05023_N_F_J_001"
AFTER_UR  = "NISAR_L2_PR_GCOV_025_033_A_017_4005_DHDH_A_20260710T112724_20260710T112759_P05023_N_F_J_001"
BASE_HOST = "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1"
BEFORE_URL = f"{BASE_HOST}/{BEFORE_UR}/{BEFORE_UR}.h5"
AFTER_URL  = f"{BASE_HOST}/{AFTER_UR}/{AFTER_UR}.h5"

# AOI
AOI_LON_MIN, AOI_LON_MAX = -91.75, -91.55
AOI_LAT_MIN, AOI_LAT_MAX = 30.25, 30.43
GCOV_X_LEFT = 365045.0
GCOV_Y_TOP  = 3567595.0
GCOV_DX, GCOV_DY = 10.0, -10.0
DS_PATH = "science/LSAR/GCOV/grids/frequencyA/HHHH"

SPECKLE_BOX_PX  = 5
VALID_FRAC_GATE = 0.85
MORPH_OPEN_PX   = 3
MIN_AREA_KM2    = 0.05

def pixel_area_km2(): return (abs(GCOV_DX) * abs(GCOV_DY)) / 1e6

def open_remote_h5(url, session):
    fs = fsspec.filesystem("http", client_kwargs={"headers": session.headers}, cookies=session.cookies)
    f  = fs.open(url, "rb", cache_type="blockcache", block_size=4*1024*1024)
    return h5py.File(f, "r")

def aoi_pixel_slice():
    tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32615", always_xy=True)
    x_min, y_min = tr.transform(AOI_LON_MIN, AOI_LAT_MIN)
    x_max, y_max = tr.transform(AOI_LON_MAX, AOI_LAT_MAX)
    col_min = int(round((x_min - GCOV_X_LEFT) / GCOV_DX))
    col_max = int(round((x_max - GCOV_X_LEFT) / GCOV_DX))
    row_min = int(round((GCOV_Y_TOP - y_max) / abs(GCOV_DY)))
    row_max = int(round((GCOV_Y_TOP - y_min) / abs(GCOV_DY)))
    return row_min, row_max, col_min, col_max

def read_aoi_slice(h5f, row_min, row_max, col_min, col_max):
    ds   = h5f[DS_PATH]
    data = ds[row_min:row_max, col_min:col_max].astype(np.float32)
    data[data <= 0] = np.nan
    return data

def quality_gate(arr, name):
    frac = float(np.sum(~np.isnan(arr))) / arr.size
    log.info("%s valid pixel fraction: %.3f", name, frac)
    if frac < VALID_FRAC_GATE:
        raise RuntimeError(f"Quality gate failed for {name}: {frac:.3f} < {VALID_FRAC_GATE}")
    return frac

def box_filter_power(arr, half_w):
    sz     = 2 * half_w + 1
    filled = np.where(np.isnan(arr), 0.0, arr)
    mask   = (~np.isnan(arr)).astype(np.float32)
    sum_p  = ndimage.uniform_filter(filled, size=sz, mode="nearest")
    cnt_p  = ndimage.uniform_filter(mask,   size=sz, mode="nearest")
    out    = np.full_like(arr, np.nan)
    v      = cnt_p > 0
    out[v] = sum_p[v] / cnt_p[v]
    return out

def power_to_db(arr):
    out   = np.full_like(arr, np.nan)
    valid = (arr > 0) & ~np.isnan(arr)
    out[valid] = 10.0 * np.log10(arr[valid])
    return out

def percentile_stretch(arr, lo=2, hi=98):
    valid = arr[~np.isnan(arr)]
    if valid.size == 0: return np.zeros_like(arr, dtype=np.uint8)
    vmin, vmax = float(np.percentile(valid, lo)), float(np.percentile(valid, hi))
    clipped = np.clip(arr, vmin, vmax)
    scaled  = (clipped - vmin) / (vmax - vmin + 1e-12) * 255.0
    scaled[np.isnan(arr)] = 0
    return scaled.astype(np.uint8)

def diverging_colormap(diff, vmin=-8.0, vmax=8.0):
    norm = np.clip((diff - vmin) / (vmax - vmin), 0.0, 1.0)
    norm[np.isnan(diff)] = 0.5
    h, w  = diff.shape
    rgb   = np.zeros((h, w, 3), dtype=np.uint8)
    below = norm < 0.5
    above = ~below
    t_b   = norm[below] * 2.0
    t_a   = (norm[above] - 0.5) * 2.0
    rgb[below, 0] = (t_b * 255).astype(np.uint8)
    rgb[below, 1] = (t_b * 255).astype(np.uint8)
    rgb[below, 2] = 255
    rgb[above, 0] = 255
    rgb[above, 1] = ((1.0 - t_a) * 255).astype(np.uint8)
    rgb[above, 2] = ((1.0 - t_a) * 255).astype(np.uint8)
    return rgb

def compute_histogram(arr, bins=50, rng=(-25, 5)):
    valid  = arr[~np.isnan(arr)].ravel()
    counts, edges = np.histogram(valid, bins=bins, range=rng)
    centres = ((edges[:-1] + edges[1:]) / 2.0).tolist()
    return centres, counts.tolist()

def polygonize_mask(mask, row_min, col_min, min_area_km2=MIN_AREA_KM2):
    """Polygonize retained change components using their true pixel outlines."""
    labeled, n = ndimage.label(mask.astype(bool))
    log.info("Connected components: %d", n)
    px_km2 = pixel_area_km2()
    # GCOV_X_LEFT / GCOV_Y_TOP are treated as pixel-centre coordinates in this
    # frozen showcase, so shift half a pixel to build a raster corner transform.
    transform = Affine(
        GCOV_DX, 0.0, GCOV_X_LEFT + (col_min - 0.5) * GCOV_DX,
        0.0, GCOV_DY, GCOV_Y_TOP + (row_min - 0.5) * GCOV_DY,
    )
    features = []
    for lid in range(1, n + 1):
        comp = labeled == lid
        pixel_count = int(np.sum(comp))
        area_km2 = pixel_count * px_km2
        if area_km2 < min_area_km2:
            continue
        comp_u8 = comp.astype(np.uint8)
        for geom, value in raster_shapes(comp_u8, mask=comp, transform=transform, connectivity=4):
            if int(value) != 1:
                continue
            lonlat_geom = transform_geom("EPSG:32615", "EPSG:4326", geom, precision=7)
            features.append({
                "type": "Feature",
                "geometry": lonlat_geom,
                "properties": {
                    "area_km2": round(area_km2, 4),
                    "pixel_count": pixel_count,
                    "label_id": lid,
                },
            })
    features.sort(key=lambda f: f["properties"]["area_km2"], reverse=True)
    log.info("Retained %d polygon features", len(features))
    return features


def fetch_dswx_reference(session, bbox):
    log.info("Searching OPERA DSWx-HLS reference granule (Jul 6-8, 2026)...")
    try:
        results = earthaccess.search_data(
            short_name="OPERA_L3_DSWX-HLS_V1",
            bounding_box=tuple(bbox),
            temporal=("2026-07-06", "2026-07-08"),
            count=10)
        log.info("CMR DSWx-HLS results: %d", len(results))
        granule = next((r for r in results if "_L9_" in r.get("umm", {}).get("GranuleUR", "")), None)
        if not granule and results: granule = results[0]
        if not granule: return None, 0.0, "unavailable"
        ur   = granule.get("umm", {}).get("GranuleUR", "unknown")
        links = granule.data_links()
        wtr_links = [l for l in links if "_B01_WTR" in l]
        log.info("Using granule: %s  WTR links: %d", ur, len(wtr_links))
        if not wtr_links: return None, 0.0, ur
        resp = session.get(wtr_links[0], timeout=60)
        if resp.status_code != 200:
            log.warning("WTR download HTTP %d", resp.status_code)
            return None, 0.0, ur
        log.info("WTR band downloaded: %.1f KB", len(resp.content) / 1024)
        try:
            img     = Image.open(io.BytesIO(resp.content))
            wtr_arr = np.array(img)
            valid   = ~np.isin(wtr_arr, [252, 253, 254, 255])
            frac    = float(valid.sum()) / wtr_arr.size
            water   = np.isin(wtr_arr, [1, 2]).astype(np.uint8)
            log.info("DSWx valid frac: %.3f, water px: %d", frac, water.sum())
            return water, frac, ur
        except Exception as ex:
            log.warning("PIL cannot parse WTR TIFF: %s", ex)
            return None, 0.0, ur
    except Exception as ex:
        log.warning("DSWx acquisition failed: %s", ex)
        return None, 0.0, "unavailable"

def run_pipeline():
    log.info("=" * 60)
    log.info("NISAR Real Flood Showcase Pipeline — Step 12")
    log.info("=" * 60)

    # 1. Auth
    log.info("[1/12] Earthdata authentication...")
    # Supports environment variables (EARTHDATA_USERNAME / EARTHDATA_PASSWORD),
    # ~/.netrc, or interactive login
    try:
        auth = earthaccess.login(persist=False)
    except Exception:
        auth = earthaccess.login(strategy="netrc", persist=False)
    if not (auth and auth.authenticated):
        raise RuntimeError(
            "Earthdata authentication required for raw HDF5 granule streaming. "
            "Provide EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env or configure ~/.netrc."
        )
    session = auth.get_session()

    # 2. AOI slice
    log.info("[2/12] Computing AOI pixel slice...")
    row_min, row_max, col_min, col_max = aoi_pixel_slice()
    log.info("  Rows [%d:%d] Cols [%d:%d] → %.1f x %.1f km",
             row_min, row_max, col_min, col_max,
             (col_max-col_min)*abs(GCOV_DX)/1000, (row_max-row_min)*abs(GCOV_DY)/1000)

    # 3. BEFORE granule
    log.info("[3/12] Streaming BEFORE granule (Jun 28, 2026)...")
    hf = open_remote_h5(BEFORE_URL, session)
    before_raw = read_aoi_slice(hf, row_min, row_max, col_min, col_max)
    hf.close()
    log.info("  BEFORE shape=%s  nan=%d", before_raw.shape, int(np.isnan(before_raw).sum()))

    # 4. AFTER granule
    log.info("[4/12] Streaming AFTER granule (Jul 10, 2026)...")
    hf = open_remote_h5(AFTER_URL, session)
    after_raw = read_aoi_slice(hf, row_min, row_max, col_min, col_max)
    hf.close()
    log.info("  AFTER shape=%s  nan=%d", after_raw.shape, int(np.isnan(after_raw).sum()))

    # 5. Quality gate
    log.info("[5/12] Quality gate (%.0f%%)...", VALID_FRAC_GATE*100)
    bvf = quality_gate(before_raw, "BEFORE")
    avf = quality_gate(after_raw,  "AFTER")

    # 6. Speckle filter (linear power)
    log.info("[6/12] Box speckle filter %dx%d (linear power)...", 2*SPECKLE_BOX_PX+1, 2*SPECKLE_BOX_PX+1)
    before_filt = box_filter_power(before_raw, SPECKLE_BOX_PX)
    after_filt  = box_filter_power(after_raw,  SPECKLE_BOX_PX)

    # 7. Convert to dB
    log.info("[7/12] Converting to dB...")
    before_db = power_to_db(before_filt)
    after_db  = power_to_db(after_filt)
    log.info("  BEFORE dB mean=%.2f std=%.2f", float(np.nanmean(before_db)), float(np.nanstd(before_db)))
    log.info("  AFTER  dB mean=%.2f std=%.2f", float(np.nanmean(after_db)),  float(np.nanstd(after_db)))

    # 8. Difference
    log.info("[8/12] Difference raster (after - before)...")
    diff_db = after_db - before_db
    log.info("  Diff mean=%.3f std=%.3f min=%.2f max=%.2f",
             float(np.nanmean(diff_db)), float(np.nanstd(diff_db)),
             float(np.nanmin(diff_db)), float(np.nanmax(diff_db)))

    # 9. DSWx reference
    log.info("[9/12] DSWx-HLS reference acquisition...")
    bbox = (AOI_LON_MIN, AOI_LAT_MIN, AOI_LON_MAX, AOI_LAT_MAX)
    dswx_water, dswx_frac, dswx_ur = fetch_dswx_reference(session, bbox)

    # 10. Threshold calibration (empirical: 1.5 std below median, capped)
    log.info("[10/12] Threshold calibration and masking...")
    diff_valid = diff_db[~np.isnan(diff_db)].ravel()
    p2, p16, p50, p84, p98 = np.percentile(diff_valid, [2, 16, 50, 84, 98])
    log.info("  P2=%.2f P16=%.2f P50=%.2f P84=%.2f P98=%.2f dB", p2, p16, p50, p84, p98)
    std_diff     = float(np.nanstd(diff_db))
    threshold_db = float(p50) - 1.5 * std_diff
    threshold_db = max(-6.0, min(-2.0, threshold_db))
    log.info("  Threshold: %.3f dB", threshold_db)

    candidate = (diff_db < threshold_db).astype(np.uint8)
    candidate[np.isnan(before_db) | np.isnan(after_db)] = 0
    struct   = ndimage.generate_binary_structure(2, 1)
    struct   = ndimage.iterate_structure(struct, MORPH_OPEN_PX)
    opened   = ndimage.binary_opening(candidate, structure=struct).astype(np.uint8)
    wg_px    = int(np.sum(opened))
    wg_area  = wg_px * pixel_area_km2()
    log.info("  Candidate backscatter-decrease pixels: %d  area: %.2f km²", wg_px, wg_area)

    # 11. Metrics
    log.info("[11/12] Metrics (DSWx reference is context only; spatial comparison not implemented)...")
    metrics_source = "not_independently_validated"

    # 12. Polygonize
    log.info("[12/12] Polygonizing...")
    features  = polygonize_mask(opened, row_min, col_min)
    total_area = sum(f["properties"]["area_km2"] for f in features)

    # ── Outputs ──────────────────────────────────────────────────
    log.info("Saving products...")
    before_u8 = percentile_stretch(before_db)
    after_u8  = percentile_stretch(after_db)

    p_before   = STATIC_REAL / "before_db_preview.png"
    p_after    = STATIC_REAL / "after_db_preview.png"
    p_diff     = STATIC_REAL / "diff_db_colormap.png"
    p_mask     = STATIC_REAL / "change_mask_overlay.png"
    p_comp     = STATIC_REAL / "before_with_change_overlay.png"
    p_geojson  = PROCESSED   / "water_change_polygons.geojson"
    p_manifest = PROCESSED   / "manifest_real_flood_001.json"

    Image.fromarray(before_u8, "L").convert("RGB").save(p_before, "PNG"); log.info("Saved %s", p_before)
    Image.fromarray(after_u8,  "L").convert("RGB").save(p_after,  "PNG"); log.info("Saved %s", p_after)

    diff_rgb = diverging_colormap(diff_db)
    Image.fromarray(diff_rgb, "RGB").save(p_diff, "PNG"); log.info("Saved %s", p_diff)

    mask_rgba = np.zeros((*opened.shape, 4), dtype=np.uint8)
    mask_rgba[opened == 1] = [30, 160, 220, 200]
    mask_img  = Image.fromarray(mask_rgba, "RGBA")
    mask_img.save(p_mask, "PNG"); log.info("Saved %s", p_mask)

    base_rgba = Image.fromarray(before_u8, "L").convert("RGB").convert("RGBA")
    base_rgba.alpha_composite(mask_img)
    base_rgba.convert("RGB").save(p_comp, "PNG"); log.info("Saved %s", p_comp)

    bh_c, bh_n = compute_histogram(before_db, rng=(-25, 5))
    ah_c, ah_n = compute_histogram(after_db,  rng=(-25, 5))
    dh_c, dh_n = compute_histogram(diff_db,   rng=(-15, 10))

    geojson = {"type": "FeatureCollection", "features": features,
               "metadata": {"source": "NISAR LSAR GCOV PROVISIONAL",
                             "before_granule": BEFORE_UR, "after_granule": AFTER_UR,
                             "threshold_db": round(threshold_db, 3),
                             "total_area_km2": round(total_area, 3)}}
    p_geojson.write_text(json.dumps(geojson, indent=2)); log.info("Saved %s", p_geojson)

    manifest = {
        "showcase_id": "real_flood_001", "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aoi": {"name": "Atchafalaya Basin / Henderson Lake, Louisiana",
                "lon_min": AOI_LON_MIN, "lon_max": AOI_LON_MAX,
                "lat_min": AOI_LAT_MIN, "lat_max": AOI_LAT_MAX,
                "width_km":  round((col_max-col_min)*abs(GCOV_DX)/1000, 2),
                "height_km": round((row_max-row_min)*abs(GCOV_DY)/1000, 2)},
        "granules": {"before": {"granule_ur": BEFORE_UR, "date": "2026-06-28", "url": BEFORE_URL},
                     "after":  {"granule_ur": AFTER_UR,  "date": "2026-07-10", "url": AFTER_URL}},
        "reference": {"collection": "OPERA_L3_DSWX-HLS_V1", "granule_ur": dswx_ur,
                      "date": "2026-07-07", "cloud_cover_pct": 37,
                      "source": "NASA PO.DAAC via Earthdata CMR"},
        "processing": {"dataset_path": DS_PATH, "projection": "EPSG:32615 (UTM 15N)",
                       "pixel_spacing_m": 10,
                       "speckle_filter": f"{2*SPECKLE_BOX_PX+1}x{2*SPECKLE_BOX_PX+1} box (linear power)",
                       "threshold_db": round(threshold_db, 3),
                       "morph_open_px": MORPH_OPEN_PX, "min_area_km2": MIN_AREA_KM2},
        "quality": {"before_valid_frac": round(bvf, 4), "after_valid_frac": round(avf, 4),
                    "quality_gate_threshold": VALID_FRAC_GATE},
        "results": {"water_gain_area_km2": round(wg_area, 3), "candidate_radar_change_area_km2": round(wg_area, 3), "polygon_count": len(features),
                    "polygon_total_area_km2": round(total_area, 3),
                    "metrics_source": metrics_source,
                    "iou": None, "precision": None, "recall": None, "f1": None},
        "outputs": {"before_png": str(p_before.relative_to(ROOT)),
                    "after_png":  str(p_after.relative_to(ROOT)),
                    "diff_png":   str(p_diff.relative_to(ROOT)),
                    "mask_png":   str(p_mask.relative_to(ROOT)),
                    "composite_png": str(p_comp.relative_to(ROOT)),
                    "geojson": str(p_geojson.relative_to(ROOT))},
        "histograms": {"before_db": {"centres": bh_c, "counts": bh_n, "units": "dB"},
                       "after_db":  {"centres": ah_c, "counts": ah_n, "units": "dB"},
                       "diff_db":   {"centres": dh_c, "counts": dh_n, "units": "dB"}},
    }
    p_manifest.write_text(json.dumps(manifest, indent=2)); log.info("Saved %s", p_manifest)

    log.info("")
    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("  Candidate radar-change area: %.3f km²", wg_area)
    log.info("  Polygon features: %d", len(features))
    log.info("  Threshold:        %.3f dB", threshold_db)
    log.info("  Before valid:     %.1f%%  After valid: %.1f%%", bvf*100, avf*100)
    log.info("=" * 60)
    return manifest

if __name__ == "__main__":
    try:
        run_pipeline(); sys.exit(0)
    except Exception as exc:
        log.exception("Pipeline failed: %s", exc); sys.exit(1)
