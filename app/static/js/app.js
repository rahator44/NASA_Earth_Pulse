/**
 * NISAR Surface Change Explorer
 * Global Application Setup
 */

document.addEventListener('DOMContentLoaded', () => {
  const defaults = {
    mode: 'public', reducedMotion: false, compactMetadata: false,
    mapDefaultView: 'global', showChangeRegions: true, showAois: true,
    showFootprints: false, language: 'en'
  };
  const storageKey = 'nisar-explorer-preferences';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(storageKey) || '{}') || {}; } catch (_) {}
  const prefs = { ...defaults, ...saved };
  window.NisarPreferences = {
    get: key => prefs[key],
    set(key, value) { prefs[key] = value; try { localStorage.setItem(storageKey, JSON.stringify(prefs)); } catch (_) {} apply(); }
  };
  function apply() {
    const page = document.body.dataset.page;
    document.body.dataset.mode = page === 'lab' ? 'scientist' : prefs.mode;
    document.body.classList.toggle('reduced-motion', !!prefs.reducedMotion);
    document.body.classList.toggle('compact-metadata', !!prefs.compactMetadata);
    document.querySelectorAll('[data-mode-option]').forEach(button => {
      const selected = button.dataset.modeOption === prefs.mode;
      button.setAttribute('aria-checked', String(selected));
      button.classList.toggle('mode-option-active', selected);
    });
    document.querySelectorAll('[data-pref]').forEach(input => {
      const key = input.dataset.pref;
      if (input.type === 'checkbox') input.checked = !!prefs[key];
      else input.value = prefs[key] ?? defaults[key];
    });
  }
  document.querySelectorAll('[data-pref]').forEach(input => input.addEventListener('change', () => {
    prefs[input.dataset.pref] = input.type === 'checkbox' ? input.checked : input.value;
    try { localStorage.setItem(storageKey, JSON.stringify(prefs)); } catch (_) {}
    apply();
  }));
  document.querySelectorAll('[data-mode-option]').forEach(button => button.addEventListener('click', () => {
    prefs.mode = button.dataset.modeOption;
    try { localStorage.setItem(storageKey, JSON.stringify(prefs)); } catch (_) {}
    apply();
  }));
  apply();

  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // HTMX content re-render hook to re-trigger icons if HTMX is used
  document.body.addEventListener('htmx:afterSwap', () => {
    if (window.lucide) {
      window.lucide.createIcons();
    }
  });

});
