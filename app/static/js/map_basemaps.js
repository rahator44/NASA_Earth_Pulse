/** Shared basemap configuration for every MapLibre map in the application. */
(function (global) {
  'use strict';

  const OSM_SOURCE_ID = 'osm-basemap';
  const OSM_LAYER_ID = 'osm-basemap-layer';
  const SATELLITE_SOURCE_ID = 'mapbox-satellite';
  const SATELLITE_LAYER_ID = 'satellite-basemap';
  const rawToken = typeof global.MAPBOX_PUBLIC_TOKEN === 'string'
    ? global.MAPBOX_PUBLIC_TOKEN.trim()
    : '';
  const publicToken = /^pk\.[A-Za-z0-9._~-]{20,2048}$/.test(rawToken) ? rawToken : '';

  const osmSource = {
    type: 'raster',
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    tileSize: 256,
    maxzoom: 19,
    attribution: '© OpenStreetMap contributors'
  };

  function createStyle() {
    // OSM is always present underneath the optional satellite layer.  This
    // guarantees that every map retains a visible street-map fallback even
    // when a Mapbox token is invalid or satellite tile requests fail.
    const sources = { [OSM_SOURCE_ID]: osmSource };
    const layers = [{
      id: OSM_LAYER_ID,
      type: 'raster',
      source: OSM_SOURCE_ID,
      layout: { visibility: 'visible' },
      minzoom: 0,
      maxzoom: 19
    }];

    if (publicToken) {
      sources[SATELLITE_SOURCE_ID] = {
        type: 'raster',
        tiles: [`https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg90?access_token=${encodeURIComponent(publicToken)}`],
        tileSize: 512,
        maxzoom: 19,
        attribution: '© Mapbox © OpenStreetMap contributors'
      };
      layers.push({
        id: SATELLITE_LAYER_ID,
        type: 'raster',
        source: SATELLITE_SOURCE_ID,
        layout: { visibility: 'visible' },
        minzoom: 0,
        maxzoom: 19
      });
    }
    return { version: 8, sources, layers };
  }

  function defaultMode() {
    return publicToken ? 'satellite' : 'streets';
  }

  function canUseSatellite() {
    return Boolean(publicToken);
  }

  function setMode(map, mode) {
    const useSatellite = mode === 'satellite' && canUseSatellite();
    // Keep OSM visible underneath satellite so a failed raster request never
    // leaves a black/empty map canvas.
    const streets = map.getLayer(OSM_LAYER_ID);
    if (streets) map.setLayoutProperty(OSM_LAYER_ID, 'visibility', 'visible');
    const satellite = map.getLayer(SATELLITE_LAYER_ID);
    if (satellite) map.setLayoutProperty(SATELLITE_LAYER_ID, 'visibility', useSatellite ? 'visible' : 'none');
    return useSatellite ? 'satellite' : 'streets';
  }

  function showFallbackNotice(map) {
    const container = map.getContainer();
    let notice = container.querySelector('[data-basemap-fallback]');
    if (!notice) {
      notice = document.createElement('div');
      notice.dataset.basemapFallback = 'true';
      notice.className = 'basemap-fallback-notice';
      notice.textContent = 'Satellite basemap unavailable — using OpenStreetMap.';
      container.appendChild(notice);
    }
  }

  function bindFallback(map, onFallback) {
    let switched = false;
    map.on('error', event => {
      const sourceId = event && (event.sourceId || (event.source && event.source.id));
      const errorText = String((event && event.error && (event.error.message || event.error)) || '');
      const isSatelliteError = sourceId === SATELLITE_SOURCE_ID || /api\.mapbox\.com|mapbox-satellite/i.test(errorText);
      if (!canUseSatellite() || switched || !isSatelliteError) return;
      switched = true;
      setMode(map, 'streets');
      showFallbackNotice(map);
      if (typeof onFallback === 'function') onFallback();
    });
  }

  global.NisarBasemaps = Object.freeze({
    createStyle,
    defaultMode,
    canUseSatellite,
    setMode,
    bindFallback,
    ids: Object.freeze({ osmSource: OSM_SOURCE_ID, osmLayer: OSM_LAYER_ID, satelliteSource: SATELLITE_SOURCE_ID, satelliteLayer: SATELLITE_LAYER_ID })
  });
})(window);
