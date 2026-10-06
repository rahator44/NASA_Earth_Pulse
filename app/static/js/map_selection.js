/**
 * NISAR Surface Change Explorer
 * Map Selection Tooling
 *
 * Implements lightweight, framework-free MapLibre GL interaction:
 * - Click Location (Point selection)
 * - Draw Rectangle (2-click bounding box)
 * - Draw Polygon (multi-point vertex drawing, double-click or button to complete)
 * - Clear Selection
 */

class MapSelectionManager {
  constructor(map, options = {}) {
    this.map = map;
    this.onSelect = options.onSelect || (() => {});
    this.onClear = options.onClear || (() => {});

    this.currentMode = 'click'; // 'click' | 'rectangle' | 'polygon'
    
    // Rectangle drawing state
    this.rectStart = null;
    this.isDrawingRect = false;

    // Polygon drawing state
    this.polygonPoints = [];
    this.isDrawingPolygon = false;

    this.initSourcesAndLayers();
    this.bindMapEvents();
  }

  initSourcesAndLayers() {
    // 1. Point selection source & layer
    if (!this.map.getSource('user-selection')) {
      this.map.addSource('user-selection', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      });

      this.map.addLayer({
        id: 'user-selection-point-halo',
        type: 'circle',
        source: 'user-selection',
        paint: {
          'circle-radius': 10,
          'circle-color': '#1E6BFF',
          'circle-opacity': 0.35,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#60A5FA'
        }
      });

      this.map.addLayer({
        id: 'user-selection-point-core',
        type: 'circle',
        source: 'user-selection',
        paint: {
          'circle-radius': 4.5,
          'circle-color': '#FFFFFF',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#1E6BFF'
        }
      });
    }

    // 2. Polygon/Rectangle selection source & layers
    if (!this.map.getSource('user-selection-poly')) {
      this.map.addSource('user-selection-poly', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
      });

      this.map.addLayer({
        id: 'user-selection-poly-fill',
        type: 'fill',
        source: 'user-selection-poly',
        paint: {
          'fill-color': '#1E6BFF',
          'fill-opacity': 0.18
        }
      });

      this.map.addLayer({
        id: 'user-selection-poly-line',
        type: 'line',
        source: 'user-selection-poly',
        paint: {
          'line-color': '#60A5FA',
          'line-width': 2,
          'line-dasharray': [2, 2]
        }
      });
    }
  }

  setMode(mode) {
    this.cancelActiveDrawing();
    this.currentMode = mode;

    const canvas = this.map.getCanvas();
    if (mode === 'rectangle' || mode === 'polygon') {
      canvas.style.cursor = 'crosshair';
    } else {
      canvas.style.cursor = '';
    }

    // Update toolbar buttons
    ['click', 'rectangle', 'polygon'].forEach(m => {
      const btn = document.getElementById(`tool-${m}`);
      if (btn) {
        const isActive = (m === mode);
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        if (isActive) {
          btn.classList.add('bg-[#1E6BFF]', 'text-white', 'border-[#1E6BFF]');
          btn.classList.remove('btn-secondary');
        } else {
          btn.classList.remove('bg-[#1E6BFF]', 'text-white', 'border-[#1E6BFF]');
          btn.classList.add('btn-secondary');
        }
      }
    });

    this.updateInstructionBanner();
  }

  updateInstructionBanner() {
    const banner = document.getElementById('map-interaction-hint');
    if (!banner) return;

    if (this.currentMode === 'rectangle') {
      if (!this.isDrawingRect) {
        banner.textContent = 'Mode: Draw Rectangle — Click first corner on map.';
      } else {
        banner.textContent = 'Click second corner to complete rectangle.';
      }
      banner.classList.remove('hidden');
    } else if (this.currentMode === 'polygon') {
      if (this.polygonPoints.length === 0) {
        banner.textContent = 'Mode: Draw Polygon — Click map to place first vertex.';
      } else {
        banner.textContent = `Placing vertex ${this.polygonPoints.length + 1} — Double click to finish polygon.`;
      }
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }
  }

  cancelActiveDrawing() {
    this.isDrawingRect = false;
    this.rectStart = null;
    this.isDrawingPolygon = false;
    this.polygonPoints = [];
    this.updateInstructionBanner();
  }

  bindMapEvents() {
    // Single Click Handling
    this.map.on('click', (e) => {
      // Check if user clicked an existing Change Region or Demo AOI
      const bbox = [
        [e.point.x - 3, e.point.y - 3],
        [e.point.x + 3, e.point.y + 3]
      ];
      
      if (this.currentMode === 'click') {
        this.handleClickPoint(e.lngLat.lng, e.lngLat.lat);
      } else if (this.currentMode === 'rectangle') {
        this.handleRectangleClick(e.lngLat.lng, e.lngLat.lat);
      } else if (this.currentMode === 'polygon') {
        this.handlePolygonClick(e.lngLat.lng, e.lngLat.lat);
      }
    });

    // Mouse Move Handling for Drawing Previews
    this.map.on('mousemove', (e) => {
      if (this.isDrawingRect && this.rectStart) {
        this.updateRectanglePreview(e.lngLat.lng, e.lngLat.lat);
      } else if (this.isDrawingPolygon && this.polygonPoints.length > 0) {
        this.updatePolygonPreview(e.lngLat.lng, e.lngLat.lat);
      }
    });

    // Double Click to finish Polygon
    this.map.on('dblclick', (e) => {
      if (this.currentMode === 'polygon' && this.polygonPoints.length >= 3) {
        e.preventDefault();
        this.finishPolygon();
      }
    });
  }

  formatCoordDisplay(lng, lat) {
    const latStr = `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? 'N' : 'S'}`;
    const lonStr = `${Math.abs(lng).toFixed(4)}° ${lng >= 0 ? 'E' : 'W'}`;
    return `${latStr}, ${lonStr}`;
  }

  // 1. POINT CLICK MODE
  handleClickPoint(lng, lat) {
    // Clear polygon
    this.clearPolygon();

    // Place point
    const pointGeoJSON = {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties: {}
      }]
    };
    this.map.getSource('user-selection').setData(pointGeoJSON);

    const coordsDisplay = this.formatCoordDisplay(lng, lat);
    this.onSelect({
      geometry: { type: 'Point', coordinates: [lng, lat] },
      selection_type: 'point',
      coordinates_display: coordsDisplay
    });
  }

  // 2. RECTANGLE DRAW MODE
  handleRectangleClick(lng, lat) {
    if (!this.isDrawingRect) {
      // First corner
      this.isDrawingRect = true;
      this.rectStart = [lng, lat];
      this.clearPoint();
      this.updateInstructionBanner();
    } else {
      // Second corner — finalize
      const start = this.rectStart;
      const end = [lng, lat];
      this.isDrawingRect = false;
      this.rectStart = null;
      this.updateInstructionBanner();

      const polyCoordinates = [
        [start[0], start[1]],
        [end[0], start[1]],
        [end[0], end[1]],
        [start[0], end[1]],
        [start[0], start[1]]
      ];

      const polyGeoJSON = {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [polyCoordinates] },
          properties: {}
        }]
      };
      this.map.getSource('user-selection-poly').setData(polyGeoJSON);

      const latMid = (start[1] + end[1]) / 2.0;
      const lngMid = (start[0] + end[0]) / 2.0;
      const coordsDisplay = `Box Centroid: ${this.formatCoordDisplay(lngMid, latMid)}`;

      this.onSelect({
        geometry: { type: 'Polygon', coordinates: [polyCoordinates] },
        selection_type: 'rectangle',
        coordinates_display: coordsDisplay
      });
    }
  }

  updateRectanglePreview(currLng, currLat) {
    if (!this.rectStart) return;
    const start = this.rectStart;
    const polyCoordinates = [
      [start[0], start[1]],
      [currLng, start[1]],
      [currLng, currLat],
      [start[0], currLat],
      [start[0], start[1]]
    ];

    this.map.getSource('user-selection-poly').setData({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [polyCoordinates] },
        properties: {}
      }]
    });
  }

  // 3. POLYGON DRAW MODE
  handlePolygonClick(lng, lat) {
    this.clearPoint();
    this.isDrawingPolygon = true;
    this.polygonPoints.push([lng, lat]);
    this.updateInstructionBanner();

    // If 3+ vertices, user can close polygon by clicking near start point (within small delta)
    if (this.polygonPoints.length > 3) {
      const first = this.polygonPoints[0];
      const dLng = Math.abs(lng - first[0]);
      const dLat = Math.abs(lat - first[1]);
      if (dLng < 0.2 && dLat < 0.2) {
        // remove duplicate click and finish
        this.polygonPoints.pop();
        this.finishPolygon();
        return;
      }
    }

    // Render current vertices/lines
    const previewCoords = [...this.polygonPoints, this.polygonPoints[0]];
    this.map.getSource('user-selection-poly').setData({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [previewCoords] },
        properties: {}
      }]
    });
  }

  updatePolygonPreview(currLng, currLat) {
    if (this.polygonPoints.length === 0) return;
    const previewCoords = [...this.polygonPoints, [currLng, currLat], this.polygonPoints[0]];
    this.map.getSource('user-selection-poly').setData({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [previewCoords] },
        properties: {}
      }]
    });
  }

  finishPolygon() {
    if (this.polygonPoints.length < 3) {
      this.cancelActiveDrawing();
      return;
    }

    const closedRing = [...this.polygonPoints, this.polygonPoints[0]];
    this.isDrawingPolygon = false;
    const pts = [...this.polygonPoints];
    this.polygonPoints = [];
    this.updateInstructionBanner();

    this.map.getSource('user-selection-poly').setData({
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [closedRing] },
        properties: {}
      }]
    });

    // Approximate centroid
    const lats = pts.map(p => p[1]);
    const lngs = pts.map(p => p[0]);
    const latMid = (Math.min(...lats) + Math.max(...lats)) / 2.0;
    const lngMid = (Math.min(...lngs) + Math.max(...lngs)) / 2.0;
    const coordsDisplay = `Polygon Centroid: ${this.formatCoordDisplay(lngMid, latMid)}`;

    this.onSelect({
      geometry: { type: 'Polygon', coordinates: [closedRing] },
      selection_type: 'polygon',
      coordinates_display: coordsDisplay
    });
  }

  // 4. CLEAR SELECTION
  clear() {
    this.cancelActiveDrawing();
    this.clearPoint();
    this.clearPolygon();
    this.setMode('click');
    this.onClear();
  }

  clearPoint() {
    const pointSource = this.map.getSource('user-selection');
    if (pointSource) {
      pointSource.setData({ type: 'FeatureCollection', features: [] });
    }
  }

  clearPolygon() {
    const polySource = this.map.getSource('user-selection-poly');
    if (polySource) {
      polySource.setData({ type: 'FeatureCollection', features: [] });
    }
  }

  // Programmatic Polygon Display (e.g. for highlighting a selected AOI)
  displayPolygon(coordinates, coordsDisplay = '') {
    this.clearPoint();
    this.cancelActiveDrawing();
    const polySource = this.map.getSource('user-selection-poly');
    if (polySource) {
      polySource.setData({
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: coordinates },
          properties: {}
        }]
      });
    }
  }
}

window.MapSelectionManager = MapSelectionManager;
