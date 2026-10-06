/**
 * Situation Dashboard Compact Map Overview
 * Renders analyzed AOIs colored STRICTLY by scientific observation state.
 * Displays Review Priority in popup tooltips only when scored.
 */

window.initDashboardMap = function(geojson) {
  const container = document.getElementById('dashboard-map');
  if (!container) return;
  if (typeof maplibregl === 'undefined') {
    container.innerHTML = '<div class="h-full flex items-center justify-center p-6 text-center text-sm text-[#94A3B8]"><div><div class="text-white font-medium mb-1">Interactive map could not load.</div><div>Analysis records remain available in the dashboard below.</div></div></div>';
    return;
  }
  if (!window.NisarBasemaps) {
    container.innerHTML = '<div class="h-full flex items-center justify-center p-6 text-center text-sm text-[#94A3B8]">Basemap configuration could not load. Analysis records remain available below.</div>';
    return;
  }

  const map = new maplibregl.Map({
    container: 'dashboard-map',
    style: window.NisarBasemaps.createStyle(),
    center: [0, 20],
    zoom: 1.5,
    attributionControl: false
  });
  map.on('error', event => {
    if (event.error) console.error('MapLibre error:', event.error);
  });
  window.NisarBasemaps.bindFallback(map);

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-left');

  map.on('load', () => {
    map.resize();
    map.addSource('analyzed-aois', {
      type: 'geojson',
      data: geojson
    });

    // Fill Layer: Colors strictly driven by scientific observation state
    map.addLayer({
      id: 'analyzed-aois-fill',
      type: 'fill',
      source: 'analyzed-aois',
      paint: {
        'fill-color': ['get', 'observation_state_color'],
        'fill-opacity': 0.35
      }
    });

    // Stroke Layer: Colors strictly driven by scientific observation state
    map.addLayer({
      id: 'analyzed-aois-stroke',
      type: 'line',
      source: 'analyzed-aois',
      paint: {
        'line-color': ['get', 'observation_state_color'],
        'line-width': 2,
        'line-opacity': 0.9
      }
    });

    // Click Popup
    map.on('click', 'analyzed-aois-fill', (e) => {
      if (!e.features || !e.features.length) return;
      const f = e.features[0];
      const p = f.properties;

      let priorityHtml = '';
      if (p.review_priority_band && p.review_score !== null && p.review_score !== undefined) {
        let badgeColor = '#94A3B8';
        if (p.review_priority_band === 'HIGH') badgeColor = '#818CF8';
        else if (p.review_priority_band === 'MEDIUM') badgeColor = '#38BDF8';

        priorityHtml = `
          <div class="mt-2 pt-2 border-t border-[#1E2838] flex items-center justify-between text-[11px] font-mono">
            <span class="text-[#5C6B80]">Review Priority:</span>
            <span style="color: ${badgeColor}; font-weight: bold;">
              ${p.review_priority_band} (${Number(p.review_score).toFixed(2)})
            </span>
          </div>
        `;
      }

      let actionHtml = '';
      if (p.event_url) {
        actionHtml = `
          <div class="mt-3 pt-2 border-t border-[#1E2838]">
            <a href="${p.event_url}" class="btn btn-primary text-xs py-1 px-2.5 w-full text-center block">
              View Explanation
            </a>
          </div>
        `;
      }

      const content = `
        <div class="p-1 font-mono text-xs text-white max-w-xs">
          <div class="font-bold text-sm text-white">${p.aoi_name}</div>
          <div class="text-[10px] text-[#5C6B80]">${p.aoi_country || 'Global'} &bull; ${p.domain_label}</div>
          <div class="mt-2 flex items-center gap-1.5">
            <span class="inline-block w-2.5 h-2.5 rounded-full" style="background-color: ${p.observation_state_color};"></span>
            <span class="font-semibold uppercase tracking-wider text-[11px]" style="color: ${p.observation_state_color};">
              ${p.observation_state_label}
            </span>
          </div>
          <div class="mt-2 text-[11px] text-white font-semibold">${p.human_headline || p.interpretation}</div>
          <div class="text-[11px] text-[#94A3B8] mt-1">${p.human_label || p.domain_label}</div>
          <div class="text-[10px] text-[#94A3B8] mt-1">${p.comparison_dates || 'Dates unavailable'}</div>
          <div class="text-[10px] text-[#CBD5E1] mt-1">${p.primary_measurement || 'No primary measurement recorded'}</div>
          ${priorityHtml}
          ${actionHtml}
        </div>
      `;

      new maplibregl.Popup({ closeButton: true, className: 'scientific-popup' })
        .setLngLat(e.lngLat)
        .setHTML(content)
        .addTo(map);
    });

    // Hover cursor
    map.on('mouseenter', 'analyzed-aois-fill', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'analyzed-aois-fill', () => {
      map.getCanvas().style.cursor = '';
    });

    // Auto fit bounds
    try {
      if (geojson.features && geojson.features.length) {
        const bounds = new maplibregl.LngLatBounds();
        geojson.features.forEach(feat => {
          if (feat.geometry && feat.geometry.coordinates) {
            const geom = feat.geometry;
            if (geom.type === 'Polygon') {
              geom.coordinates[0].forEach(c => bounds.extend(c));
            } else if (geom.type === 'MultiPolygon') {
              geom.coordinates.forEach(poly => poly[0].forEach(c => bounds.extend(c)));
            }
          }
        });
        if (!bounds.isEmpty()) {
          map.fitBounds(bounds, { padding: 40, maxZoom: 6 });
        }
      }
    } catch (_) {}
  });
};
