/**
 * PiLot Theme Manager
 *
 * Reads/writes theme preference to localStorage, toggles the
 * data-theme attribute on <html>, and respects prefers-color-scheme
 * when set to "auto".
 *
 * Loads synchronously (before other scripts) to prevent flash of
 * wrong theme.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "pilot-theme";
  var ATTR        = "data-theme";

  /**
   * Detect system preference.
   * @returns {"dark"|"light"}
   */
  function systemTheme() {
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
      return "light";
    }
    return "dark";
  }

  /**
   * Read the stored preference.
   * @returns {"dark"|"light"|"auto"}
   */
  function getPreference() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "dark";
    } catch (e) {
      return "dark";
    }
  }

  /**
   * Persist the preference.
   * @param {"dark"|"light"|"auto"} value
   */
  function setPreference(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (e) {
      // localStorage may be unavailable
    }
  }

  /**
   * Resolve the effective theme (never "auto").
   * @param {"dark"|"light"|"auto"} pref
   * @returns {"dark"|"light"}
   */
  function resolve(pref) {
    if (pref === "auto") return systemTheme();
    return pref;
  }

  /**
   * Apply a theme to the document.
   * @param {"dark"|"light"} theme
   */
  function apply(theme) {
    document.documentElement.setAttribute(ATTR, theme);
  }

  /**
   * Cycle through themes: dark -> light -> auto -> dark
   */
  function toggle() {
    var pref = getPreference();
    var next;
    if (pref === "dark")  next = "light";
    else if (pref === "light") next = "auto";
    else next = "dark";

    setPreference(next);
    apply(resolve(next));

    // Update the settings select if it exists
    var sel = document.getElementById("setting-theme");
    if (sel) sel.value = next;
  }

  /**
   * Set a specific theme.
   * @param {"dark"|"light"|"auto"} value
   */
  function set(value) {
    setPreference(value);
    apply(resolve(value));
  }

  // ---- Immediate application (no DOMContentLoaded wait) ----
  var pref = getPreference();
  apply(resolve(pref));

  // ---- Bind toggle button after DOM is ready ----
  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", toggle);
    }

    // Sync settings page select
    var sel = document.getElementById("setting-theme");
    if (sel) {
      sel.value = getPreference();
      sel.addEventListener("change", function () {
        set(sel.value);
      });
    }
  });

  // ---- React to OS theme changes when in auto mode ----
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      if (getPreference() === "auto") {
        apply(systemTheme());
      }
    });
  }

  // Expose for programmatic use
  window.pilotTheme = {
    get: getPreference,
    set: set,
    toggle: toggle,
    resolve: function () { return resolve(getPreference()); }
  };
})();
