// Runs before React (no flash of the wrong theme). External file because CSP blocks inline scripts.
// Keep key + defaults in sync with src/store/theme.js
(function () {
  try {
    var s = JSON.parse(localStorage.getItem("faceai-theme-v2") || "{}").state || {};
    var mode = s.mode || "light";
    var dark = mode === "dark" || (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.dataset.accent = s.accent || "maroon";
  } catch (e) {}
})();
