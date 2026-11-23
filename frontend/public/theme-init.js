// Runs before React (no flash of the wrong theme). External file because CSP blocks inline scripts.
(function () {
  try {
    var s = JSON.parse(localStorage.getItem("faceai-theme") || "{}").state || {};
    var mode = s.mode || "system";
    var dark = mode === "dark" || (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.dataset.accent = s.accent || "indigo";
  } catch (e) {}
})();
