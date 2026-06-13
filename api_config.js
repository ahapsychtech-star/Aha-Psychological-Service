/**
 * api_config.js
 * Routes all API calls to the Railway backend from the Vercel frontend.
 */

(function () {
  // Your Railway backend URL
  const PRODUCTION_API_URL = 'https://web-production-0b7ca.up.railway.app';

  const isLocal = (
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1'
  );

  // Expose globally so all JS files can use it
  window.API_BASE = isLocal ? '' : PRODUCTION_API_URL;

  /**
   * Prefixed fetch - use this instead of plain fetch() in all portal JS files.
   * Usage: apiFetch('/api/users').then(...)
   */
  window.apiFetch = function (path, options) {
    return fetch(window.API_BASE + path, Object.assign({ credentials: 'include' }, options || {}));
  };
})();
