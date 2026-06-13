/**
 * api_config.js
 * Dynamically sets the backend API base URL.
 *   - In local development (localhost) it points to the Flask server.
 *   - In production (on Vercel) it points to the Railway backend.
 *     Set window.RAILWAY_URL via an environment variable during your
 *     Vercel build, OR update the PRODUCTION_API_URL constant below
 *     after you get your Railway domain.
 */

(function () {
  // -- UPDATE THIS after deploying to Railway --
  const PRODUCTION_API_URL = 'https://YOUR_APP.up.railway.app';

  const isLocal = (
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1'
  );

  // Expose globally so all JS files can use it
  window.API_BASE = isLocal ? '' : PRODUCTION_API_URL;

  /**
   * Prefixed fetch – use this instead of plain fetch() in all portal JS files.
   * Usage: apiFetch('/api/users').then(...)
   */
  window.apiFetch = function (path, options) {
    return fetch(window.API_BASE + path, Object.assign({ credentials: 'include' }, options || {}));
  };
})();
