/**
 * NISAR Surface Change Explorer
 * Navigation Drawer & Keyboard Accessibility
 */

function setupNavigation() {
  const drawer = document.getElementById('mobile-drawer');
  const openBtn = document.getElementById('mobile-menu-toggle');
  const closeBtn = document.getElementById('mobile-drawer-close');
  const backdrop = document.getElementById('drawer-backdrop');
  const mainContent = document.getElementById('main-content');

  if (!drawer || !openBtn) return;

  function openDrawer() {
    drawer.classList.remove('hidden');
    // slight delay for transition
    requestAnimationFrame(() => {
      drawer.classList.add('opacity-100');
      const panel = drawer.querySelector('.drawer-panel');
      if (panel) {
        panel.classList.remove('-translate-x-full');
      }
    });
    openBtn.setAttribute('aria-expanded', 'true');
    if (mainContent) mainContent.inert = true;
    if (closeBtn) closeBtn.focus();
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    const panel = drawer.querySelector('.drawer-panel');
    if (panel) {
      panel.classList.add('-translate-x-full');
    }
    drawer.classList.remove('opacity-100');
    setTimeout(() => {
      drawer.classList.add('hidden');
    }, 200);

    openBtn.setAttribute('aria-expanded', 'false');
    if (mainContent) mainContent.inert = false;
    openBtn.focus();
    document.body.style.overflow = '';
  }

  openBtn.addEventListener('click', openDrawer);

  if (closeBtn) {
    closeBtn.addEventListener('click', closeDrawer);
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeDrawer);
  }

  // Keyboard accessibility: ESC key dismisses drawer
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !drawer.classList.contains('hidden')) {
      closeDrawer();
    }
  });

  // Close drawer if screen resizes to desktop width (>1024px)
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 1024 && !drawer.classList.contains('hidden')) {
      closeDrawer();
    }
  });
}

document.addEventListener('DOMContentLoaded', setupNavigation);
