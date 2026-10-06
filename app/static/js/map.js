/**
 * NISAR Surface Change Explorer
 * MapLibre GL JS Core Orchestrator
 *
 * Connects MapLibre map, server-side spatial inspection API,
 * interactive drawing tooling, live NISAR coverage discovery,
 * and the Area Inspector.
 */

document.addEventListener('DOMContentLoaded', () => {
  initNisarMap();
});

function initNisarMap() {
  const mapContainer = document.getElementById('map');
  if (!mapContainer) return;

  if (typeof maplibregl === 'undefined') {
    console.error('[MapLibre] maplibregl library is not loaded.');
    mapContainer.innerHTML = '<div class="p-4 text-red-400 font-mono text-sm">Failed to load MapLibre GL JS library.</div>';
    return;
  }

  if (!window.NisarBasemaps) {
    console.error('[MapLibre] Shared basemap configuration is unavailable.');
    return;
  }

  const preferences = window.NisarPreferences;
  const savedView = (() => { try { return JSON.parse(localStorage.getItem('nisar-map-last-view') || 'null'); } catch (_) { return null; } })();
  const defaultView = preferences ? preferences.get('mapDefaultView') : 'global';
  const initialView = defaultView === 'last-view' && savedView
    ? savedView
    : defaultView === 'north-america' ? { center: [-101, 39], zoom: 3.1 } : { center: [0, 20], zoom: 1.8 };
  try {
    const map = new maplibregl.Map({
      container: 'map',
      style: window.NisarBasemaps.createStyle(),
      center: initialView.center,
      zoom: initialView.zoom,
      minZoom: 1,
      maxZoom: 18,
      attributionControl: false
    });
    map.on('error', event => {
      if (event.error) console.error('MapLibre error:', event.error);
    });
    window.NisarBasemaps.bindFallback(map, () => {
      const status = document.getElementById('map-basemap-status');
      if (status) status.textContent = 'Satellite basemap unavailable — using OpenStreetMap.';
      const satelliteButton = document.getElementById('basemap-satellite');
      const streetsButton = document.getElementById('basemap-streets');
      if (satelliteButton) satelliteButton.setAttribute('aria-pressed', 'false');
      if (streetsButton) streetsButton.setAttribute('aria-pressed', 'true');
      const currentLabel = document.getElementById('map-basemap-label');
      if (currentLabel) currentLabel.textContent = 'OpenStreetMap';
    });

    // Controls
    map.addControl(new maplibregl.NavigationControl({
      showCompass: true,
      visualizePitch: true
    }), 'top-right');

    map.addControl(new maplibregl.AttributionControl({
      compact: false
    }), 'bottom-right');
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');

    // Instantiate Area Inspector
    const inspector = new window.AreaInspector('area-inspector-content');
    window.nisarInspector = inspector;

    // Coordinate HUD update
    const coordDisplay = document.getElementById('map-coordinates');
    const zoomDisplay = document.getElementById('map-zoom');

    function updateReadout() {
      const center = map.getCenter();
      const zoom = map.getZoom();
      if (coordDisplay) {
        const latStr = `${Math.abs(center.lat).toFixed(4)}° ${center.lat >= 0 ? 'N' : 'S'}`;
        const lngStr = `${Math.abs(center.lng).toFixed(4)}° ${center.lng >= 0 ? 'E' : 'W'}`;
        coordDisplay.textContent = `${latStr}, ${lngStr}`;
      }
      if (zoomDisplay) {
        zoomDisplay.textContent = `Z${zoom.toFixed(1)}`;
      }
    }

    map.on('move', updateReadout);
    map.on('moveend', () => {
      try { localStorage.setItem('nisar-map-last-view', JSON.stringify({ center: map.getCenter().toArray(), zoom: map.getZoom() })); } catch (_) {}
    });

    // Map Load Pipeline
    map.on('load', async () => {
      map.resize();
      updateReadout();

      // Add scientific overlays above the initial OSM raster layer.
      await loadDemoLayers(map);
      initFootprintsLayer(map);

      // 1. Selection is created last so its marker/drawing stays above overlays.
      const selectionManager = new window.MapSelectionManager(map, {
        onSelect: (payload) => {
          inspector.setLastGeometry(payload.geometry);
          performAreaInspection(payload);
        },
        onClear: () => {
          inspector.renderEmpty();
          clearHighlightedAOIs();
          clearNisarFootprints(map);
        }
      });
      window.nisarSelection = selectionManager;

      // 3. Setup Toolbar Tool Selectors
      setupToolbar(map, selectionManager, inspector);
      setupLocationSearch(map, selectionManager);

      // 4. Setup "Find Demo Area" Selector
      setupFindDemoArea(map, selectionManager, inspector);

      // 5. Setup Layer Visibility Toggles
      setupLayerToggles(map);
      setupBasemapSwitcher(map);

      // 6. Check URL query parameters (e.g. /map?aoi=aoi_synth_alpha)
      checkUrlParameters(map, inspector);

      console.log('[NISAR Map] Interactive map initialized.');
    });

    if (typeof ResizeObserver !== 'undefined') {
      const workspace = mapContainer.closest('.grid') || mapContainer.parentElement;
      if (workspace) {
        const workspaceObserver = new ResizeObserver(() => map.resize());
        workspaceObserver.observe(workspace);
      }
    } else window.addEventListener('resize', () => map.resize());
    window.nisarMap = map;

  } catch (err) {
    console.error('[MapLibre] Error initializing map:', err);
    mapContainer.innerHTML = `<div class="p-6 text-red-400 font-mono text-sm bg-panel border border-red-900/50">
      <div class="font-bold mb-2">Map Initialization Error</div>
      <div>${err.message || err}</div>
    </div>`;
  }
}

/** Split stored features by origin while keeping real and demo overlays distinct. */
function splitByDemoOrigin(collection) {
  const features = collection && Array.isArray(collection.features) ? collection.features : [];
  return {
    real: { type: 'FeatureCollection', features: features.filter(f => f.properties?.is_demo === false) },
    demo: { type: 'FeatureCollection', features: features.filter(f => f.properties?.is_demo !== false) }
  };
}

function addGeoJSONSource(map, id, data) {
  if (map.getSource(id)) map.getSource(id).setData(data);
  else map.addSource(id, { type: 'geojson', data });
}

function addAOILayers(map, sourceId, prefix, isDemo) {
  const color = isDemo ? '#8B5CF6' : '#1E6BFF';
  map.addLayer({
    id: `${prefix}-fill`, type: 'fill', source: sourceId,
    paint: { 'fill-color': color, 'fill-opacity': isDemo ? 0.045 : 0.09 }
  });
  map.addLayer({
    id: `${prefix}-line`, type: 'line', source: sourceId,
    paint: { 'line-color': color, 'line-width': 1.5, 'line-opacity': 0.65 }
  });
  map.addLayer({
    id: `${prefix}-highlight`, type: 'line', source: sourceId,
    paint: { 'line-color': '#60A5FA', 'line-width': 2.5, 'line-opacity': 0.95 },
    filter: ['==', ['get', 'id'], '']
  });
  map.on('click', `${prefix}-fill`, e => {
    if (window.nisarSelection?.currentMode !== 'click') return;
    const feature = e.features && e.features[0];
    if (!feature) return;
    const aoiId = feature.properties.id;
    highlightAOI(aoiId);
    map.fitBounds(geometryBounds(feature.geometry), { padding: 70, maxZoom: 9, duration: 900 });
    triggerInspectionByAoiId(aoiId, feature.geometry);
  });
  map.on('mouseenter', `${prefix}-fill`, () => {
    if (window.nisarSelection?.currentMode === 'click') map.getCanvas().style.cursor = 'pointer';
  });
  map.on('mouseleave', `${prefix}-fill`, () => { map.getCanvas().style.cursor = ''; });
}

function addChangeLayers(map, sourceId, prefix, isDemo) {
  const color = isDemo ? '#8B5CF6' : [
    'match', ['get', 'classification_status'], 'resolved', '#00D2FF', 'ambiguous', '#8B5CF6', '#1E6BFF'
  ];
  map.addLayer({
    id: `${prefix}-fill`, type: 'fill', source: sourceId,
    paint: { 'fill-color': color, 'fill-opacity': isDemo ? 0.18 : 0.32 }
  });
  map.addLayer({
    id: `${prefix}-line`, type: 'line', source: sourceId,
    paint: { 'line-color': color, 'line-width': 1.8, 'line-opacity': isDemo ? 0.58 : 0.92 }
  });
  map.on('click', `${prefix}-fill`, e => {
    if (window.nisarSelection?.currentMode !== 'click') return;
    const feature = e.features && e.features[0];
    if (!feature) return;
    window.nisarInspector.setLastGeometry(feature.geometry);
    performAreaInspection({
      geometry: feature.geometry,
      selection_type: 'polygon',
      coordinates_display: `Detected Change Region (${feature.properties.area_km2 || ''} km²)`
    });
  });
}

function geometryBounds(geometry) {
  const points = [];
  const visit = value => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && Number.isFinite(value[0]) && Number.isFinite(value[1])) points.push(value);
    else value.forEach(visit);
  };
  visit(geometry && geometry.coordinates);
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  return [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]];
}

async function loadDemoLayers(map) {
  try {
    const response = await fetch('/api/demo/aois.geojson');
    if (!response.ok) throw new Error(`AOI request failed (${response.status})`);
    const split = splitByDemoOrigin(await response.json());
    addGeoJSONSource(map, 'real-analysis-aois', split.real);
    addGeoJSONSource(map, 'synthetic-aois', split.demo);
    addAOILayers(map, 'real-analysis-aois', 'real-analysis-aois', false);
    addAOILayers(map, 'synthetic-aois', 'synthetic-aois', true);
  } catch (err) {
    console.warn('[MapLibre] Could not load AOI layers:', err);
  }

  try {
    const response = await fetch('/api/demo/change-regions.geojson');
    if (!response.ok) throw new Error(`Change-region request failed (${response.status})`);
    const split = splitByDemoOrigin(await response.json());
    addGeoJSONSource(map, 'real-change-regions', split.real);
    addGeoJSONSource(map, 'synthetic-change-regions', split.demo);
    addChangeLayers(map, 'real-change-regions', 'real-change-regions', false);
    addChangeLayers(map, 'synthetic-change-regions', 'synthetic-change-regions', true);
  } catch (err) {
    console.warn('[MapLibre] Could not load change-region layers:', err);
  }

  // Keep a predictable visual stack: real, then synthetic; footprints and
  // user-selection are appended after this function by the load pipeline.
  [
    'real-analysis-aois-fill', 'real-analysis-aois-line', 'real-analysis-aois-highlight',
    'real-change-regions-fill', 'real-change-regions-line',
    'synthetic-aois-fill', 'synthetic-aois-line', 'synthetic-aois-highlight',
    'synthetic-change-regions-fill', 'synthetic-change-regions-line'
  ].forEach(id => { if (map.getLayer(id)) map.moveLayer(id); });
}

/**
 * Initializes NISAR Granule Footprints Overlay Layer
 */
function initFootprintsLayer(map) {
  if (!map.getSource('nisar-footprints')) {
    map.addSource('nisar-footprints', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    map.addLayer({
      id: 'nisar-footprints-fill',
      type: 'fill',
      source: 'nisar-footprints',
      paint: {
        'fill-color': '#38BDF8',
        'fill-opacity': 0.08
      }
    });

    map.addLayer({
      id: 'nisar-footprints-line',
      type: 'line',
      source: 'nisar-footprints',
      paint: {
        'line-color': '#38BDF8',
        'line-width': 1.3,
        'line-opacity': 0.75
      }
    });

    // Footprint click popup
    map.on('click', 'nisar-footprints-fill', (e) => {
      const feat = e.features[0];
      if (!feat) return;
      const p = feat.properties;
      const html = `
        <div class="p-2 text-xs font-mono bg-[#090D14] text-white border border-[#1E2838] space-y-1">
          <div class="font-bold text-[#38BDF8]">${p.product_type} Acquisition</div>
          <div>Maturity: <span class="text-white">${p.data_maturity}</span></div>
          <div>Track: <span class="text-white">${p.track || '—'}</span> | Frame: <span class="text-white">${p.frame || '—'}</span></div>
          <div>Date: <span class="text-[#94A3B8]">${p.date || '—'}</span></div>
        </div>
      `;
      new maplibregl.Popup({ closeButton: true, className: 'nisar-popup' })
        .setLngLat(e.lngLat)
        .setHTML(html)
        .addTo(map);
    });

    map.on('mouseenter', 'nisar-footprints-fill', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'nisar-footprints-fill', () => {
      map.getCanvas().style.cursor = '';
    });
  }

  window.updateNisarFootprints = (geojson) => {
    const src = map.getSource('nisar-footprints');
    if (src && geojson) {
      src.setData(geojson);
      const toggle = document.getElementById('layer-toggle-footprints');
      if (toggle) {
        toggle.disabled = false;
        toggle.checked = true;
        const visibility = 'visible';
        if (map.getLayer('nisar-footprints-fill')) map.setLayoutProperty('nisar-footprints-fill', 'visibility', visibility);
        if (map.getLayer('nisar-footprints-line')) map.setLayoutProperty('nisar-footprints-line', 'visibility', visibility);
      }
    }
  };
}

function clearNisarFootprints(map) {
  const src = map.getSource('nisar-footprints');
  if (src) {
    src.setData({ type: 'FeatureCollection', features: [] });
  }
}

/**
 * Sends Selection Payload to POST /api/demo/inspect-area
 */
async function performAreaInspection(payload) {
  const inspector = window.nisarInspector;
  if (!inspector) return;

  inspector.renderLoading();
  inspector.setLastRequest(() => performAreaInspection(payload));

  try {
    const res = await fetch('/api/demo/inspect-area', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        geometry: payload.geometry || null,
        selection_type: payload.selection_type || 'point',
        aoi_id: payload.aoi_id || null
      })
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    if (payload.coordinates_display && !data.coordinates_display) {
      data.coordinates_display = payload.coordinates_display;
    }

    // Highlight matched AOIs on the map
    if (data.matched_aoi_ids && data.matched_aoi_ids.length > 0) {
      highlightAOIs(data.matched_aoi_ids);
    } else {
      clearHighlightedAOIs();
    }

    inspector.renderResponse(data);

  } catch (err) {
    console.error('[Area Inspection Error]:', err);
    inspector.renderError(err.message || 'Inspection request failed.');
  }
}

/**
 * Inspects a specific AOI directly by its ID
 */
function triggerInspectionByAoiId(aoiId, geometry = null) {
  if (geometry && window.nisarInspector) {
    window.nisarInspector.setLastGeometry(geometry);
  }
  performAreaInspection({
    aoi_id: aoiId,
    geometry: geometry,
    selection_type: 'point',
    coordinates_display: `AOI: ${aoiId}`
  });
}

function highlightAOI(aoiId) {
  highlightAOIs([aoiId]);
}

function highlightAOIs(aoiIds) {
  const map = window.nisarMap;
  if (!map) return;
  ['real-analysis-aois-highlight', 'synthetic-aois-highlight'].forEach(layerId => {
    if (!map.getLayer(layerId)) return;
    map.setFilter(layerId, !aoiIds || aoiIds.length === 0
      ? ['==', ['get', 'id'], '']
      : ['in', ['get', 'id'], ['literal', aoiIds]]);
  });
}

function clearHighlightedAOIs() {
  highlightAOIs([]);
}

/**
 * Map Toolbar Event Setup
 */
function setupToolbar(map, selectionManager, inspector) {
  const btnClick = document.getElementById('tool-click');
  const btnRect = document.getElementById('tool-rectangle');
  const btnPoly = document.getElementById('tool-polygon');
  const btnClear = document.getElementById('tool-clear');

  if (btnClick) {
    btnClick.addEventListener('click', () => selectionManager.setMode('click'));
  }
  if (btnRect) {
    btnRect.addEventListener('click', () => selectionManager.setMode('rectangle'));
  }
  if (btnPoly) {
    btnPoly.addEventListener('click', () => selectionManager.setMode('polygon'));
  }
  if (btnClear) {
    btnClear.addEventListener('click', () => selectionManager.clear());
  }
}

function setupBasemapSwitcher(map) {
  const satelliteButton = document.getElementById('basemap-satellite');
  const streetsButton = document.getElementById('basemap-streets');
  const status = document.getElementById('map-basemap-status');
  const currentLabel = document.getElementById('map-basemap-label');
  const basemaps = window.NisarBasemaps;
  if (!basemaps || !streetsButton) return;

  const satelliteAvailable = basemaps.canUseSatellite();
  if (satelliteButton) {
    satelliteButton.disabled = !satelliteAvailable;
    if (!satelliteAvailable) satelliteButton.title = 'Satellite basemap requires Mapbox configuration.';
  }
  if (!satelliteAvailable && status) status.textContent = 'Satellite basemap requires Mapbox configuration.';

  const updateMode = mode => {
    const selected = basemaps.setMode(map, mode);
    if (satelliteButton) satelliteButton.setAttribute('aria-pressed', selected === 'satellite' ? 'true' : 'false');
    streetsButton.setAttribute('aria-pressed', selected === 'streets' ? 'true' : 'false');
    if (currentLabel) currentLabel.textContent = selected === 'satellite' ? 'Mapbox Satellite' : 'OpenStreetMap';
    if (status && satelliteAvailable) status.textContent = '';
  };

  if (satelliteButton) satelliteButton.addEventListener('click', () => updateMode('satellite'));
  streetsButton.addEventListener('click', () => updateMode('streets'));
  updateMode(basemaps.defaultMode());
}

function setupLocationSearch(map, selectionManager) {
  const form = document.getElementById('location-search-form');
  const input = document.getElementById('location-search-input');
  const resultsNode = document.getElementById('location-search-results');
  const statusNode = document.getElementById('location-search-status');
  if (!form || !input || !resultsNode || !statusNode) return;

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const query = input.value.trim();
    resultsNode.replaceChildren();
    if (!query) {
      statusNode.textContent = 'Enter a place name or latitude, longitude.';
      return;
    }
    statusNode.textContent = 'Searching…';
    try {
      const response = await fetch(`/api/locations/search?q=${encodeURIComponent(query)}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Place search is temporarily unavailable. You can still enter coordinates or select an area directly on the map.');
      const results = Array.isArray(payload.results) ? payload.results : [];
      if (!results.length) {
        statusNode.textContent = 'No locations found. You can still enter coordinates or select an area directly on the map.';
        return;
      }
      statusNode.textContent = `${results.length} location${results.length === 1 ? '' : 's'} found.`;
      results.forEach(result => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'location-result';
        button.textContent = result.name;
        button.addEventListener('click', () => {
          const lat = Number(result.lat), lon = Number(result.lon);
          if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
          selectionManager.setMode('click');
          map.flyTo({ center: [lon, lat], zoom: Math.min(10, Math.max(8, map.getZoom())), duration: 1100 });
          selectionManager.handleClickPoint(lon, lat);
        });
        resultsNode.appendChild(button);
      });
    } catch (error) {
      statusNode.textContent = error.message || 'Place search is temporarily unavailable. You can still enter coordinates or select an area directly on the map.';
    }
  });
}

/**
 * "Find Demo Area" Selector Setup
 */
function setupFindDemoArea(map, selectionManager, inspector) {
  const selectElem = document.getElementById('select-demo-area');
  if (!selectElem) return;

  const aoiBboxes = {
    'aoi_real_001': [[-91.75, 30.25], [-91.55, 30.43]],
    'aoi_synth_alpha': [[-25.5, 14.8], [-24.8, 15.4]],
    'aoi_synth_beta': [[9.5, -15.5], [10.3, -14.7]],
    'aoi_synth_gamma': [[44.5, 29.5], [45.3, 30.3]],
    'aoi_synth_delta': [[-60.5, -20.5], [-59.7, -19.7]]
  };

  const aoiGeoms = {
    'aoi_real_001': { type: 'Polygon', coordinates: [[[-91.75, 30.25], [-91.55, 30.25], [-91.55, 30.43], [-91.75, 30.43], [-91.75, 30.25]]] },
    'aoi_synth_alpha': { type: 'Polygon', coordinates: [[[-25.5, 14.8], [-24.8, 14.8], [-24.8, 15.4], [-25.5, 15.4], [-25.5, 14.8]]] },
    'aoi_synth_beta': { type: 'Polygon', coordinates: [[[9.5, -15.5], [10.3, -15.5], [10.3, -14.7], [9.5, -14.7], [9.5, -15.5]]] },
    'aoi_synth_gamma': { type: 'Polygon', coordinates: [[[44.5, 29.5], [45.3, 29.5], [45.3, 30.3], [44.5, 30.3], [44.5, 29.5]]] },
    'aoi_synth_delta': { type: 'Polygon', coordinates: [[[-60.5, -20.5], [-59.7, -20.5], [-59.7, -19.7], [-60.5, -19.7], [-60.5, -20.5]]] }
  };

  window.selectDemoAOI = (aoiId) => {
    if (selectElem) selectElem.value = aoiId;
    const bbox = aoiBboxes[aoiId];
    if (bbox) {
      map.fitBounds(bbox, {
        padding: 80,
        maxZoom: 9,
        duration: 1200
      });
    }
    highlightAOI(aoiId);
    triggerInspectionByAoiId(aoiId, aoiGeoms[aoiId]);
  };

  selectElem.addEventListener('change', (e) => {
    const aoiId = e.target.value;
    if (aoiId && aoiBboxes[aoiId]) {
      window.selectDemoAOI(aoiId);
    }
  });
}

/**
 * Layer Visibility Checkboxes
 */
function setupLayerToggles(map) {
  const preferences = window.NisarPreferences;
  const groups = [
    { id: 'layer-toggle-real-changes', key: 'real-change-regions', layers: ['real-change-regions-fill', 'real-change-regions-line'], fallback: preferences ? !!preferences.get('showChangeRegions') : true, preference: 'showChangeRegions' },
    { id: 'layer-toggle-real-aois', key: 'real-analysis-aois', layers: ['real-analysis-aois-fill', 'real-analysis-aois-line', 'real-analysis-aois-highlight'], fallback: preferences ? !!preferences.get('showAois') : true, preference: 'showAois' },
    { id: 'layer-toggle-synthetic-aois', key: 'synthetic-aois', layers: ['synthetic-aois-fill', 'synthetic-aois-line', 'synthetic-aois-highlight'], fallback: false },
    { id: 'layer-toggle-synthetic-changes', key: 'synthetic-change-regions', layers: ['synthetic-change-regions-fill', 'synthetic-change-regions-line'], fallback: false },
    { id: 'layer-toggle-footprints', key: 'footprints', layers: ['nisar-footprints-fill', 'nisar-footprints-line'], fallback: preferences ? !!preferences.get('showFootprints') : false, preference: 'showFootprints' },
    { id: 'layer-toggle-selection', key: 'selection', layers: ['user-selection-point-halo', 'user-selection-point-core', 'user-selection-poly-fill', 'user-selection-poly-line'], fallback: true }
  ];

  groups.forEach(group => {
    const toggle = document.getElementById(group.id);
    if (!toggle) return;
    const saved = localStorage.getItem(`nisar-map-layer-${group.key}`);
    toggle.checked = saved === null ? group.fallback : saved === 'true';
    const apply = () => {
      const visibility = toggle.checked ? 'visible' : 'none';
      group.layers.forEach(id => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visibility); });
      localStorage.setItem(`nisar-map-layer-${group.key}`, String(toggle.checked));
      if (group.preference && preferences) preferences.set(group.preference, toggle.checked);
    };
    apply();
    toggle.addEventListener('change', apply);
  });
}

/**
 * Checks for query parameters in the URL (e.g., ?aoi=aoi_synth_alpha)
 */
function checkUrlParameters(map, inspector) {
  try {
    const params = new URLSearchParams(window.location.search);
    const targetAoi = params.get('aoi');
    if (targetAoi && window.selectDemoAOI) {
      setTimeout(() => {
        window.selectDemoAOI(targetAoi);
      }, 500);
    }
  } catch (e) {
    console.warn('[Map URL State] Error reading URL parameters:', e);
  }
}
