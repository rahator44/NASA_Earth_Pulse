/**
 * NISAR Surface Change Explorer - Evidence Viewer Component
 * Handles interactive Before/After swipe divider, layer mode toggles,
 * and overlay opacity control.
 */

window.initEvidenceViewer = function(config) {
  return {
    analysisId: config.analysisId || '',
    mode: config.initialMode || 'swipe', // 'swipe', 'before', 'after', 'difference', 'mask'
    dividerPos: 50, // 0 to 100 percent
    opacity: 70, // 0 to 100 percent for overlay modes
    hasBefore: config.hasBefore || false,
    hasAfter: config.hasAfter || false,
    hasDifference: config.hasDifference || false,
    hasMask: config.hasMask || false,
    qualityGatePassed: config.qualityGatePassed !== false,
    qualityNotes: config.qualityNotes || '',
    isDragging: false,
    showLegend: true,
    showMetadata: false,

    init() {
      // If incomplete pair or quality gate failed, fallback appropriately
      if (!this.qualityGatePassed || !this.hasAfter) {
        if (this.hasBefore) {
          this.mode = 'before';
        }
      }

      // Re-initialize Lucide icons in case dynamic markup rendered
      if (window.lucide && typeof window.lucide.createIcons === 'function') {
        this.$nextTick(() => window.lucide.createIcons());
      }
    },

    setMode(newMode) {
      if (newMode === 'swipe' && (!this.hasBefore || !this.hasAfter)) return;
      if (newMode === 'difference' && (!this.hasDifference || !this.qualityGatePassed)) return;
      if (newMode === 'mask' && (!this.hasMask || !this.qualityGatePassed)) return;
      if (newMode === 'after' && !this.hasAfter) return;
      if (newMode === 'before' && !this.hasBefore) return;

      this.mode = newMode;
      if (window.lucide && typeof window.lucide.createIcons === 'function') {
        this.$nextTick(() => window.lucide.createIcons());
      }
    },

    startDrag(e) {
      if (this.mode !== 'swipe') return;
      this.isDragging = true;
      e.target.setPointerCapture?.(e.pointerId);
      this.handleDrag(e);
    },

    onDrag(e) {
      if (!this.isDragging || this.mode !== 'swipe') return;
      this.handleDrag(e);
    },

    stopDrag(e) {
      this.isDragging = false;
      try {
        e.target.releasePointerCapture?.(e.pointerId);
      } catch (_) {}
    },

    handleDrag(e) {
      const frame = this.$refs.viewerFrame;
      if (!frame) return;

      const rect = frame.getBoundingClientRect();
      const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      const relativeX = clientX - rect.left;
      let pct = (relativeX / rect.width) * 100;
      
      // Clamp between 0% and 100%
      if (pct < 0) pct = 0;
      if (pct > 100) pct = 100;
      
      this.dividerPos = Math.round(pct * 10) / 10;
    },

    stepDivider(delta) {
      if (this.mode !== 'swipe') return;
      let nextPos = this.dividerPos + delta;
      if (nextPos < 0) nextPos = 0;
      if (nextPos > 100) nextPos = 100;
      this.dividerPos = nextPos;
    },

    resetDivider() {
      this.dividerPos = 50;
    }
  };
};

/**
 * Scientist Image Lab Workspace Controller
 */
window.initLabWorkspace = function(config) {
  return {
    tab: 'distribution',
    currentThreshold: config.defaultThreshold !== undefined ? config.defaultThreshold : 0,
    defaultThreshold: config.defaultThreshold !== undefined ? config.defaultThreshold : 0,
    hasThreshold: config.hasThreshold || false,
    thresholdUnit: config.thresholdUnit || '',
    thresholdDirection: config.thresholdDirection || 'below_threshold',
    previewStates: config.previewStates || [],
    activeChannel: config.activeChannel || 'HH',
    channelNotice: '',
    qualityMaskActive: false,
    qualityMaskUrl: config.qualityMaskUrl || '',
    cursorX: '--',
    cursorY: '--',

    init() {
      // Default tab fallback if no histogram
      if (!config.hasHistogram) {
        this.tab = 'quality';
      }
      this.$watch('currentThreshold', () => {
        this.updateActiveMask();
      });
    },

    get isPreviewMode() {
      return this.hasThreshold && Math.abs(this.currentThreshold - this.defaultThreshold) > 0.001;
    },

    selectChannel(chan) {
      this.activeChannel = chan;
      if (chan !== config.activeChannel) {
        this.channelNotice = 'Additional channel visualization is not stored for this demo.';
      } else {
        this.channelNotice = '';
      }
    },

    resetThreshold() {
      this.currentThreshold = this.defaultThreshold;
      this.updateActiveMask();
    },

    updateActiveMask() {
      if (!this.previewStates || this.previewStates.length === 0) return;
      let closest = this.previewStates[0];
      let minDiff = Math.abs(closest.threshold_value - this.currentThreshold);
      for (const st of this.previewStates) {
        const diff = Math.abs(st.threshold_value - this.currentThreshold);
        if (diff < minDiff) {
          minDiff = diff;
          closest = st;
        }
      }
      // Query mask image if rendered
      const maskImgs = document.querySelectorAll('img[alt*="change mask" i], img[alt*="Detected change mask" i]');
      maskImgs.forEach(img => {
        if (closest.mask_url) img.src = closest.mask_url;
      });
    },

    getThresholdX(val, minBin, maxBin) {
      if (minBin === undefined || maxBin === undefined || maxBin <= minBin) return 270;
      let ratio = (val - minBin) / (maxBin - minBin);
      if (ratio < 0) ratio = 0;
      if (ratio > 1) ratio = 1;
      return Math.round(ratio * 520) + 10;
    },

    onViewerMouseMove(e) {
      const target = e.currentTarget;
      if (!target) return;
      const rect = target.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      this.cursorX = Math.max(0, Math.min(100, Math.round(x * 10) / 10));
      this.cursorY = Math.max(0, Math.min(100, Math.round(y * 10) / 10));
    }
  };
};
