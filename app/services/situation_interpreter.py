"""Deterministic interpretation of stored, processed analyses."""
from datetime import datetime
from typing import Any, Iterable, Optional

from app.models.situation import (
    DecodedNISARMetadata,
    SituationEvidence,
    SituationInterpretation,
    SituationRecord,
)
from app.services.nisar_decoder import decode_nisar_metadata
from app.services.interpretation_rules import evidence_ids as build_evidence_ids, rule
from app.utils.situation_presentation import LIMITATIONS, STATE_WORDING, enum_value, format_measurement, public_quality


MEASUREMENTS = {
    # Legacy/synthetic keys remain readable, but real NISAR records use measurement-first names.
    "inundated_area_km2": ("Synthetic surface-water change area", "km²", "Area stored by a demonstration fixture."),
    "new_water_area_km2": ("Synthetic surface-water change area", "km²", "Area stored by a demonstration fixture."),
    "candidate_radar_change_area_km2": ("Candidate radar-change pixels", "km²", "Area of quality-screened pixels that met the radar-change threshold before minimum-region filtering."),
    "retained_mapped_region_area_km2": ("Retained mapped change regions", "km²", "Area remaining after removing connected components smaller than the configured minimum region size."),
    "removed_small_component_area_km2": ("Filtered small-component area", "km²", "Candidate area removed by the configured minimum connected-region size filter."),
    "change_criterion_db": ("Radar-change criterion", "dB", "Pixels more negative than this after-minus-before backscatter criterion entered the candidate mask."),
    "polygon_count": ("Retained mapped regions", "regions", "Number of connected change regions retained after minimum-size filtering."),
    "changed_area_km2": ("Measured radar-change area", "km²", "Area identified by the stored change analysis."),
    "anomaly_area_km2": ("Measured radar-anomaly area", "km²", "Area identified by the stored anomaly analysis."),
    "backscatter_reduction_mean_db": ("Legacy mean backscatter value", "dB", "Legacy demonstration field; prefer mean_backscatter_difference_db."),
    "mean_backscatter_difference_db": ("Mean backscatter difference (after − before)", "dB", "Signed mean change in radar backscatter; negative means the radar return decreased."),
    "los_displacement_mm": ("Line-of-sight displacement", "mm", "Relative displacement measured along the satellite line of sight."),
    "max_displacement_mm": ("Maximum relative displacement", "mm", "Maximum relative displacement recorded by the analysis."),
    "velocity_m_per_day": ("Surface velocity", "m/day", "Velocity recorded by the stored motion analysis."),
    "before_velocity_m_per_day": ("Before surface velocity", "m/day", "Velocity recorded in the before observation."),
    "after_velocity_m_per_day": ("After surface velocity", "m/day", "Velocity recorded in the after observation."),
    "mean_coherence": ("Mean interferometric coherence", None, "Consistency of the radar phase signal across repeat observations."),
    "coherence_loss": ("Coherence loss", None, "Change in radar phase consistency across repeat observations."),
}

WATER_DOMAINS = {"flood_wetland"}


def _firms_supported(manifest: Any) -> bool:
    if not manifest or not (manifest.matching_firms_detection_count or 0) > 0:
        return False
    if manifest.firms_time_buffer_hours is None or manifest.firms_spatial_buffer_m is None:
        return False
    distance = manifest.nearest_firms_distance_m
    return distance is None or distance <= manifest.firms_spatial_buffer_m


def _date_label(raw: str) -> str:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except (ValueError, TypeError):
        return raw


def _evidence(
    *, evidence_type: str, name: str, value: Any = None, unit: Optional[str] = None,
    direction: Optional[str] = None, quality_status: Optional[str] = None,
    quality_value: Any = None, public: str, scientist: Optional[str] = None,
    source: Optional[str] = None, support: str,
) -> SituationEvidence:
    return SituationEvidence(
        evidence_type=evidence_type, measurement_name=name, measurement_value=value,
        measurement_unit=unit, direction=direction, quality_status=quality_status,
        quality_value=quality_value, description_public=public,
        description_scientist=scientist, source=source, support_level=support,
    )


def _measurement_evidence(analysis: Any, source: str) -> list[SituationEvidence]:
    evidence = []
    for key, value in (analysis.measurements or {}).items():
        if key not in MEASUREMENTS or value is None:
            continue
        label, unit, description = MEASUREMENTS[key]
        direction = None
        if "backscatter" in key:
            if key == "mean_backscatter_difference_db":
                if float(value) == 0:
                    direction = "no net direction"
                else:
                    direction = "decrease" if float(value) < 0 else "increase"
                description = f"The stored signed after-minus-before measurement shows a radar backscatter {direction}."
            else:
                # Preserve legacy fixture readability without using its sign to drive physical interpretation.
                description = "A legacy demonstration backscatter field is stored; direction is not inferred from this key."
        evidence.append(_evidence(
            evidence_type="processed_nisar_measurement", name=label,
            value=value, unit=unit, direction=direction,
            public=f"{label}: {format_measurement(value, unit or '')}.",
            scientist=f"{key}={value}{(' ' + unit) if unit else ''}",
            source=source, support="direct_measurement",
        ))
    return evidence


def _candidate_evidence(candidates: Iterable[Any], manifest: Any) -> tuple[list[SituationEvidence], list[SituationEvidence], list[SituationEvidence], list[SituationEvidence]]:
    direct: list[SituationEvidence] = []
    supporting: list[SituationEvidence] = []
    context: list[SituationEvidence] = []
    contradicting: list[SituationEvidence] = []
    physical_labels = {
        "gamma0_backscatter_drop_db": ("Radar backscatter change", "dB"),
        "backscatter_drop_db": ("Radar backscatter change", "dB"),
        "copol_phase_shift_deg": ("Co-polarized radar phase shift", "degrees"),
        "cross_pol_coherence_loss": ("Cross-polarized radar coherence loss", None),
        "canopy_roughness_decrease": ("Canopy roughness decrease", None),
    }
    for candidate in candidates:
        for key, value in (candidate.physical_evidence or {}).items():
            if value is None:
                continue
            if any(term in key.lower() for term in ("threshold", "valid_pixel_fraction", "polarization", "frequency_grid")):
                continue
            label, unit = physical_labels.get(key, ("Stored candidate evidence", None))
            direct.append(_evidence(
                evidence_type="candidate_physical_evidence", name=label, value=value, unit=unit,
                public=(f"Stored candidate evidence: {label.lower()} ({format_measurement(value, unit or '')})."
                        if key in physical_labels else "Additional stored candidate evidence is available in Scientist Mode."),
                scientist=f"{key}={value}", source="Stored candidate evidence", support="direct_measurement",
            ))
        for key, value in (candidate.independent_evidence or {}).items():
            if value is None or value is False or value == 0:
                if "firms" in key.lower() or "thermal" in key.lower():
                    contradicting.append(_evidence(
                        evidence_type="independent_observation", name=key, value=value,
                        public="No matching active-fire or thermal detections were recorded in the stored evidence.",
                        scientist=f"{key}={value}", source="Stored independent-evidence record", support="contradicting",
                    ))
                continue
            is_context = isinstance(value, str) and any(term in (key + value).lower() for term in ("context", "opera_dswx"))
            target = context if is_context else supporting
            level = "contextual" if is_context else "independent_support"
            target.append(_evidence(
                evidence_type="contextual_observation" if is_context else "independent_observation",
                name=key, value=value,
                public=str(value) if isinstance(value, str) else f"Stored supporting observation: {key.replace('_', ' ')} ({format_measurement(value)}).",
                scientist=f"{key}={value}", source="Stored supporting evidence", support=level,
            ))
        for key, value in (candidate.contradicting_evidence or {}).items():
            contradicting.append(_evidence(
                evidence_type="contradicting_evidence", name=key, value=value,
                public=f"Stored evidence weighs against this interpretation: {key.replace('_', ' ')}.",
                scientist=f"{key}={value}", source="Stored candidate evidence", support="contradicting",
            ))

    # Positive FIRMS counts corroborate only when the stored match includes both
    # configured temporal and spatial criteria. A point is never a perimeter.
    firms_valid = _firms_supported(manifest)
    if manifest and manifest.matching_firms_detection_count and manifest.matching_firms_detection_count > 0:
        target = supporting if firms_valid else context
        level = "independent_support" if firms_valid else "contextual"
        target.append(_evidence(
            evidence_type="active_fire_point_detections", name="FIRMS active-fire detections",
            value=manifest.matching_firms_detection_count, unit="detections",
            public=(f"{manifest.matching_firms_detection_count} FIRMS active-fire point detection(s) match the configured time and distance windows."
                    if firms_valid else "FIRMS detections are recorded, but the stored record lacks the time or distance criteria needed to corroborate them."),
            scientist=f"time_buffer_hours={manifest.firms_time_buffer_hours}; spatial_buffer_m={manifest.firms_spatial_buffer_m}; nearest_distance_m={manifest.nearest_firms_distance_m}",
            source="NASA FIRMS active-fire point observations", support=level,
        ))
    return direct, supporting, context, contradicting


def _metadata(analysis: Any, before: Any, after: Any, manifest: Any) -> DecodedNISARMetadata:
    acq = before or after
    code = enum_value(acq.product_type) if acq else None
    if acq and acq.id:
        # The actual granule identifier may carry L2 and PR codes.
        code = acq.id
    maturity = enum_value(acq.maturity) if acq else None
    return decode_nisar_metadata(
        product_code=code,
        maturity=maturity,
        orbit_direction=acq.orbit_direction if acq else (manifest.orbit_direction if manifest else None),
        track=acq.track if acq else (manifest.track if manifest else None),
        frame=acq.frame if acq else (manifest.frame if manifest else None),
        mode=acq.mode if acq else (manifest.mode if manifest else None),
        frequency=acq.frequency if acq else None,
        bandwidth=acq.bandwidth if acq else None,
        polarizations=acq.polarizations if acq else (manifest.polarizations if manifest else []),
        acquisition_dates=[item.acquisition_datetime for item in (before, after) if item],
        # Do not relabel this app's pipeline version as a NISAR PGE version.
        processing_version=getattr(acq, "processing_version", None) if acq else None,
        analysis_pipeline_version=manifest.pipeline_version if manifest else None,
        code_version=manifest.code_version if manifest else None,
        crid=acq.crid if acq else (manifest.crid if manifest else None),
        comparison_policy=manifest.comparison_policy if manifest else None,
        dataset_path=(manifest.detection_parameters or {}).get("dataset_path") if manifest else None,
        quality_parameters=manifest.quality_parameters if manifest else {},
        detection_parameters=manifest.detection_parameters if manifest else {},
        source=acq.source if acq else None,
        before_granule_id=before.id if before else None,
        after_granule_id=after.id if after else None,
    )


def _interpretations(analysis: Any, candidates: Iterable[Any], manifest: Any, product_code: Optional[str] = None) -> tuple[list[SituationInterpretation], str, str, str, list[str]]:
    state = enum_value(analysis.observation_state)
    domain = enum_value(analysis.domain)
    if state in STATE_WORDING:
        headline, summary = STATE_WORDING[state]
    else:
        headline, summary = "Surface observation", "Technical metadata available; interpretation not defined."
    interpretations: list[SituationInterpretation] = []
    limitations: list[str] = []
    measurements = analysis.measurements or {}
    supported = [item for item in candidates if getattr(item, "supported", False)]

    if state == "no_change":
        interpretations.append(SituationInterpretation(
            code="no_significant_change", public_label="No significant surface change",
            scientific_label="No change above configured analysis criteria",
            description=summary, status="supported",
            reason="The processed analysis state is NO_CHANGE.",
        ))
        what_changed = "No significant surface change was found under the configured analysis criteria."
        measured = "Repeat radar observations were compared using the stored analysis; no significant change passed its criteria."
        limitations = ["This result does not establish that the area is safe or free of hazards."]
        return interpretations, headline, summary, what_changed + "\n" + measured, limitations

    if state == "insufficient_data":
        reason = analysis.quality.notes or "The stored analysis did not pass its quality gate."
        what_changed = "The analysis could not determine whether surface change occurred."
        measured = "The stored analysis did not have enough usable radar data to support a conclusion."
        limitations = [LIMITATIONS["insufficient"], reason]
        return interpretations, headline, summary, what_changed + "\n" + measured, limitations

    if state == "unknown_change":
        interpretations.append(SituationInterpretation(
            code="unknown_surface_change", public_label="Unknown radar change",
            scientific_label="Unclassified radar change", description=summary,
            status="ambiguous", reason="The stored observation state is UNKNOWN_CHANGE.",
            rule_id="UNKNOWN_CHANGE_01", public_reason=rule("UNKNOWN_CHANGE_01").public_reason,
            alternative_explanations=list(rule("UNKNOWN_CHANGE_01").alternative_explanations),
            limitations=[LIMITATIONS["unknown"]],
        ))
        for item in candidates:
            if item.physical_evidence or item.independent_evidence:
                label = enum_value(item.candidate_domain).replace("_", " ").title()
                interpretations.append(SituationInterpretation(
                    code=f"possible_{enum_value(item.candidate_domain)}",
                    public_label=f"Possible {label.lower()} explanation",
                    scientific_label=f"Candidate: {label}",
                    description=item.notes or "Stored evidence lists this as a candidate interpretation.",
                    status="possible" if item.supported else "ambiguous",
                    reason="Candidate evidence is recorded, but the cause is not established.",
                    limitations=[LIMITATIONS["unknown"]],
                ))
        what_changed = "Unusual radar change was measured, but its physical cause was not identified."
        measured = "The processed analysis flagged a radar anomaly; candidate evidence remains inconclusive."
        limitations = [LIMITATIONS["unknown"]]
        return interpretations, headline, summary, what_changed + "\n" + measured, limitations

    if state not in {"change_detected", "strong_change"}:
        return interpretations, headline, summary, summary, [LIMITATIONS["unknown"]]

    if domain in WATER_DOMAINS:
        candidate_area = measurements.get("candidate_radar_change_area_km2")
        retained_area = measurements.get("retained_mapped_region_area_km2")
        filtered_area = measurements.get("removed_small_component_area_km2")
        legacy_area = measurements.get("inundated_area_km2", measurements.get("new_water_area_km2"))
        area = candidate_area if candidate_area is not None else legacy_area
        # Physical direction is only inferred from the canonical signed metric: after - before.
        backscatter = measurements.get("mean_backscatter_difference_db")
        coherent = bool(supported or measurements.get("polygon_count"))
        independent_water = any(
            enum_value(item.candidate_domain) in WATER_DOMAINS
            and any(
                ("optical_water" in key.lower() or "water_index" in key.lower())
                and value not in (None, False, 0, "")
                for key, value in (item.independent_evidence or {}).items()
            )
            for item in supported
        )
        fire_related = False
        direction = None
        if backscatter is not None:
            direction = "expansion" if float(backscatter) < 0 else "recession" if float(backscatter) > 0 else None
        elif candidate_area is not None and measurements.get("change_criterion_db") is not None:
            # The real showcase mask is explicitly defined by a negative after-minus-before criterion.
            direction = "expansion" if float(measurements["change_criterion_db"]) < 0 else None
        elif "backscatter_reduction_mean_db" in measurements:
            # Legacy demonstration records may use an ambiguously named field. Do not reverse-engineer its sign.
            direction = None
        code = "surface_water_recession" if direction == "recession" else "surface_water_expansion"
        label = "Surface-water change consistent with inundation" if independent_water and direction != "recession" else (
            "Possible surface-water recession" if direction == "recession" else "Possible surface-water expansion"
        )
        if state == "change_detected":
            headline = "Surface-water change detected"
        description = (
            "NISAR observed a coherent decrease in radar backscatter that is consistent with increased open water or inundation."
            if direction == "expansion" else
            "NISAR observed a coherent increase in radar backscatter that may be consistent with reduced open water or surface-water recession."
            if direction == "recession" else
            "The processed radar analysis identified coherent surface-water change in the selected area."
        )
        if independent_water:
            description = "NISAR radar change is consistent with the stored independent optical water evidence; this does not by itself confirm a flood."
        water_rule = rule("GCOV_BACKSCATTER_INCREASE_01" if direction == "recession" else "GCOV_BACKSCATTER_DECREASE_01")
        interpretations.append(SituationInterpretation(
            code=code, public_label=label, scientific_label="Radar-observed surface-water / inundation candidate change",
            description=description, status="supported" if independent_water else "possible",
            reason="A transparent application rule links the stored radar-change measurement to this cautious candidate interpretation.",
            rule_id=water_rule.rule_id,
            public_reason=water_rule.public_reason,
            alternative_explanations=list(water_rule.alternative_explanations),
            limitations=[water_rule.limitation],
        ))
        if any(enum_value(item.candidate_domain) == "wildfire" for item in supported):
            # Defensive; no fire attribution from a water-domain record.
            fire_related = False
        _ = fire_related
        what_changed = description
        if candidate_area is not None:
            what_changed += f" Candidate radar-change pixels: {format_measurement(candidate_area, 'km²')}."
            if retained_area is not None:
                what_changed += f" After minimum-region filtering, {format_measurement(retained_area, 'km²')} remained as mapped regions."
            if filtered_area is not None and float(filtered_area) > 0:
                what_changed += f" {format_measurement(filtered_area, 'km²')} of smaller components were filtered from the mapped-region total."
        elif area is not None:
            what_changed += f" Stored demonstration change area: {format_measurement(area, 'km²')}."
        measured = "NISAR GCOV measured repeat-pass radar surface backscatter."
        if backscatter is not None:
            measured += f" Signed after-minus-before backscatter difference: {format_measurement(backscatter, 'dB')}."
        elif measurements.get("change_criterion_db") is not None:
            measured += f" Candidate pixels met an after-minus-before backscatter criterion of {format_measurement(measurements['change_criterion_db'], 'dB')} or lower."
        limitations = [LIMITATIONS["water"]]
        # Explicitly guard against unsupported authoritative flood wording.
        if not independent_water:
            limitations.append("This interpretation is not an authoritative flood declaration.")
        return interpretations, headline, summary, what_changed + "\n" + measured, limitations

    if domain == "wildfire":
        firms = _firms_supported(manifest)
        code = "fire_correlated_vegetation_disturbance" if firms else "vegetation_disturbance"
        label = "Vegetation disturbance consistent with fire activity" if firms else "Vegetation disturbance"
        headline = "Vegetation disturbance detected" if state == "change_detected" else headline
        description = (
            "NISAR observed a coherent change in radar backscatter from vegetated surfaces."
            if not firms else
            "Radar-detected vegetation disturbance is spatially and temporally supported by FIRMS active-fire point detections."
        )
        vegetation_rule = rule("FIRMS_FIRE_SUPPORT_01" if firms else "GCOV_VEGETATION_DISTURBANCE_01")
        interpretations.append(SituationInterpretation(
            code=code, public_label=label, scientific_label="Radar-detected vegetation disturbance",
            description=description, status="supported" if firms else "possible",
            reason="The deterministic vegetation rule uses stored radar evidence" + (" plus qualifying FIRMS context." if firms else "."),
            rule_id=vegetation_rule.rule_id, public_reason=vegetation_rule.public_reason,
            alternative_explanations=list(vegetation_rule.alternative_explanations),
            limitations=[vegetation_rule.limitation],
        ))
        limitations = [LIMITATIONS["vegetation"]]
        if firms:
            limitations.append("FIRMS active-fire detections are points and do not define a burn perimeter.")
        return interpretations, headline, summary, description, limitations

    if domain == "deformation":
        if product_code != "GUNW":
            interpretations.append(SituationInterpretation(
                code="unknown_surface_change", public_label="Radar surface change",
                scientific_label="Deformation-domain change without a decoded GUNW product",
                description="The stored analysis reports change, but its product metadata does not identify a GUNW displacement product.",
                status="ambiguous", reason="A deformation label alone does not establish a displacement measurement.",
                limitations=[LIMITATIONS["unknown"]],
            ))
            return interpretations, headline, summary, "The stored analysis reports a change; a GUNW displacement interpretation is not supported by the decoded product metadata.", [LIMITATIONS["unknown"]]
        los = measurements.get("los_displacement_mm", measurements.get("max_displacement_mm"))
        coherence = measurements.get("mean_coherence")
        label = "Ground movement"
        headline = "Ground movement detected" if state == "change_detected" else headline
        description = "The radar observations indicate relative movement of the surface toward or away from the satellite."
        if los is not None:
            description += f" Stored line-of-sight displacement: {format_measurement(los, 'mm')}."
        interpretations.append(SituationInterpretation(
            code="ground_displacement", public_label=label,
            scientific_label="Relative line-of-sight surface displacement",
            description=description, status="supported",
            reason="Ground-motion interpretation follows the stored deformation analysis state and measurements.",
            rule_id="GUNW_LOS_DISPLACEMENT_01", public_reason=rule("GUNW_LOS_DISPLACEMENT_01").public_reason,
            alternative_explanations=list(rule("GUNW_LOS_DISPLACEMENT_01").alternative_explanations),
            limitations=[LIMITATIONS["gunw"]],
        ))
        return interpretations, headline, summary, description, [LIMITATIONS["gunw"], "The cause and vertical component of any line-of-sight motion remain unresolved."]

    if domain == "glacier":
        if product_code != "GOFF":
            interpretations.append(SituationInterpretation(
                code="unknown_surface_change", public_label="Radar surface change",
                scientific_label="Glacier-domain change without a decoded GOFF product",
                description="The stored analysis does not identify a GOFF pixel-offset product.",
                status="ambiguous", reason="Glacier motion cannot be inferred from domain metadata alone.",
                limitations=[LIMITATIONS["goff"]],
            ))
            return interpretations, headline, summary, "The stored analysis reports a change, but glacier motion is not supported by decoded GOFF product metadata.", [LIMITATIONS["goff"]]
        velocity = measurements.get("velocity_m_per_day")
        velocity_before = measurements.get("before_velocity_m_per_day")
        velocity_after = measurements.get("after_velocity_m_per_day")
        if velocity_before is not None and velocity_after is not None:
            velocity_change = float(velocity_after) - float(velocity_before)
            if velocity_change > 0:
                glacier_code, glacier_label = "glacier_acceleration", "Glacier velocity increased"
                velocity_text = "The stored before/after measurements show increased glacier velocity."
            elif velocity_change < 0:
                glacier_code, glacier_label = "glacier_slowdown", "Glacier velocity decreased"
                velocity_text = "The stored before/after measurements show decreased glacier velocity."
            else:
                glacier_code, glacier_label = "glacier_displacement", "Glacier motion detected"
                velocity_text = "The stored before/after velocity measurements show no net speed change."
            goff_rule = rule("GOFF_MOTION_01")
            interpretations.append(SituationInterpretation(
                code=glacier_code, public_label=glacier_label,
                scientific_label="Stored GOFF before/after velocity comparison",
                description=velocity_text, status="supported",
                reason="The stated direction is derived from both stored velocity measurements.",
                rule_id=goff_rule.rule_id, public_reason=goff_rule.public_reason,
                alternative_explanations=list(goff_rule.alternative_explanations),
                limitations=[LIMITATIONS["goff"]],
            ))
            headline = "Glacier motion change detected" if state == "change_detected" else headline
            return interpretations, headline, summary, f"{velocity_text} Before: {format_measurement(velocity_before, 'm/day')}; after: {format_measurement(velocity_after, 'm/day')}.", [LIMITATIONS["goff"]]
        description = "The processed pixel-offset analysis indicates glacier surface motion."
        if velocity is not None:
            description += f" Stored velocity: {format_measurement(velocity, 'm/day')}."
        interpretations.append(SituationInterpretation(
            code="glacier_displacement", public_label="Glacier motion change",
            scientific_label="Geocoded pixel-offset surface motion",
            description=description, status="supported",
            reason="A stored GOFF-style motion analysis and measurement are present.",
            rule_id="GOFF_MOTION_01", public_reason=rule("GOFF_MOTION_01").public_reason,
            alternative_explanations=list(rule("GOFF_MOTION_01").alternative_explanations),
            limitations=[LIMITATIONS["goff"]],
        ))
        headline = "Glacier motion change detected" if state == "change_detected" else headline
        return interpretations, headline, summary, description, [LIMITATIONS["goff"]]

    headline = "Strong surface change detected" if state == "strong_change" else "Surface change detected"
    interpretation = SituationInterpretation(
        code="unknown_surface_change", public_label="Unclassified surface change",
        scientific_label="Processed radar change", description=summary,
        status="ambiguous", reason="Stored evidence supports change, but not a more specific physical interpretation.",
        limitations=[LIMITATIONS["unknown"]],
    )
    interpretations.append(interpretation)
    return interpretations, headline, summary, "A processed radar change was measured; the physical cause is not identified.", [LIMITATIONS["unknown"]]


def build_situation_record(
    analysis: Any,
    *, event: Any = None, aoi: Any = None, before: Any = None, after: Any = None,
    manifest: Any = None, candidates: Iterable[Any] = (), validation: Any = None,
    evidence: Any = None, regions: Iterable[Any] = (),
) -> SituationRecord:
    """Create a deterministic explanation from one stored analysis record."""
    candidates = list(candidates or [])
    regions = list(regions or [])
    state = enum_value(analysis.observation_state)
    origin = enum_value(analysis.data_origin)
    metadata = _metadata(analysis, before, after, manifest)
    direct = _measurement_evidence(analysis, (before.source if before else "NISAR processed analysis"))
    candidate_direct, supporting, context, contradicting = _candidate_evidence(candidates, manifest)
    direct.extend(candidate_direct)
    if any(region.geometry for region in regions):
        direct.append(_evidence(
            evidence_type="coherent_change_regions", name="Connected radar-change regions",
            value=len([region for region in regions if region.geometry]), unit="regions",
            public=f"{len([region for region in regions if region.geometry])} connected change region(s) are stored.",
            scientist="Count of stored polygonized change regions", source="Processed analysis polygons", support="direct_measurement",
        ))
    interpretations, headline, summary, changed_plus_measured, limitations = _interpretations(
        analysis, candidates, manifest, metadata.product_code
    )
    explanation_evidence_ids = build_evidence_ids([*direct, *supporting, *context])
    for interpretation in interpretations:
        if not interpretation.evidence_ids:
            interpretation.evidence_ids = explanation_evidence_ids
    parts = changed_plus_measured.split("\n", 1)
    what_changed = parts[0]
    what_measured = parts[1] if len(parts) > 1 else (metadata.product_explanation or "Stored radar measurements were analyzed.")

    if aoi and (getattr(aoi, "display_name", None) or getattr(aoi, "region", None)):
        place = ", ".join(value for value in [getattr(aoi, "display_name", None), getattr(aoi, "region", None), getattr(aoi, "country", None)] if value)
        context.append(_evidence(
            evidence_type="location_context", name="Analysis area", value=place,
            public=f"Analysis area: {place}.", scientist=f"aoi_id={aoi.id}", source="Stored AOI record", support="contextual",
        ))

    valid_fraction = float(getattr(analysis.quality, "valid_pixel_fraction", 0.0) or 0.0)
    coherence = (analysis.measurements or {}).get("mean_coherence")
    quality_parameters = manifest.quality_parameters if manifest else {}
    coherence_threshold = quality_parameters.get("min_coherence", quality_parameters.get("coherence_threshold"))
    quality = public_quality(valid_fraction, bool(analysis.quality.quality_gate_passed), analysis.quality.notes, coherence, coherence_threshold)
    if state == "insufficient_data":
        quality["explanation"] = "Too much of the selected area lacked usable radar data for a reliable change analysis."
        quality["failure_reason"] = analysis.quality.notes
    quality_threshold = (manifest.quality_parameters or {}).get("quality_gate_threshold") if manifest else None
    if quality_threshold is not None:
        quality["configured_threshold"] = quality_threshold

    if state == "no_change":
        recommended = "No significant surface change detected under the configured analysis criteria."
    elif state == "unknown_change":
        recommended = "Unusual radar change detected. Cause not identified."
    elif state == "insufficient_data":
        recommended = "Not enough usable data to determine surface change."
    else:
        recommended = interpretations[0].description if interpretations else summary

    validation_note = getattr(validation, "notes", None)
    if validation_note:
        context.append(_evidence(
            evidence_type="validation_context", name="Validation record", value=validation_note,
            public=validation_note, scientist=f"status={enum_value(validation.status)}; reference={validation.reference_dataset}",
            source=validation.reference_dataset, support="contextual",
        ))
    if evidence and getattr(evidence, "optical_context", None):
        optical = evidence.optical_context
        context.append(_evidence(
            evidence_type="earth_observation_context", name="Optical reference context",
            value=optical.date, public=f"Optical context source: {optical.source} ({optical.date or 'date not recorded'}).",
            scientist=f"source={optical.source}; date={optical.date}", source=optical.source, support="contextual",
        ))

    dates = [_date_label(item) for item in metadata.acquisition_dates]
    if event and event.comparison_start:
        dates = [_date_label(event.comparison_start), _date_label(event.comparison_end)] if event.comparison_end else [_date_label(event.comparison_start)]
    if dates:
        what_changed = f"Observed {dates[0]}" + (f" → {dates[1]}. " if len(dates) > 1 else ". ") + what_changed

    if origin == "precomputed_real_analysis":
        human_label = "REAL NISAR ANALYSIS"
    elif origin == "synthetic_ui_fixture":
        human_label = "DEMO INTERPRETATION"
        summary = "Synthetic development fixture — not an Earth observation result. " + summary
    else:
        human_label = "ANALYSIS RECORD"

    return SituationRecord(
        analysis_id=analysis.id,
        event_id=getattr(event, "id", None),
        aoi_id=analysis.aoi_id,
        observation_state=state,
        headline=headline,
        summary=summary,
        what_changed=what_changed,
        what_nisar_measured=what_measured,
        interpretations=interpretations,
        direct_evidence=direct,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        context=context,
        data_quality=quality,
        what_we_cannot_say=limitations,
        recommended_public_wording=recommended,
        technical_metadata=metadata,
        manifest_id=analysis.manifest_id,
        data_origin=origin,
        human_label=human_label,
    )


def build_coverage_only_situation(metadata: DecodedNISARMetadata, acquisition_count: int = 0) -> SituationRecord:
    """Describe coverage metadata without claiming that physical change exists."""
    return SituationRecord(
        observation_state="no_processed_analysis",
        headline="NISAR observations are available for this area.",
        summary="No processed surface-change analysis exists yet.",
        what_changed="No processed surface-change analysis exists yet.",
        what_nisar_measured=(metadata.product_explanation or "NISAR product metadata is available.") + " Product availability alone does not show that surface change occurred.",
        interpretations=[],
        direct_evidence=[],
        supporting_evidence=[],
        contradicting_evidence=[],
        context=[_evidence(
            evidence_type="coverage_metadata", name="NISAR archive observations",
            value=acquisition_count, unit="acquisitions",
            public=f"{acquisition_count} archive observation(s) are available; no processed analysis is attached.",
            scientist="Metadata-only archive search result", source=metadata.source or "ASF DAAC", support="contextual",
        )],
        data_quality={"status": "not_assessed", "explanation": "No processed analysis quality assessment exists."},
        what_we_cannot_say=["Product availability does not establish that any physical change occurred."],
        recommended_public_wording="NISAR observations are available for this area, but no processed surface-change analysis exists yet.",
        technical_metadata=metadata,
        data_origin="live_metadata",
        human_label="LIVE METADATA",
    )
