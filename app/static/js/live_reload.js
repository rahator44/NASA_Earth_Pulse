/**
 * NISAR Explorer - Live Auto-Reload & Dev Server Health Watcher
 * Provides Vite/Next.js-style automatic browser reloading and server connection state.
 */
(() => {
  // Only activate in local development environments
  const isLocalhost = Boolean(
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname.endsWith('.local')
  );

  if (!isLocalhost) return;

  let currentSessionId = null;
  let isReconnecting = false;
  let eventSource = null;
  let reconnectPollTimer = null;
  let toastEl = null;

  function createToastElement() {
    if (toastEl) return toastEl;
    toastEl = document.createElement('div');
    toastEl.id = 'dev-live-reload-toast';
    toastEl.className = 'fixed top-4 right-4 z-[99999] transition-all duration-300 pointer-events-none opacity-0 translate-y-[-10px]';
    toastEl.innerHTML = `
      <div class="flex items-center gap-2.5 px-3.5 py-2 bg-[#090D14]/95 border border-[#1E2838] backdrop-blur-md rounded shadow-2xl text-xs font-mono">
        <span id="dev-toast-dot" class="relative flex h-2.5 w-2.5">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-sky-500"></span>
        </span>
        <span id="dev-toast-text" class="text-[#CBD5E1] tracking-wide">CONNECTING...</span>
      </div>
    `;
    document.body.appendChild(toastEl);
    return toastEl;
  }

  function showToast(text, type = 'info') {
    createToastElement();
    const textEl = document.getElementById('dev-toast-text');
    const dotEl = document.getElementById('dev-toast-dot');
    if (!textEl || !dotEl) return;

    textEl.textContent = text;
    if (type === 'reloading') {
      dotEl.innerHTML = `
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
        <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
      `;
    } else if (type === 'success') {
      dotEl.innerHTML = `
        <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
      `;
    }

    toastEl.classList.remove('opacity-0', 'translate-y-[-10px]');
    toastEl.classList.add('opacity-100', 'translate-y-0');
  }

  function hideToast(delay = 1500) {
    if (!toastEl) return;
    setTimeout(() => {
      toastEl.classList.remove('opacity-100', 'translate-y-0');
      toastEl.classList.add('opacity-0', 'translate-y-[-10px]');
    }, delay);
  }

  function startFallbackPolling() {
    if (reconnectPollTimer) return;
    reconnectPollTimer = setInterval(async () => {
      try {
        const res = await fetch('/api/system/status-heartbeat', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          clearInterval(reconnectPollTimer);
          reconnectPollTimer = null;
          if (currentSessionId && data.sessionId && data.sessionId !== currentSessionId) {
            showToast('SERVER RELOADED · REFRESHING...', 'success');
            setTimeout(() => window.location.reload(), 400);
          } else {
            initSSE();
            hideToast(500);
          }
        }
      } catch (_) {
        // Still waiting for server to boot back up
      }
    }, 1000);
  }

  function initSSE() {
    if (eventSource) {
      try { eventSource.close(); } catch (_) {}
    }

    try {
      eventSource = new EventSource('/api/system/live-reload');

      eventSource.onopen = () => {
        if (isReconnecting) {
          isReconnecting = false;
          hideToast(600);
        }
      };

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (!currentSessionId) {
            currentSessionId = payload.sessionId;
            return;
          }

          // If session ID changed, server was reloaded!
          if (payload.sessionId && payload.sessionId !== currentSessionId) {
            showToast('CODE UPDATED · REFRESHING...', 'success');
            setTimeout(() => window.location.reload(), 300);
          }
        } catch (_) {}
      };

      eventSource.onerror = () => {
        if (!isReconnecting) {
          isReconnecting = true;
          showToast('SERVER RESTARTING · WAITING FOR RELOAD...', 'reloading');
        }
        try { eventSource.close(); } catch (_) {}
        eventSource = null;
        startFallbackPolling();
      };
    } catch (_) {
      startFallbackPolling();
    }
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSSE);
  } else {
    initSSE();
  }
})();
