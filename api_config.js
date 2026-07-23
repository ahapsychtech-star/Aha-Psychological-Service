/**
 * api_config.js
 * Uses the same origin on Vercel deployments and falls back to the Railway backend only when needed.
 */

(function () {
  const FALLBACK_API_URL = 'https://web-production-0b7ca.up.railway.app';
  const PRODUCTION_API_URL = (typeof window !== 'undefined' && window.location && window.location.origin)
    ? window.location.origin
    : FALLBACK_API_URL;

  // Expose globally so all JS files can use it
  window.API_BASE = PRODUCTION_API_URL;
  window.getApiUrl = function(path) {
    if (!path) return path;
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    if (path.startsWith('/')) return window.API_BASE + path;
    return window.API_BASE + '/' + path;
  };

  /**
   * Prefixed fetch - use this instead of plain fetch() in all portal JS files.
   * Usage: apiFetch('/api/users').then(...)
   */
  window.apiFetch = function (path, options) {
    return fetch(window.API_BASE + path, Object.assign({ credentials: 'include' }, options || {}));
  };
})();
