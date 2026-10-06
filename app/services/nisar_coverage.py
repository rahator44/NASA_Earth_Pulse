"""
NISAR Coverage Service
Performs real metadata discovery against the Alaska Satellite Facility (ASF) DAAC.
Searches metadata only — no raw data downloads or scientific radar processing.
"""
import concurrent.futures
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from shapely.geometry import shape
from shapely import to_wkt

try:
    import asf_search as asf
    ASF_SEARCH_AVAILABLE = True
except ImportError:  # Keep the demo app bootable when optional live-search dependency is absent.
    asf = None
    ASF_SEARCH_AVAILABLE = False

from app.models.coverage import (
    CompatiblePairCandidate,
    CoverageAcquisition,
    CoverageProductSummary,
    CoverageSearchRequest,
    CoverageSearchResponse,
    CoverageSearchStatus,
    MaturityProductSummary,
    ModuleAvailability,
    NinePointChecks,
    PairCompatibilityStatus,
)

logger = logging.getLogger("nisar.coverage")

# Configuration constants
NISAR_PROVISIONAL_START_DATE = "2026-06-17"
DEFAULT_PRODUCTS = ["GCOV", "GUNW", "GOFF"]
MAX_SEARCH_RESULTS_PER_PRODUCT = 50
MAX_AOI_SPAN_DEGREES = 5.0
CACHE_TTL_SECONDS = 900  # 15 minutes
SEARCH_TIMEOUT_SECONDS = 60  # Bounded execution for parallel product searches (1 minute)


class NisarCoverageService:
    def __init__(self, search_client: Optional[Callable[..., Any]] = None):
        # Allow injecting a custom/mock client for unit tests.  If asf_search is
        # unavailable, keep the application bootable and fail live searches
        # explicitly instead of crashing every page at import time.
        if search_client is not None:
            self.search_client = search_client
        elif ASF_SEARCH_AVAILABLE:
            self.search_client = asf.search
        else:
            self.search_client = self._missing_asf_search
        self._cache: dict[str, tuple[float, CoverageSearchResponse]] = {}
        self.last_successful_query: Optional[str] = None

    @staticmethod
    def _missing_asf_search(**kwargs):
        raise RuntimeError("Live NISAR coverage search is unavailable because the asf_search package is not installed.")

    def get_status(self) -> dict[str, Any]:
        """Returns lightweight service status without invoking external network requests."""
        return {
            "configured": True,
            "asf_search_installed": ASF_SEARCH_AVAILABLE,
            "asf_version": getattr(asf, "__version__", "not-installed") if asf is not None else "not-installed",
            "cache_entries": len(self._cache),
            "provisional_start_date": NISAR_PROVISIONAL_START_DATE,
            "last_successful_query": self.last_successful_query,
        }

    def _build_cache_key(
        self,
        wkt: str,
        products: list[str],
        maturity: Optional[str],
        start_date: str,
        end_date: Optional[str]
    ) -> str:
        raw_key = f"{wkt}|{','.join(sorted(products))}|{maturity or 'ALL'}|{start_date}|{end_date or 'NOW'}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _convert_geometry_to_wkt(self, geometry_dict: dict[str, Any]) -> tuple[Optional[str], Optional[CoverageSearchStatus], Optional[str]]:
        """
        Validates GeoJSON geometry and converts to WKT for asf_search.
        Checks maximum allowable search bounds for demo query safety.
        """
        if not geometry_dict or not isinstance(geometry_dict, dict):
            return None, CoverageSearchStatus.INVALID_REQUEST, "Missing or invalid GeoJSON geometry."

        geom_type = geometry_dict.get("type")
        coords = geometry_dict.get("coordinates")
        if not geom_type or coords is None:
            return None, CoverageSearchStatus.INVALID_REQUEST, "Invalid GeoJSON structure."

        try:
            geom = shape(geometry_dict)
            if not geom.is_valid:
                from shapely import make_valid
                geom = make_valid(geom)
                if not geom.is_valid:
                    return None, CoverageSearchStatus.INVALID_REQUEST, "Geometry is invalid and cannot be repaired."

            minx, miny, maxx, maxy = geom.bounds
            span_x = abs(maxx - minx)
            span_y = abs(maxy - miny)

            # Prevent world-scale or massive queries
            if span_x > MAX_AOI_SPAN_DEGREES or span_y > MAX_AOI_SPAN_DEGREES:
                return None, CoverageSearchStatus.SEARCH_AREA_TOO_LARGE, (
                    f"Search area exceeds allowable size ({span_x:.2f}° x {span_y:.2f}° > {MAX_AOI_SPAN_DEGREES}° limit). "
                    "Select a smaller area for NISAR acquisition discovery."
                )

            if geom.geom_type == "Point":
                wkt_str = f"POINT({geom.x:.5f} {geom.y:.5f})"
            else:
                if len(getattr(geom, "exterior", geom).coords) > 60:
                    geom = geom.simplify(0.001, preserve_topology=True)
                wkt_str = to_wkt(geom)

            return wkt_str, None, None

        except Exception as e:
            return None, CoverageSearchStatus.INVALID_REQUEST, f"Geometry parsing error: {e}"

    def _execute_query(self, **kwargs) -> list[Any]:
        """Direct call to search client."""
        return list(self.search_client(**kwargs))

    def _normalize_product(self, raw_item: Any, product_type: str, maturity: str) -> CoverageAcquisition:
        """Normalizes raw ASF metadata properties into a clean Pydantic CoverageAcquisition."""
        props = getattr(raw_item, "properties", {})
        geom = getattr(raw_item, "geometry", None)

        # Granule identifier
        granule_id = (
            props.get("sceneName") or
            props.get("fileID") or
            getattr(raw_item, "sceneName", None) or
            "UNKNOWN_GRANULE"
        )

        # Track and Frame
        track = props.get("pathNumber")
        frame = props.get("frameNumber")
        if track is not None:
            try:
                track = int(track)
            except (ValueError, TypeError):
                track = None
        if frame is not None:
            try:
                frame = int(frame)
            except (ValueError, TypeError):
                frame = None

        # Polarizations
        pols: list[str] = []
        raw_pol = props.get("polarization")
        if isinstance(raw_pol, list):
            pols.extend([str(p) for p in raw_pol if p])
        elif isinstance(raw_pol, str) and raw_pol.strip():
            pols.append(raw_pol.strip())

        side_pols = props.get("sideBandPolarization")
        if isinstance(side_pols, list):
            for sp in side_pols:
                if sp and str(sp) not in pols:
                    pols.append(str(sp))

        main_pols = props.get("mainBandPolarization")
        if isinstance(main_pols, list):
            for mp in main_pols:
                if mp and str(mp) not in pols:
                    pols.append(str(mp))

        # Bandwidth
        bandwidth_raw = props.get("rangeBandwidth")
        bandwidth_str = None
        if isinstance(bandwidth_raw, list) and bandwidth_raw:
            clean_bw = [str(v) for v in bandwidth_raw if v is not None]
            bandwidth_str = f"{'+'.join(clean_bw)} MHz" if clean_bw else None
        elif bandwidth_raw is not None:
            bandwidth_str = f"{bandwidth_raw} MHz"

        # Frequency / Sensor
        sensor = props.get("sensor") or "L-SAR"

        # Mode fallback from the documented NISAR naming convention:
        # token 8 is the 4-character bandwidth mode (e.g. 4005 = 40 MHz
        # primary + 5 MHz secondary), while token 9 is the polarization mode
        # (e.g. DHDH = HH/HV dual-pol on both bands).  These are distinct.
        beam_mode = props.get("beamModeType")
        if granule_id and "_" in granule_id:
            tokens = granule_id.split("_")
            if not beam_mode and len(tokens) >= 10 and len(tokens[8]) == 4 and tokens[8].isdigit():
                beam_mode = f"{tokens[8]} (bandwidth mode from granule ID)"
            if not pols and len(tokens) >= 10 and len(tokens[9]) == 4 and tokens[9].isalpha():
                pol_mode_code = tokens[9].upper()
                pol_map = {
                    "DH": ["HH", "HV"], "DV": ["VV", "VH"],
                    "SH": ["HH"], "SV": ["VV"],
                    "QP": ["HH", "HV", "VV", "VH"],
                    "CL": ["LH", "LV"], "CR": ["RH", "RV"], "NA": [],
                }
                for half in (pol_mode_code[:2], pol_mode_code[2:]):
                    for pol in pol_map.get(half, []):
                        if pol not in pols:
                            pols.append(pol)

        return CoverageAcquisition(
            id=granule_id,
            product_type=product_type,
            acquisition_datetime=props.get("startTime"),
            start_time=props.get("startTime"),
            stop_time=props.get("stopTime"),
            track=track,
            frame=frame,
            orbit_direction=props.get("flightDirection"),
            polarizations=pols,
            beam_mode=beam_mode,
            frequency=sensor,
            bandwidth=bandwidth_str,
            data_maturity=maturity,
            processing_version=props.get("pgeVersion"),
            crid=props.get("crid"),
            geometry=geom,
            metadata_url=props.get("url"),
            download_url=props.get("url"),
            source="NASA NISAR / ASF DAAC",
            data_origin="live_metadata"
        )

    def _derive_module_availability(self, products: dict[str, CoverageProductSummary]) -> ModuleAvailability:
        """
        Derives DATA AVAILABILITY only — NOT physical change detection.
        - Vegetation Disturbance: requires suitable GCOV coverage
        - Flood / Wetland: requires suitable GCOV coverage
        - Glacier: requires GOFF coverage
        - Ground Deformation: requires GUNW coverage
        """
        has_gcov = products.get("GCOV", CoverageProductSummary()).total_count > 0
        has_gunw = products.get("GUNW", CoverageProductSummary()).total_count > 0
        has_goff = products.get("GOFF", CoverageProductSummary()).total_count > 0

        return ModuleAvailability(
            vegetation_disturbance="DATA AVAILABLE" if has_gcov else "PRODUCT NOT FOUND",
            flood_wetland="DATA AVAILABLE" if has_gcov else "PRODUCT NOT FOUND",
            glacier="DATA AVAILABLE" if has_goff else "PRODUCT NOT FOUND",
            deformation="DATA AVAILABLE" if has_gunw else "PRODUCT NOT FOUND",
        )

    def _evaluate_gcov_pair(self, before: CoverageAcquisition, after: CoverageAcquisition) -> CompatiblePairCandidate:
        """
        Evaluates candidate GCOV comparison pairs under the nine-point compatibility check.
        Ensures incomplete metadata cannot produce a false COMPATIBLE claim.
        """
        checks_dict: dict[str, str] = {}

        # 1. Track
        if before.track is not None and after.track is not None:
            same_track = (before.track == after.track)
            checks_dict["track"] = f"{before.track} vs {after.track}"
        else:
            same_track = None
            checks_dict["track"] = "Unknown"

        # 2. Frame
        if before.frame is not None and after.frame is not None:
            same_frame = (before.frame == after.frame)
            checks_dict["frame"] = f"{before.frame} vs {after.frame}"
        else:
            same_frame = None
            checks_dict["frame"] = "Unknown"

        # 3. Orbit direction
        if before.orbit_direction and after.orbit_direction:
            same_direction = (before.orbit_direction.upper() == after.orbit_direction.upper())
            checks_dict["direction"] = f"{before.orbit_direction} vs {after.orbit_direction}"
        else:
            same_direction = None
            checks_dict["direction"] = "Unknown"

        # 4. Beam / Observation mode
        if before.beam_mode and after.beam_mode:
            compatible_mode = (before.beam_mode == after.beam_mode)
            checks_dict["mode"] = f"{before.beam_mode} vs {after.beam_mode}"
        else:
            compatible_mode = None
            checks_dict["mode"] = "Unknown"

        # 5. Polarization
        if before.polarizations and after.polarizations:
            common_pols = set(before.polarizations) & set(after.polarizations)
            compatible_pol = len(common_pols) > 0
            checks_dict["polarization"] = f"Common: {list(common_pols)}" if compatible_pol else "No common polarizations"
        else:
            compatible_pol = None
            checks_dict["polarization"] = "Unknown"

        # 6. Frequency / Sensor
        if before.frequency and after.frequency:
            compatible_freq = (before.frequency == after.frequency)
            checks_dict["frequency"] = f"{before.frequency} vs {after.frequency}"
        else:
            compatible_freq = None
            checks_dict["frequency"] = "Unknown"

        # 7. Bandwidth
        if before.bandwidth and after.bandwidth:
            compatible_bw = (before.bandwidth == after.bandwidth)
            checks_dict["bandwidth"] = f"{before.bandwidth} vs {after.bandwidth}"
        else:
            compatible_bw = None
            checks_dict["bandwidth"] = "Unknown"

        # 8. Maturity (must be same maturity by default policy)
        same_maturity = (before.data_maturity == after.data_maturity)
        checks_dict["maturity"] = f"{before.data_maturity} vs {after.data_maturity}"

        # 9. Processing version / CRID
        if before.crid and after.crid:
            compatible_version = (before.crid == after.crid)
            checks_dict["version"] = f"CRID {before.crid} vs {after.crid}"
        elif before.processing_version and after.processing_version:
            compatible_version = (before.processing_version == after.processing_version)
            checks_dict["version"] = f"PGE {before.processing_version} vs {after.processing_version}"
        else:
            compatible_version = None
            checks_dict["version"] = "Unknown"

        nine_checks = NinePointChecks(
            same_track=same_track,
            same_frame=same_frame,
            same_direction=same_direction,
            compatible_mode=compatible_mode,
            compatible_polarization=compatible_pol,
            compatible_frequency=compatible_freq,
            compatible_bandwidth=compatible_bw,
            same_maturity=same_maturity,
            compatible_processing_version=compatible_version,
            details=checks_dict
        )

        all_checks = [
            same_track, same_frame, same_direction, compatible_mode,
            compatible_pol, compatible_freq, compatible_bw, same_maturity, compatible_version
        ]

        if any(c is False for c in all_checks):
            status = PairCompatibilityStatus.INCOMPATIBLE
            notes = "Physical or radar acquisition parameters conflict."
        elif any(c is None for c in [same_track, same_frame, same_direction, compatible_mode, compatible_pol]):
            status = PairCompatibilityStatus.INSUFFICIENT_METADATA
            notes = "Key radar comparison metadata missing from archive catalog."
        else:
            status = PairCompatibilityStatus.COMPATIBLE
            notes = "Candidate pair satisfies geometric and radiometric comparison criteria."

        temporal_days = None
        if before.start_time and after.start_time:
            try:
                dt_b = datetime.fromisoformat(before.start_time.replace("Z", "+00:00"))
                dt_a = datetime.fromisoformat(after.start_time.replace("Z", "+00:00"))
                temporal_days = abs((dt_a - dt_b).days)
            except Exception:
                pass

        return CompatiblePairCandidate(
            before_id=before.id,
            after_id=after.id,
            before_date=before.start_time,
            after_date=after.start_time,
            temporal_baseline_days=temporal_days,
            compatibility_status=status,
            checks=nine_checks,
            comparison_policy="nearest_previous",
            notes=notes
        )

    def _generate_gcov_pair_candidates(self, gcov_summary: CoverageProductSummary) -> list[CompatiblePairCandidate]:
        """
        Identifies candidate before/after comparison pairs for GCOV.
        Prefers PROVISIONAL <-> PROVISIONAL pairs. Never automatically pairs BETA with PROVISIONAL.
        Groups by track and frame when possible to find genuine repeat-pass pairs.
        """
        candidates: list[CompatiblePairCandidate] = []

        for maturity_summary in [gcov_summary.provisional, gcov_summary.beta]:
            acqs = [a for a in maturity_summary.acquisitions if a.start_time]
            if len(acqs) < 2:
                continue

            # First attempt: find genuine repeat-pass pairs with identical (track, frame)
            by_tf: dict[tuple[Any, Any], list[CoverageAcquisition]] = {}
            for a in acqs:
                if a.track is not None and a.frame is not None:
                    by_tf.setdefault((a.track, a.frame), []).append(a)

            repeat_pairs_found = False
            for (t, f), tf_acqs in by_tf.items():
                if len(tf_acqs) >= 2:
                    tf_acqs.sort(key=lambda a: a.start_time or "")
                    for i in range(1, len(tf_acqs)):
                        after_acq = tf_acqs[i]
                        before_acq = tf_acqs[i - 1]
                        pair = self._evaluate_gcov_pair(before_acq, after_acq)
                        candidates.append(pair)
                        repeat_pairs_found = True
                        if len(candidates) >= 10:
                            break
                if len(candidates) >= 10:
                    break

            # Fallback if no repeat-pass pairs on identical track/frame: chronological adjacent
            if not repeat_pairs_found:
                acqs.sort(key=lambda a: a.start_time or "")
                for i in range(1, len(acqs)):
                    after_acq = acqs[i]
                    before_acq = acqs[i - 1]
                    pair = self._evaluate_gcov_pair(before_acq, after_acq)
                    candidates.append(pair)
                    if len(candidates) >= 10:
                        break

        return candidates

    def search_coverage(self, request: CoverageSearchRequest) -> CoverageSearchResponse:
        """
        Executes live metadata search across GCOV, GUNW, and GOFF products.
        Caches repeated queries and handles errors/timeouts gracefully.
        """
        logger.info("Initiating coverage search for products: %s", request.requested_products)

        # 1. Convert AOI to WKT and validate boundaries
        wkt_str, err_status, err_msg = self._convert_geometry_to_wkt(request.geometry)
        if err_status:
            return CoverageSearchResponse(
                search_status=err_status,
                searched_at=datetime.now(timezone.utc).isoformat(),
                error_message=err_msg
            )

        start_date = (request.date_range or {}).get("start", NISAR_PROVISIONAL_START_DATE)
        end_date = (request.date_range or {}).get("end")

        # 2. Check in-process cache
        cache_key = self._build_cache_key(wkt_str, request.requested_products, request.maturity, start_date, end_date)
        cached_entry = self._cache.get(cache_key)
        if cached_entry:
            cached_time, cached_response = cached_entry
            if time.time() - cached_time < CACHE_TTL_SECONDS:
                logger.info("Returning cached coverage search result (key=%s)", cache_key[:8])
                return cached_response

        # 3. Query ASF in parallel by product and maturity
        products_to_query = [p for p in request.requested_products if p in DEFAULT_PRODUCTS]
        if not products_to_query:
            products_to_query = DEFAULT_PRODUCTS

        maturities_to_query = ["PROVISIONAL", "BETA"]
        if request.maturity:
            maturities_to_query = [request.maturity.upper()]

        # Prepare sub-tasks
        tasks: list[tuple[str, str, dict[str, Any]]] = []
        for prod in products_to_query:
            for mat in maturities_to_query:
                kwargs: dict[str, Any] = {
                    "dataset": "NISAR",
                    "processingLevel": prod,
                    "dataMaturity": mat,
                    "intersectsWith": wkt_str,
                    "start": start_date,
                    "maxResults": MAX_SEARCH_RESULTS_PER_PRODUCT + 1,
                }
                if end_date:
                    kwargs["end"] = end_date
                tasks.append((prod, mat, kwargs))

        products_result: dict[str, CoverageProductSummary] = {
            p: CoverageProductSummary() for p in products_to_query
        }
        total_found_across_all = 0
        is_truncated = False
        all_footprints: list[dict[str, Any]] = []
        search_warnings: list[str] = []
        failed_tasks: list[tuple[str, str, Exception]] = []
        timed_out_tasks: list[tuple[str, str]] = []

        try:
            # Parallel execution across worker threads
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks), 6)) as executor:
                future_to_task = {
                    executor.submit(self._execute_query, **kw): (p, m)
                    for p, m, kw in tasks
                }

                done, not_done = concurrent.futures.wait(
                    future_to_task.keys(),
                    timeout=SEARCH_TIMEOUT_SECONDS
                )

                for future in not_done:
                    prod, mat = future_to_task[future]
                    timed_out_tasks.append((prod, mat))
                    search_warnings.append(f"Archive query for {prod} ({mat}) timed out.")
                    logger.warning("ASF metadata search sub-query timed out for %s %s", prod, mat)
                    future.cancel()

                for future in done:
                    prod, mat = future_to_task[future]
                    try:
                        raw_items = future.result()
                    except Exception as sub_err:
                        failed_tasks.append((prod, mat, sub_err))
                        search_warnings.append(f"Archive query for {prod} ({mat}) failed: {sub_err}")
                        logger.warning("ASF metadata sub-query error for %s %s: %s", prod, mat, sub_err)
                        continue

                    if len(raw_items) > MAX_SEARCH_RESULTS_PER_PRODUCT:
                        is_truncated = True
                        raw_items = raw_items[:MAX_SEARCH_RESULTS_PER_PRODUCT]

                    normalized_acqs: list[CoverageAcquisition] = []
                    for item in raw_items:
                        acq = self._normalize_product(item, prod, mat)
                        normalized_acqs.append(acq)
                        if acq.geometry and len(all_footprints) < 20:
                            all_footprints.append({
                                "type": "Feature",
                                "id": acq.id,
                                "geometry": acq.geometry,
                                "properties": {
                                    "id": acq.id,
                                    "product_type": acq.product_type,
                                    "data_maturity": acq.data_maturity,
                                    "date": acq.start_time,
                                    "track": acq.track,
                                    "frame": acq.frame,
                                    "direction": acq.orbit_direction
                                }
                            })

                    latest_date = None
                    if normalized_acqs:
                        dates = [a.start_time for a in normalized_acqs if a.start_time]
                        if dates:
                            latest_date = max(dates)

                    mat_summary = MaturityProductSummary(
                        count=len(normalized_acqs),
                        latest_date=latest_date,
                        acquisitions=normalized_acqs
                    )

                    target_summary = products_result[prod]
                    if mat == "PROVISIONAL":
                        target_summary.provisional = mat_summary
                    else:
                        target_summary.beta = mat_summary

                    target_summary.total_count = target_summary.provisional.count + target_summary.beta.count

            # If every single task failed or timed out, report SERVICE_UNAVAILABLE
            if tasks and (len(failed_tasks) + len(timed_out_tasks) == len(tasks)):
                first_exc = failed_tasks[0][2] if failed_tasks else None
                err_desc = type(first_exc).__name__ if first_exc else "TimeoutError"
                return CoverageSearchResponse(
                    search_status=CoverageSearchStatus.SERVICE_UNAVAILABLE,
                    searched_at=datetime.now(timezone.utc).isoformat(),
                    error_message=f"The NISAR archive could not be queried at this time ({err_desc})."
                )

            total_found_across_all = sum(p.total_count for p in products_result.values())

        except Exception as e:
            logger.error("ASF metadata search failure: %s", e, exc_info=True)
            return CoverageSearchResponse(
                search_status=CoverageSearchStatus.SERVICE_UNAVAILABLE,
                searched_at=datetime.now(timezone.utc).isoformat(),
                error_message=f"The NISAR archive could not be queried at this time ({type(e).__name__})."
            )

        # 4. GCOV comparison pair discovery
        gcov_summary = products_result.get("GCOV", CoverageProductSummary())
        pair_candidates = self._generate_gcov_pair_candidates(gcov_summary)

        # 5. Derive module availability (data availability only)
        module_avail = self._derive_module_availability(products_result)

        # 6. Build Footprints GeoJSON FeatureCollection
        footprints_collection = None
        if all_footprints:
            footprints_collection = {
                "type": "FeatureCollection",
                "features": all_footprints
            }

        status = CoverageSearchStatus.AVAILABLE if total_found_across_all > 0 else CoverageSearchStatus.NO_RESULTS
        date_range_summary = f"{start_date} → {end_date or 'Present'}"

        warnings_to_return: list[str] = []
        if is_truncated:
            warnings_to_return.append("Results capped at 50 per product/maturity.")
        warnings_to_return.extend(search_warnings)

        response = CoverageSearchResponse(
            search_status=status,
            searched_at=datetime.now(timezone.utc).isoformat(),
            geometry_summary=f"WKT: {wkt_str[:40]}..." if len(wkt_str) > 40 else wkt_str,
            date_range_summary=date_range_summary,
            source="NASA NISAR / ASF DAAC",
            products=products_result,
            module_availability=module_avail,
            gcov_pair_candidates=pair_candidates,
            results_truncated=is_truncated,
            warnings=warnings_to_return,
            footprints_geojson=footprints_collection
        )

        # Cache result
        self._cache[cache_key] = (time.time(), response)
        self.last_successful_query = datetime.now(timezone.utc).isoformat()

        logger.info("Coverage search completed: status=%s, total=%d", status.value, total_found_across_all)
        return response


# Global singleton instance
coverage_service = NisarCoverageService()
