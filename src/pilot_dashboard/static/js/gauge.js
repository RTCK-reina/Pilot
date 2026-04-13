/**
 * PiLot SOC Gauge
 *
 * Renders an SVG arc gauge for battery state-of-charge.
 * Automatically picks a colour from the SOC gradient defined
 * in tokens.css.
 *
 * Usage:
 *   updateGauge("soc-gauge", 72);          // main gauge
 *   updateGauge("charge-live-gauge", 45);   // charging page mini gauge
 */
(function () {
  "use strict";

  /**
   * Return a CSS variable value from the document root.
   */
  function cssVar(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
  }

  /**
   * Determine the gauge colour based on SOC percentage.
   */
  function socColor(percent) {
    if (percent <= 10) return cssVar("--soc-color-critical");
    if (percent <= 20) return cssVar("--soc-color-low");
    if (percent <= 40) return cssVar("--soc-color-mid");
    if (percent <= 80) return cssVar("--soc-color-good");
    return cssVar("--soc-color-high");
  }

  /**
   * Update a gauge element.
   *
   * @param {string} gaugeId  - The id of the .soc-gauge container.
   * @param {number} percent  - SOC percentage 0-100.
   */
  function updateGauge(gaugeId, percent) {
    var container = document.getElementById(gaugeId);
    if (!container) return;

    percent = Math.max(0, Math.min(100, percent));

    var fill = container.querySelector(".soc-gauge__fill");
    var valueEl = container.querySelector(".soc-gauge__value");

    if (!fill) return;

    // Circumference = 2 * PI * r
    var r = parseFloat(fill.getAttribute("r"));
    var circumference = 2 * Math.PI * r;
    var offset = circumference - (circumference * percent) / 100;

    fill.style.strokeDasharray = circumference;
    fill.style.strokeDashoffset = offset;
    fill.style.stroke = socColor(percent);

    if (valueEl) {
      valueEl.textContent = Math.round(percent);
    }
  }

  /**
   * Create a mini progress bar (horizontal).
   * Appends a styled div inside the given container.
   *
   * @param {string} containerId
   * @param {number} percent 0-100
   */
  function updateProgressBar(containerId, percent) {
    var container = document.getElementById(containerId);
    if (!container) return;

    percent = Math.max(0, Math.min(100, percent));

    var bar = container.querySelector(".progress-bar__fill");
    if (!bar) {
      // Create the bar structure
      container.innerHTML =
        '<div class="progress-bar">' +
        '<div class="progress-bar__fill"></div>' +
        "</div>";
      bar = container.querySelector(".progress-bar__fill");
    }

    bar.style.width = percent + "%";
    bar.style.backgroundColor = socColor(percent);
  }

  // Listen for real-time updates and refresh the home gauge
  document.addEventListener("pilot-update", function (e) {
    var d = e.detail;
    if (d.battery_level != null) {
      updateGauge("soc-gauge", d.battery_level);
      updateGauge("charge-live-gauge", d.battery_level);

      // Also update the value/range text on home page
      var rangeEl = document.getElementById("range-value");
      if (rangeEl && d.battery_range != null) {
        rangeEl.textContent = Math.round(d.battery_range);
      }
      var socEl = document.getElementById("soc-value");
      if (socEl) {
        socEl.textContent = Math.round(d.battery_level);
      }
    }
  });

  // Expose globally
  window.pilotGauge = {
    updateGauge: updateGauge,
    updateProgressBar: updateProgressBar,
    socColor: socColor
  };
})();
