/**
 * NISAR Surface Change Explorer
 * Area Inspector Component Handler
 *
 * Implements two clearly separated sections:
 * 1. PROCESSED ANALYSIS (Step 5 stored analysis)
 *    - State 1: Nothing Selected
 *    - State 2: Loading (Skeleton)
 *    - State 3: Analysis Found (Observation state != domain)
 *    - State 4: Unknown / Unclassified (Neutral candidate hypotheses)
 *    - State 5: Insufficient Data (Separated from No Change)
 *    - State 6: No Change under the current analysis criteria
 *    - State 7: No Stored Analysis (NOT an observation state!)
 * 2. NISAR COVERAGE (Step 6 live metadata discovery via ASF DAAC)
 *    - Lazy loaded with [CHECK NISAR COVERAGE] button
 *    - AVAILABLE / NO_RESULTS / SERVICE_UNAVAILABLE / SEARCH_AREA_TOO_LARGE
 *    - GCOV, GUNW, GOFF product & maturity breakdown (PROVISIONAL vs BETA)
 *    - Available analysis types
 *    - Expandable acquisition granule table (no downloads)
 *    - Expandable GCOV 9-point comparison pair candidates
 */

class AreaInspector {
  constructor(containerId = 'area-inspector-content') {
    this.container = document.getElementById(containerId);
    this.lastRequest = null;
    this.lastGeometry = null;
    this.lastCoverageResponse = null;
    this.hasProcessedAnalysis = false;
  }

  escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  buildSituationContent(situation) {
    if (!situation) return '';
    const esc = value => this.escapeHtml(value);
    const rows = (items, empty) => items?.length
      ? `<ul class="list-disc pl-5 space-y-1">${items.map(item => `<li>${esc(item.description_public)}</li>`).join('')}</ul>`
      : `<p class="text-[#64748B]">${empty}</p>`;
    const interpretations = (situation.interpretations || []).map(item => `
      <div class="p-2.5 bg-[#090D14] border border-[#1E2838]">
        <div class="flex items-center justify-between gap-2"><div class="text-xs text-white font-medium">${esc(item.public_label)}</div><span class="type-metadata">${esc((item.status || '').toUpperCase())}</span></div>
        <p class="text-[11px] text-[#CBD5E1] mt-1">${esc(item.description)}</p>
        ${item.public_reason ? `<div class="mt-2"><div class="type-metadata text-[#60A5FA]">WHY THIS INTERPRETATION?</div><p class="text-[11px] text-[#94A3B8] mt-1">${esc(item.public_reason)}</p></div>` : ''}
        ${(item.alternative_explanations || []).length ? `<div class="mt-2"><div class="type-metadata">OTHER POSSIBLE EXPLANATIONS</div><ul class="list-disc pl-5 text-[11px] text-[#94A3B8] mt-1">${item.alternative_explanations.map(alt => `<li>${esc(alt)}</li>`).join('')}</ul></div>` : ''}
        <div class="scientist-only type-metadata mt-2">RULE ${esc(item.rule_id || 'N/A')} · ${esc(item.reason || '')}</div>
      </div>`).join('');
    const quality = situation.data_quality || {};
    return `<section class="space-y-3 border border-[#1E6BFF]/30 bg-[#0B1220] p-3" aria-label="What NISAR observed">
      <div class="type-metadata text-[#60A5FA]">WHAT NISAR OBSERVED · ${esc(situation.human_label)}</div>
      ${situation.human_label === 'DEMO INTERPRETATION' ? '<p class="text-[11px] text-amber-200 border border-amber-900/50 p-2">Synthetic development fixture — not an Earth observation result.</p>' : ''}
      <h3 class="text-base text-white font-semibold">${esc(situation.headline)}</h3>
      <p class="text-xs text-[#CBD5E1]">${esc(situation.what_changed)}</p>
      <div><h4 class="type-metadata mb-1">WHAT DID NISAR MEASURE?</h4><p class="text-xs text-[#CBD5E1]">${esc(situation.what_nisar_measured)}</p></div>
      ${situation.technical_metadata ? `<div class="p-2.5 bg-[#090D14] border border-[#1E2838] space-y-1.5"><h4 class="type-metadata">HOW TO READ THE NISAR DATA</h4><div class="text-xs text-white font-medium">${esc(situation.technical_metadata.product_name_public || 'NISAR science product')}${situation.technical_metadata.product_code ? ` <span class="text-[#64748B] font-mono">(${esc(situation.technical_metadata.product_code)})</span>` : ''}</div>${situation.technical_metadata.product_explanation ? `<p class="text-[11px] text-[#94A3B8]">${esc(situation.technical_metadata.product_explanation)}</p>` : ''}<div class="grid sm:grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-[#CBD5E1]">${situation.technical_metadata.orbit_direction_public ? `<div><span class="text-[#64748B]">Pass:</span> ${esc(situation.technical_metadata.orbit_direction_public)}</div>` : ''}${situation.technical_metadata.maturity_label ? `<div><span class="text-[#64748B]">Data maturity:</span> ${esc(situation.technical_metadata.maturity_label)}</div>` : ''}${(situation.technical_metadata.polarizations || []).length ? `<div class="sm:col-span-2"><span class="text-[#64748B]">Radar channels:</span> ${(situation.technical_metadata.polarizations || []).map((pol, i) => `${esc(pol)}${situation.technical_metadata.polarization_explanations?.[i] ? ` — ${esc(situation.technical_metadata.polarization_explanations[i])}` : ''}`).join('; ')}</div>` : ''}</div></div>` : ''}
      <div><h4 class="type-metadata mb-1">WHAT COULD THIS MEAN?</h4><div class="space-y-1">${interpretations || '<p class="text-xs text-[#94A3B8]">The stored evidence does not support a more specific physical interpretation.</p>'}</div></div>
      <div class="grid sm:grid-cols-2 gap-2 text-xs">
        <div><h4 class="type-metadata mb-1">DIRECT NISAR EVIDENCE</h4>${rows(situation.direct_evidence, 'No direct measurement details are stored.')}</div>
        <div><h4 class="type-metadata mb-1">SUPPORTING EARTH-OBSERVATION EVIDENCE</h4>${rows(situation.supporting_evidence, 'No independent supporting evidence is stored.')}</div>
      </div>
      ${situation.context?.length ? `<div><h4 class="type-metadata mb-1">CONTEXT</h4>${rows(situation.context, '')}</div>` : ''}
      <div class="p-2 bg-[#090D14] border border-[#1E2838]"><h4 class="type-metadata mb-1">DATA QUALITY · ${esc(quality.status || 'Not assessed')}</h4><p class="text-xs text-[#CBD5E1]">${esc(quality.explanation || 'No quality assessment is stored.')}${quality.valid_pixel_percent !== undefined ? ` ${esc(quality.valid_pixel_percent)}% of selected radar pixels were usable.` : ''}</p></div>
      <div><h4 class="type-metadata mb-1">WHAT WE CANNOT SAY</h4>${rows((situation.what_we_cannot_say || []).map(text => ({description_public:text})), 'No additional limitations are stored.')}</div>
      <details class="scientist-only border-t border-[#1E2838] pt-2"><summary class="type-metadata cursor-pointer">SCIENTIST METADATA</summary><div class="mt-2 text-[10px] text-[#94A3B8] break-all space-y-1">
        <div>Product ${esc(situation.technical_metadata?.product_code || '')} · Maturity ${esc(situation.technical_metadata?.maturity_code || '')} · Track ${esc(situation.technical_metadata?.track ?? '')} · Frame ${esc(situation.technical_metadata?.frame ?? '')}</div>
        <div>Before: ${esc(situation.technical_metadata?.before_granule_id || '')}</div><div>After: ${esc(situation.technical_metadata?.after_granule_id || '')}</div>
        <div>Orbit ${esc(situation.technical_metadata?.orbit_direction || '')} · Mode ${esc(situation.technical_metadata?.mode || '')} · Polarizations ${esc((situation.technical_metadata?.polarizations || []).join('/'))} · CRID ${esc(situation.technical_metadata?.crid || '')}</div>
        <div>Processing version ${esc(situation.technical_metadata?.processing_version || 'not recorded')} · Analysis pipeline ${esc(situation.technical_metadata?.analysis_pipeline_version || '')} · Manifest ${esc(situation.manifest_id || '')}</div>
        <div>Recorded dataset path: ${esc(situation.technical_metadata?.dataset_path || 'not stored')}</div>
        <div>Comparison ${esc(situation.technical_metadata?.comparison_policy || '')} · Threshold/quality: ${esc(JSON.stringify(situation.technical_metadata?.quality_parameters || {}))} · Detection: ${esc(JSON.stringify(situation.technical_metadata?.detection_parameters || {}))}</div>
      </div></details>
    </section>`;
  }

  setLastRequest(fn) {
    this.lastRequest = fn;
  }

  setLastGeometry(geom) {
    this.lastGeometry = geom;
  }

  retryLastRequest() {
    if (typeof this.lastRequest === 'function') {
      this.lastRequest();
    }
  }

  // STATE 1 — NOTHING SELECTED
  renderEmpty() {
    if (!this.container) return;
    this.lastGeometry = null;
    this.lastCoverageResponse = null;
    this.container.innerHTML = `
      <div class="empty-state py-8 px-4 bg-[#090D14] border border-[#1E2838] rounded-[2px]" aria-live="polite">
        <div class="empty-state-icon w-10 h-10 mb-3 mx-auto flex items-center justify-center bg-[#0F141F] border border-[#1E2838] text-[#1E6BFF]">
          <i data-lucide="crosshair" class="w-5 h-5"></i>
        </div>
        <div class="empty-state-title text-xs font-semibold text-white uppercase tracking-wider text-center">No Area Selected</div>
        <p class="empty-state-description text-[12px] text-[#94A3B8] leading-relaxed text-center mt-2">
          Click the map or draw an area to inspect available processed surface-change analyses and query live NISAR archive coverage.
        </p>
      </div>
    `;
    this.refreshIcons();
  }

  // STATE 2 — LOADING
  renderLoading() {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="space-y-4 py-4" aria-live="assertive" aria-busy="true">
        <div class="flex items-center gap-2 text-xs font-mono text-[#60A5FA]">
          <div class="w-3.5 h-3.5 border-2 border-[#1E6BFF] border-t-transparent rounded-full animate-spin"></div>
          <span>Inspecting selected area...</span>
        </div>
        <div class="space-y-2.5 p-3 bg-[#090D14] border border-[#1E2838]">
          <div class="skeleton h-4 w-3/4"></div>
          <div class="skeleton h-3 w-1/2"></div>
          <div class="skeleton h-12 w-full mt-3"></div>
          <div class="skeleton h-3 w-2/3"></div>
        </div>
        <div class="space-y-2">
          <div class="skeleton h-8 w-full"></div>
          <div class="skeleton h-8 w-full"></div>
        </div>
      </div>
    `;
  }

  // ERROR STATE — SOFTWARE/REQUEST ERROR
  renderError(message = 'This request could not be completed.') {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="p-4 bg-[#140D0D] border border-red-900/50 rounded-[2px] space-y-3" aria-live="assertive">
        <div class="flex items-center gap-2 text-red-400">
          <i data-lucide="alert-triangle" class="w-4 h-4"></i>
          <span class="text-xs font-mono font-bold tracking-wider uppercase">Unable to Inspect Area</span>
        </div>
        <p class="text-xs text-[#94A3B8] leading-relaxed">
          ${message}
        </p>
        <div class="pt-2">
          <button type="button" 
                  id="btn-inspector-retry"
                  class="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5 w-full justify-center">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
            <span>Try Again</span>
          </button>
        </div>
      </div>
    `;
    const btnRetry = document.getElementById('btn-inspector-retry');
    if (btnRetry) {
      btnRetry.addEventListener('click', () => this.retryLastRequest());
    }
    this.refreshIcons();
  }

  // MAIN DISPATCH: Process server AreaInspectionResponse
  renderResponse(data) {
    if (!this.container) return;

    // CASE C: NO STORED ANALYSIS (NOT an observation state!)
    if (!data.has_processed_analysis || !data.matches || data.matches.length === 0) {
      this.renderNoAnalysis(data);
      return;
    }

    // MULTIPLE OR SINGLE STORED MATCHES
    this.renderMatches(data);
  }

  // STATE 7 — NO STORED ANALYSIS
  renderNoAnalysis(data) {
    this.hasProcessedAnalysis = false;
    const coords = data.coordinates_display || 'Selected Area';
    this.container.innerHTML = `
      <div class="space-y-4" aria-live="polite">
        
        <!-- Section 1 Header Info -->
        <div class="p-3 bg-[#090D14] border border-[#1E2838] space-y-2">
          <div class="flex items-center justify-between">
            <span class="type-metadata text-[10px] text-[#5C6B80]">COORDINATES</span>
            <span class="font-mono text-xs text-white">${coords}</span>
          </div>
        </div>

        <!-- Strict Case C Notice Banner -->
        <div class="p-4 bg-[#0F141F] border border-[#1E2838] space-y-3 rounded-[2px]">
          <div class="flex items-center gap-2 text-[#94A3B8]">
            <i data-lucide="help-circle" class="w-4 h-4 text-[#5C6B80]"></i>
            <span class="text-xs font-mono font-bold uppercase tracking-wider text-white">No Processed Analysis</span>
          </div>

          <p class="text-xs text-[#94A3B8] leading-relaxed">
            No processed surface-change analysis is available for this selection in the current demo.
          </p>

          <div class="p-2.5 bg-[#090D14] border border-[#1E2838] text-[11px] text-[#CBD5E1] space-y-1">
            <div class="font-semibold text-white flex items-center gap-1.5">
              <span class="w-1.5 h-1.5 rounded-full bg-[#38BDF8]"></span>
              <span>Important Scientific Rule:</span>
            </div>
            <p class="text-[#94A3B8]">
              This does not mean No Change or Insufficient Data. Those are observation states that require processed SAR pairs.
            </p>
          </div>
        </div>

        <!-- Available Actions -->
        <div class="space-y-2">
          <button type="button" 
                  id="btn-goto-demo-area" 
                  class="btn btn-secondary text-xs py-2 px-3 w-full flex items-center justify-center gap-2">
            <i data-lucide="target" class="w-3.5 h-3.5 text-[#1E6BFF]"></i>
            <span>View Demo Areas</span>
          </button>

          <a href="/methods" 
             class="btn btn-secondary text-xs py-2 px-3 w-full flex items-center justify-center gap-2">
            <i data-lucide="book-open" class="w-3.5 h-3.5 text-[#5C6B80]"></i>
            <span>Methods & Validation</span>
          </a>
        </div>

        <!-- Section 2: Real NISAR Archive Coverage Hook -->
        <div id="coverage-section-root">
          ${this.buildCoveragePromptHtml()}
        </div>

      </div>
    `;

    const btnGoto = document.getElementById('btn-goto-demo-area');
    if (btnGoto && window.selectDemoAOI) {
      btnGoto.addEventListener('click', () => {
        window.selectDemoAOI('aoi_synth_alpha');
      });
    }

    this.bindCoverageCheckButton();
    this.refreshIcons();
  }

  // RENDER STORED MATCHES (States 3, 4, 5, 6)
  renderMatches(data) {
    this.hasProcessedAnalysis = true;
    const coords = data.coordinates_display || 'Selected Area';
    const matchCount = data.matches.length;

    let matchesHtml = '';
    data.matches.forEach((match, idx) => {
      matchesHtml += this.buildMatchCard(match, idx, matchCount);
    });

    this.container.innerHTML = `
      <div class="space-y-4" aria-live="polite">
        
        <!-- Selection Header & Synthetic Labeling -->
        <div class="p-3 bg-[#090D14] border border-[#1E2838] space-y-2">
          <div class="flex items-center justify-between text-xs">
            <span class="type-metadata text-[10px] text-[#5C6B80]">SELECTION</span>
            <span class="font-mono text-xs text-white">${coords}</span>
          </div>

          <div class="flex items-center justify-between pt-1 border-t border-[#1E2838]/60">
            <span class="text-[11px] text-[#94A3B8]">
              ${matchCount === 1 ? '1 analyzed area intersects selection' : `${matchCount} analyzed areas intersect selection`}
            </span>
            ${data.matches && data.matches.some(m => !m.is_demo) ? `
              <span class="badge border-[#10B981] bg-[#10B981]/20 text-[#34D399] text-[9px] font-bold uppercase tracking-wider">
                REAL NISAR ANALYSIS
              </span>
            ` : `
              <span class="badge badge-synthetic text-[9px] uppercase tracking-wider" 
                    title="Synthetic development fixture — not an Earth observation result.">
                DEMO FIXTURE
              </span>
            `}
          </div>
        </div>

        <!-- Section 1: Processed Analysis Cards -->
        <div class="space-y-4">
          ${matchesHtml}
        </div>

        <!-- Section 2: Real NISAR Archive Coverage Hook -->
        <div id="coverage-section-root">
          ${this.buildCoveragePromptHtml()}
        </div>

      </div>
    `;

    this.bindCoverageCheckButton();
    this.refreshIcons();
  }

  buildMatchCard(match, idx, total) {
    const isMultiple = total > 1;

    // 1. Observation State Badge & Header
    const stateRaw = match.observation_state_raw;
    const stateBadgeClass = match.observation_state_badge_class || 'badge-state-change';
    const stateLabel = match.observation_state_label || 'OBSERVATION';
    const domainLabel = match.domain_label || 'Unclassified Change';

    // 2. Specific State Content (States 4, 5, 6, 3)
    let stateSpecificContent = '';

    // STATE 4: UNKNOWN CHANGE
    if (stateRaw === 'unknown_change') {
      let candidateList = '';
      if (match.candidates && match.candidates.length > 0) {
        match.candidates.forEach(cand => {
          candidateList += `
            <div class="p-2 bg-[#0F141F] border border-[#1E2838] space-y-1">
              <div class="flex items-center justify-between text-xs">
                <span class="font-semibold text-white">${cand.candidate_domain_label}</span>
                <span class="text-[10px] font-mono text-[#F59E0B]">Hypothesis</span>
              </div>
              <div class="text-[11px] text-[#94A3B8] space-y-0.5">
                <div>• Physical radar signature matched</div>
                <div>• Independent support: not confirmed</div>
              </div>
              ${cand.notes ? `<div class="text-[10px] text-[#64748B] italic pt-1">${cand.notes}</div>` : ''}
            </div>
          `;
        });
      }

      stateSpecificContent = `
        <div class="p-3 bg-[#1A1308] border border-amber-900/40 space-y-2 rounded-[2px]">
          <div class="flex items-center gap-1.5 text-[#F59E0B] text-xs font-semibold">
            <i data-lucide="help-circle" class="w-4 h-4"></i>
            <span>Unusual radar change detected. Cause not identified.</span>
          </div>
          ${match.candidates && match.candidates.length > 0 ? `
            <div class="pt-2 border-t border-amber-900/30 space-y-2">
              <div class="type-metadata text-[10px] text-[#F59E0B]">POSSIBLE INTERPRETATIONS</div>
              <div class="space-y-1.5">
                ${candidateList}
              </div>
              <p class="text-[10px] text-[#94A3B8] italic pt-1">
                Candidate interpretations are not confirmed causes.
              </p>
            </div>
          ` : ''}
        </div>
      `;
    }
    // STATE 5: INSUFFICIENT DATA
    else if (stateRaw === 'insufficient_data') {
      stateSpecificContent = `
        <div class="p-3 bg-[#140D0D] border border-red-900/40 space-y-2 rounded-[2px]">
          <div class="flex items-center gap-1.5 text-red-400 text-xs font-semibold">
            <i data-lucide="alert-circle" class="w-4 h-4"></i>
            <span>INSUFFICIENT DATA</span>
          </div>
          <p class="text-xs text-[#CBD5E1] leading-relaxed">
            Not enough usable data was available to determine surface change for this analysis.
          </p>
          ${match.quality_notes ? `
            <div class="p-2 bg-[#090D14] border border-[#1E2838] text-[11px] font-mono text-[#94A3B8]">
              Reason: ${match.quality_notes}
            </div>
          ` : ''}
        </div>
      `;
    }
    // STATE 6: NO CHANGE
    else if (stateRaw === 'no_change') {
      stateSpecificContent = `
        <div class="p-3 bg-[#0A1612] border border-emerald-900/40 space-y-2 rounded-[2px]">
          <div class="flex items-center gap-1.5 text-emerald-400 text-xs font-semibold">
            <i data-lucide="check-circle" class="w-4 h-4"></i>
            <span>NO CHANGE DETECTED</span>
          </div>
          <p class="text-xs text-[#CBD5E1] leading-relaxed">
            Usable observations were analyzed and no significant surface change was detected under the configured criteria.
          </p>
        </div>
      `;
    }
    // STATE 3: CHANGE DETECTED
    else {
      stateSpecificContent = `
        <div class="p-3 bg-[#081220] border border-[#1E6BFF]/30 space-y-1.5 rounded-[2px]">
          <div class="flex items-center gap-1.5 text-[#38BDF8] text-xs font-semibold">
            <i data-lucide="activity" class="w-4 h-4"></i>
            <span>SURFACE CHANGE DETECTED</span>
          </div>
          ${match.event_description ? `
            <p class="text-xs text-[#CBD5E1] leading-relaxed">
              ${match.event_description}
            </p>
          ` : ''}
        </div>
      `;
    }

    // 3. Primary measurement (withheld for insufficient_data)
    let measurementBlock = '';
    if (match.primary_measurement_label && match.primary_measurement_value && stateRaw !== 'insufficient_data') {
      measurementBlock = `
        <div class="flex items-center justify-between text-xs py-1 border-b border-[#1E2838]/60">
          <span class="type-metadata text-[10px] text-[#5C6B80] uppercase">${match.primary_measurement_label}</span>
          <span class="font-mono text-white font-semibold">${match.primary_measurement_value}</span>
        </div>
      `;
    }

    // 4. Exposure Context (clearly separated from observation, NO review priority)
    let exposureBlock = '';
    if (match.exposure) {
      const exp = match.exposure;
      exposureBlock = `
        <div class="p-2.5 bg-[#090D14] border border-[#1E2838] space-y-1.5 rounded-[2px]">
          <div class="flex items-center justify-between text-[10px]">
            <span class="type-metadata text-[#5C6B80]">EXPOSURE CONTEXT</span>
            <span class="badge badge-synthetic text-[8px]">DEMO FIXTURE</span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
            <div>
              <span class="text-[10px] text-[#5C6B80] block">POPULATION:</span>
              <span class="text-white">${exp.estimated_population !== null && exp.estimated_population !== undefined ? exp.estimated_population.toLocaleString() : 'N/A'}</span>
            </div>
            <div>
              <span class="text-[10px] text-[#5C6B80] block">ROADS:</span>
              <span class="text-white">${exp.road_length_km !== null && exp.road_length_km !== undefined ? `${exp.road_length_km} km` : 'N/A'}</span>
            </div>
          </div>
          ${exp.notes ? `<div class="text-[10px] text-[#64748B] pt-0.5">${exp.notes}</div>` : ''}
        </div>
      `;
    }

    // 5. Actions: Links to Event and Lab
    const eventUrl = match.event_id ? `/event/${match.event_id}` : '#';
    const labUrl = `/lab/${match.analysis_id}`;
    const situationContent = this.buildSituationContent(match.situation);

    return `
      <div class="p-3 bg-[#090D14] border ${isMultiple ? 'border-[#1E6BFF]/40' : 'border-[#1E2838]'} space-y-3 rounded-[2px]">
        
        <!-- Header: AOI Display Name & Distinct Badges -->
        <div class="space-y-1.5 pb-2 border-b border-[#1E2838]">
          <div class="flex items-start justify-between gap-2">
            <div>
              <h4 class="text-sm font-semibold text-white">${match.aoi_display_name}</h4>
              <span class="type-metadata text-[10px] text-[#5C6B80]">
                ${match.aoi_region || ''}${match.aoi_country ? ` &bull; ${match.aoi_country}` : ''}
              </span>
            </div>
            <span class="badge ${stateBadgeClass} text-[9px] whitespace-nowrap">
              ${stateLabel}
            </span>
          </div>

          <div class="flex items-center justify-between text-xs pt-1">
            <span class="type-metadata text-[10px] text-[#5C6B80]">WHAT NISAR OBSERVED</span>
            <span class="font-medium text-white">${this.escapeHtml(match.situation?.headline || stateLabel)}</span>
          </div>
        </div>

        ${situationContent}

        <!-- State-Specific Explanation Block -->
        <div class="scientist-only">${stateSpecificContent}

        <!-- Scientific Metadata Grid -->
        <div class="space-y-1 text-xs">
          <div class="flex items-center justify-between py-1 border-b border-[#1E2838]/60">
            <span class="type-metadata text-[10px] text-[#5C6B80]">EVENT</span>
            <span class="text-[#CBD5E1] truncate max-w-[180px]">${match.event_title || 'Analysis Record'}</span>
          </div>

          <div class="flex items-center justify-between py-1 border-b border-[#1E2838]/60">
            <span class="type-metadata text-[10px] text-[#5C6B80]">COMPARISON</span>
            <span class="font-mono text-white text-[11px]">${match.date_range_display}</span>
          </div>

          ${measurementBlock}

          <div class="flex items-center justify-between py-1 border-b border-[#1E2838]/60">
            <span class="type-metadata text-[10px] text-[#5C6B80]">PRODUCT MATURITY</span>
            <span class="badge badge-maturity text-[9px]">${match.product_maturity_label}</span>
          </div>

          <div class="flex items-center justify-between py-1 border-b border-[#1E2838]/60">
            <span class="type-metadata text-[10px] text-[#5C6B80]">VALIDATION</span>
            <span class="badge ${match.validation_status_badge_class} text-[9px]">${match.validation_status_label}</span>
          </div>

          <div class="flex items-center justify-between py-1">
            <span class="type-metadata text-[10px] text-[#5C6B80]">MANIFEST</span>
            <span class="font-mono text-[11px] text-[#60A5FA]">${match.manifest_id || 'N/A'}</span>
          </div>
        </div></div>

        <!-- Exposure Context Block -->
        ${exposureBlock}

        <!-- Action Buttons -->
        <div class="grid grid-cols-2 gap-2 pt-2 border-t border-[#1E2838]">
          <a href="${eventUrl}" 
             class="btn btn-secondary text-xs py-1.5 px-2 flex items-center justify-center gap-1.5 text-center">
            <i data-lucide="external-link" class="w-3.5 h-3.5 text-[#1E6BFF]"></i>
            <span>Explore Analysis</span>
          </a>

          <a href="${labUrl}" 
             class="btn btn-secondary text-xs py-1.5 px-2 flex items-center justify-center gap-1.5 text-center">
            <i data-lucide="flask-conical" class="w-3.5 h-3.5 text-[#38BDF8]"></i>
            <span>Open Image Lab</span>
          </a>
        </div>

      </div>
    `;
  }

  // =========================================================================
  // STEP 6: REAL NISAR COVERAGE DISCOVERY COMPONENT
  // =========================================================================

  buildCoveragePromptHtml() {
    return `
      <div class="p-3.5 bg-[#090D14] border border-[#1E2838] space-y-3 rounded-[2px]">
        <div class="flex items-center justify-between border-b border-[#1E2838] pb-2">
          <div class="flex items-center gap-2">
            <i data-lucide="satellite" class="w-4 h-4 text-[#38BDF8]"></i>
            <span class="text-xs font-mono font-bold text-white tracking-wider uppercase">NISAR Coverage</span>
          </div>
          <span class="badge badge-maturity text-[9px]">ASF DAAC ARCHIVE</span>
        </div>

        <p class="text-xs text-[#94A3B8] leading-relaxed">
          Query the official Alaska Satellite Facility catalog for available NISAR L-band products over this area.
        </p>

        <button type="button" 
                id="btn-check-coverage"
                aria-label="Search live NISAR metadata archive for this area"
                class="btn bg-[#0F141F] hover:bg-[#1E6BFF]/20 text-[#60A5FA] border border-[#1E6BFF]/50 text-xs py-2 px-3 flex items-center justify-center gap-2 w-full transition-all">
          <i data-lucide="search" class="w-3.5 h-3.5 text-[#38BDF8]"></i>
          <span class="font-mono uppercase tracking-wider font-semibold">Check NISAR Coverage</span>
        </button>
      </div>
    `;
  }

  bindCoverageCheckButton() {
    const btn = document.getElementById('btn-check-coverage');
    if (!btn) return;
    btn.addEventListener('click', () => {
      this.performCoverageSearch();
    });
  }

  async performCoverageSearch() {
    const root = document.getElementById('coverage-section-root');
    if (!root) return;

    if (!this.lastGeometry) {
      root.innerHTML = `
        <div class="p-3 bg-[#140D0D] border border-red-900/40 text-xs text-red-400 space-y-1">
          <div class="font-bold">Cannot Query Coverage</div>
          <div>No active map selection geometry available.</div>
        </div>
      `;
      return;
    }

    // Cancel any previous in-flight coverage query cleanly
    if (this.coverageAbortController) {
      try { this.coverageAbortController.abort(); } catch (_) {}
    }
    this.coverageAbortController = new AbortController();

    // Loading skeleton state with live status
    root.innerHTML = `
      <div class="p-3.5 bg-[#090D14] border border-[#1E2838] space-y-3 rounded-[2px]" aria-live="assertive" aria-busy="true">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-xs font-mono text-[#38BDF8]">
            <div class="w-3.5 h-3.5 border-2 border-[#38BDF8] border-t-transparent rounded-full animate-spin"></div>
            <span>SEARCHING NISAR ARCHIVE...</span>
          </div>
          <span class="text-[10px] font-mono text-[#64748B]">ASF DAAC LIVE</span>
        </div>
        <div class="space-y-2 pt-1">
          <div class="skeleton h-3 w-3/4"></div>
          <div class="skeleton h-8 w-full"></div>
          <div class="skeleton h-8 w-full"></div>
        </div>
      </div>
    `;

    try {
      const res = await fetch('/api/coverage/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          geometry: this.lastGeometry,
          requested_products: ['GCOV', 'GUNW', 'GOFF']
        }),
        signal: this.coverageAbortController.signal
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned HTTP ${res.status}`);
      }

      const coverageData = await res.json();
      this.lastCoverageResponse = coverageData;
      this.lastCoverageQueryTime = new Date();
      this.renderCoverageResponse(coverageData);

      // Trigger map footprint rendering if footprints exist
      if (coverageData.footprints_geojson && typeof window.updateNisarFootprints === 'function') {
        window.updateNisarFootprints(coverageData.footprints_geojson);
      }

    } catch (err) {
      if (err.name === 'AbortError') {
        // Query superseded by a newer selection
        return;
      }
      console.error('[Coverage Search Error]:', err);
      this.renderCoverageError(err.message);
    }
  }

  renderCoverageError(message) {
    const root = document.getElementById('coverage-section-root');
    if (!root) return;

    root.innerHTML = `
      <div class="p-3.5 bg-[#140D0D] border border-red-900/40 space-y-2.5 rounded-[2px]" aria-live="assertive">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-red-400 text-xs font-mono font-bold uppercase tracking-wider">
            <i data-lucide="alert-triangle" class="w-4 h-4"></i>
            <span>Coverage Search Unavailable</span>
          </div>
          <span class="text-[10px] font-mono text-[#64748B]">NASA / ASF</span>
        </div>
        <p class="text-xs text-[#CBD5E1] leading-relaxed">
          ${message || 'The NISAR archive could not be queried at this time.'}
        </p>
        <button type="button" 
                id="btn-retry-coverage"
                class="btn btn-secondary text-xs py-1.5 px-3 flex items-center justify-center gap-2 w-full hover:border-[#38BDF8] hover:text-white transition-all">
          <i data-lucide="refresh-cw" class="w-3.5 h-3.5 text-[#38BDF8]"></i>
          <span>Try Again</span>
        </button>
      </div>
    `;

    const retryBtn = document.getElementById('btn-retry-coverage');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        retryBtn.disabled = true;
        retryBtn.innerHTML = `
          <div class="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
          <span>Querying Archive...</span>
        `;
        this.performCoverageSearch();
      });
    }
    this.refreshIcons();
  }

  renderCoverageResponse(data) {
    const root = document.getElementById('coverage-section-root');
    if (!root) return;

    if (data.search_status === 'SERVICE_UNAVAILABLE') {
      this.renderCoverageError(data.error_message || 'The NISAR archive could not be queried at this time.');
      return;
    }

    if (data.search_status === 'NO_RESULTS') {
      root.innerHTML = `
        <div class="p-3.5 bg-[#090D14] border border-[#1E2838] space-y-2.5 rounded-[2px]" aria-live="polite">
          <div class="flex items-center justify-between border-b border-[#1E2838] pb-1.5">
            <div class="flex items-center gap-1.5 text-[#94A3B8] text-xs font-mono font-bold uppercase">
              <i data-lucide="satellite" class="w-4 h-4 text-[#5C6B80]"></i><span>No matching NISAR observations found</span>
            </div>
            <div class="flex items-center gap-2">
              <button type="button" id="btn-reload-no-results" title="Reload archive query" class="text-[10px] font-mono text-[#38BDF8] hover:text-white flex items-center gap-1 py-0.5 px-1.5 bg-[#0F141F] border border-[#1E2838] rounded transition-colors">
                <i data-lucide="refresh-cw" class="w-2.5 h-2.5"></i><span>Reload</span>
              </button>
              <span class="badge badge-maturity text-[9px]">0 PRODUCTS</span>
            </div>
          </div>
          <p class="text-xs text-[#CBD5E1] leading-relaxed">No matching NISAR products were found for this selection and search period.</p>
          <div class="p-2 bg-[#0F141F] border border-[#1E2838] text-[11px] text-[#94A3B8]">
            This does not mean No Change. It only means the current archive query did not return matching products.
          </div>
          <div class="text-[10px] font-mono text-[#5C6B80]">SOURCE: NASA NISAR / ASF DAAC · ${data.date_range_summary || '2026-06-17 → Present'}</div>
        </div>`;
      const reloadBtn = document.getElementById('btn-reload-no-results');
      if (reloadBtn) {
        reloadBtn.addEventListener('click', () => this.performCoverageSearch());
      }
      this.refreshIcons();
      return;
    }

    const emptySummary = { provisional: { count: 0, acquisitions: [] }, beta: { count: 0, acquisitions: [] }, total_count: 0 };
    const gcov = data.products?.GCOV || emptySummary;
    const gunw = data.products?.GUNW || emptySummary;
    const goff = data.products?.GOFF || emptySummary;
    const totalProducts = Number(gcov.total_count || 0) + Number(gunw.total_count || 0) + Number(goff.total_count || 0);

    const productCards = [
      {
        code: 'GCOV', name: 'Radar Surface Backscatter', summary: gcov,
        meaning: 'Repeat radar brightness observations that can support analysis of surface-water and vegetation-structure change.',
        uses: ['Surface-water / inundation change', 'Vegetation disturbance']
      },
      {
        code: 'GUNW', name: 'Ground Movement Evidence', summary: gunw,
        meaning: 'Interferometric measurements that can support analysis of relative movement toward or away from the satellite.',
        uses: ['Relative ground movement']
      },
      {
        code: 'GOFF', name: 'Surface / Glacier Motion Evidence', summary: goff,
        meaning: 'Pixel-offset measurements that can support analysis of large surface motion such as glacier displacement.',
        uses: ['Glacier / large surface motion']
      }
    ];

    const latestDates = productCards.flatMap(card => [card.summary.provisional?.latest_date, card.summary.beta?.latest_date]).filter(Boolean).sort().reverse();
    const latestAcquisition = latestDates.length ? this.formatDateSimple(latestDates[0]) : 'Not recorded';

    const productCardsHtml = productCards.map(card => {
      const count = Number(card.summary.total_count || 0);
      const latest = card.summary.provisional?.latest_date || card.summary.beta?.latest_date;
      return `<div class="p-3 bg-[#0F141F] border border-[#1E2838] space-y-1.5">
        <div class="flex justify-between gap-2"><div><div class="text-xs text-white font-semibold">${card.name}</div><div class="text-[10px] text-[#64748B] font-mono scientist-only">${card.code}</div></div><div class="text-right"><div class="text-lg font-mono text-white">${count}</div><div class="text-[9px] text-[#64748B]">matching product${count === 1 ? '' : 's'}</div></div></div>
        <p class="text-[11px] text-[#94A3B8] leading-relaxed">${card.meaning}</p>
        ${latest ? `<div class="text-[10px] text-[#94A3B8]">Latest: <span class="text-white">${this.formatDateSimple(latest)}</span></div>` : '<div class="text-[10px] text-[#64748B]">No matching product found.</div>'}
        ${count ? `<div class="text-[10px] text-[#CBD5E1]">Can support: ${card.uses.join(' · ')}</div>` : ''}
        <div class="scientist-only text-[10px] text-[#64748B]">PROVISIONAL ${card.summary.provisional?.count || 0} · BETA ${card.summary.beta?.count || 0}</div>
      </div>`;
    }).join('');

    const allAcquisitions = [
      ...(gcov.provisional?.acquisitions || []), ...(gcov.beta?.acquisitions || []),
      ...(gunw.provisional?.acquisitions || []), ...(gunw.beta?.acquisitions || []),
      ...(goff.provisional?.acquisitions || []), ...(goff.beta?.acquisitions || [])
    ].sort((a, b) => String(b.start_time || '').localeCompare(String(a.start_time || '')));

    const productPublicName = code => ({
      GCOV: 'Radar Surface Backscatter', GUNW: 'Ground Movement Evidence', GOFF: 'Surface / Glacier Motion Evidence'
    }[code] || 'NISAR science product');
    const orbitPublicName = raw => String(raw || '').toUpperCase() === 'ASCENDING'
      ? 'Northbound pass' : String(raw || '').toUpperCase() === 'DESCENDING' ? 'Southbound pass' : 'Pass direction unavailable';

    const recentRows = allAcquisitions.slice(0, 6).map(acq => `
      <div class="flex items-start justify-between gap-3 py-2 border-b border-[#1E2838]/60 last:border-0">
        <div><div class="text-xs text-white">${productPublicName(acq.product_type)}</div><div class="text-[10px] text-[#94A3B8]">${orbitPublicName(acq.orbit_direction)}</div></div>
        <div class="text-right"><div class="text-[11px] font-mono text-white">${this.formatDateSimple(acq.start_time)}</div><div class="scientist-only text-[9px] text-[#64748B]">${acq.product_type} · ${acq.data_maturity || 'UNKNOWN'}</div></div>
      </div>`).join('');

    const pairs = data.gcov_pair_candidates || [];
    const recommendedPair = pairs.find(p => p.compatibility_status === 'COMPATIBLE') || pairs[0] || null;
    const publicPairHtml = recommendedPair ? `
      <div class="p-3 bg-[#0F141F] border border-[#1E2838] space-y-2">
        <div class="type-metadata">RECOMMENDED RADAR COMPARISON</div>
        <div class="flex items-center justify-between gap-3"><span class="font-mono text-white">${this.formatDateSimple(recommendedPair.before_date)}</span><span class="text-[#60A5FA]">→</span><span class="font-mono text-white">${this.formatDateSimple(recommendedPair.after_date)}</span></div>
        <div class="grid sm:grid-cols-2 gap-1 text-[11px] text-[#CBD5E1]">
          <div>${recommendedPair.checks?.same_track ? '✓ Same satellite path' : '• Satellite path compatibility incomplete'}</div>
          <div>${recommendedPair.checks?.same_frame ? '✓ Same observed area' : '• Area compatibility incomplete'}</div>
          <div>${recommendedPair.checks?.same_direction ? '✓ Same viewing direction' : '• Viewing direction compatibility incomplete'}</div>
          <div>${recommendedPair.checks?.compatible_polarization ? '✓ Compatible radar channels' : '• Radar-channel compatibility incomplete'}</div>
        </div>
        <p class="text-[10px] text-[#94A3B8]">This pair is a candidate for future comparison; coverage alone does not mean surface change occurred.</p>
      </div>` : '<div class="p-3 bg-[#0F141F] border border-[#1E2838] text-xs text-[#94A3B8]">No compatible GCOV comparison pair is currently available in the returned metadata.</div>';

    const acqRows = allAcquisitions.slice(0, 25).map(acq => `
      <tr class="border-b border-[#1E2838]/60">
        <td class="py-1 px-1.5 font-mono text-[10px] text-white">${this.formatDateSimple(acq.start_time)}</td>
        <td class="py-1 px-1.5 font-mono text-[10px] text-[#38BDF8]">${acq.product_type}</td>
        <td class="py-1 px-1.5 font-mono text-[10px] text-[#94A3B8]">${acq.data_maturity || '—'}</td>
        <td class="py-1 px-1.5 font-mono text-[10px] text-[#CBD5E1]">${acq.track ?? '—'}</td>
        <td class="py-1 px-1.5 font-mono text-[10px] text-[#CBD5E1]">${acq.frame ?? '—'}</td>
        <td class="py-1 px-1.5 font-mono text-[10px] text-[#94A3B8]">${acq.orbit_direction || '—'}</td>
        <td class="py-1 px-1.5 font-mono text-[10px] text-[#94A3B8]">${(acq.polarizations || []).join('/') || '—'}</td>
        <td class="py-1 px-1.5 font-mono text-[10px] text-[#94A3B8]">${acq.processing_version || '—'}</td>
      </tr>`).join('');

    const technicalPairs = pairs.map(p => `<div class="p-2 bg-[#0F141F] border border-[#1E2838] text-[10px] font-mono text-[#94A3B8] space-y-1">
      <div class="text-white">${this.formatDateSimple(p.before_date)} → ${this.formatDateSimple(p.after_date)} · ${p.compatibility_status}</div>
      <div>Track ${p.checks?.details?.track || 'unknown'} · Frame ${p.checks?.details?.frame || 'unknown'} · Direction ${p.checks?.same_direction === true ? 'same' : p.checks?.same_direction === false ? 'different' : 'unknown'} · Polarization ${p.checks?.compatible_polarization === true ? 'compatible' : p.checks?.compatible_polarization === false ? 'incompatible' : 'unknown'}</div>
    </div>`).join('');

    const warningsHtml = (data.warnings && data.warnings.length)
      ? `<div class="p-2.5 bg-[#2D1B00] border border-[#854D0E] text-[11px] text-[#FDE047] rounded-[2px] flex items-center gap-2"><i data-lucide="info" class="w-3.5 h-3.5 text-[#EAB308] shrink-0"></i><span>${data.warnings.join(' · ')}</span></div>`
      : '';

    root.innerHTML = `
      <div class="p-3.5 bg-[#090D14] border border-[#1E2838] space-y-3.5 rounded-[2px]" aria-live="polite">
        <div class="flex items-center justify-between border-b border-[#1E2838] pb-2">
          <div>
            <div class="type-metadata text-[#60A5FA]">NISAR DATA FOR THIS AREA</div>
            <div class="text-lg text-white font-semibold mt-1">${totalProducts} matching NISAR data product${totalProducts === 1 ? '' : 's'} found</div>
          </div>
          <div class="flex items-center gap-2">
            <button type="button" id="btn-reload-coverage" title="Reload live observations" class="text-[10px] font-mono text-[#38BDF8] hover:text-white flex items-center gap-1.5 py-1 px-2.5 bg-[#0F141F] border border-[#1E2838] hover:border-[#38BDF8] rounded transition-all">
              <i data-lucide="refresh-cw" class="w-3 h-3"></i><span>Reload</span>
            </button>
            <span class="badge badge-live text-[9px]">LIVE METADATA</span>
          </div>
        </div>
        ${warningsHtml}
        <div class="grid grid-cols-2 gap-2 text-[11px]"><div class="p-2 bg-[#0F141F] border border-[#1E2838]"><div class="type-metadata">LATEST AVAILABLE</div><div class="text-white mt-1">${latestAcquisition}</div></div><div class="p-2 bg-[#0F141F] border border-[#1E2838]"><div class="type-metadata">SOURCE</div><div class="text-white mt-1">NASA NISAR / ASF DAAC</div></div></div>
        ${!this.hasProcessedAnalysis ? '<div class="p-3 border border-[#1E6BFF]/30 bg-[#0B1220] text-xs text-[#CBD5E1]"><strong class="text-white">NISAR has observed this area.</strong><br>No processed surface-change analysis exists yet. These products show what can be analyzed; they do not mean a change or hazard was detected.</div>' : '<div class="p-3 border border-[#1E6BFF]/30 bg-[#0B1220] text-xs text-[#CBD5E1]">Archive coverage is separate from the processed analysis above. Product availability does not change the stored scientific result.</div>'}
        <div><div class="type-metadata mb-2">WHAT THESE PRODUCTS CAN HELP ANALYZE</div><div class="space-y-2">${productCardsHtml}</div></div>
        ${publicPairHtml}
        <div><div class="type-metadata mb-1">RECENT OBSERVATIONS</div><div class="bg-[#0F141F] border border-[#1E2838] px-3">${recentRows || '<p class="text-xs text-[#64748B] py-3">No recent products to display.</p>'}</div></div>
        <div class="p-3 bg-[#0F141F] border border-[#1E2838] text-[11px] text-[#94A3B8]"><strong class="text-white">What this means:</strong> compatible repeat observations can be compared to look for changes in surface water, vegetation structure, ground position, or large surface motion. Coverage alone does not mean that a change occurred.</div>

        <details class="scientist-only border-t border-[#1E2838] pt-3"><summary class="type-metadata cursor-pointer">SCIENTIST METADATA · ALL ACQUISITIONS & PAIR CHECKS</summary><div class="mt-3 space-y-3">
          <div class="border border-[#1E2838] overflow-x-auto max-h-64"><table class="w-full text-left"><thead><tr class="bg-[#0F141F] text-[9px] font-mono text-[#5C6B80]"><th class="p-1.5">Date</th><th class="p-1.5">Product</th><th class="p-1.5">Maturity</th><th class="p-1.5">Track</th><th class="p-1.5">Frame</th><th class="p-1.5">Orbit</th><th class="p-1.5">Pol</th><th class="p-1.5">PGE</th></tr></thead><tbody>${acqRows}</tbody></table></div>
          <div class="space-y-2">${technicalPairs || '<p class="text-[10px] text-[#64748B]">No GCOV comparison candidates returned.</p>'}</div>
        </div></details>
      </div>`;

    const reloadBtn = document.getElementById('btn-reload-coverage');
    if (reloadBtn) {
      reloadBtn.addEventListener('click', () => {
        const icon = reloadBtn.querySelector('i');
        if (icon) icon.classList.add('animate-spin');
        this.performCoverageSearch();
      });
    }

    this.refreshIcons();
  }

  formatDateSimple(dateStr) {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr.substring(0, 10);
      const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
      const day = String(d.getUTCDate()).padStart(2, '0');
      const mon = months[d.getUTCMonth()];
      const yr = d.getUTCFullYear();
      return `${day} ${mon} ${yr}`;
    } catch {
      return dateStr.substring(0, 10);
    }
  }

  refreshIcons() {
    if (typeof lucide !== 'undefined' && lucide.createIcons) {
      lucide.createIcons();
    }
  }
}

window.AreaInspector = AreaInspector;
