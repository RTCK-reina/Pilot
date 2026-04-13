/**
 * PilotCharts — reusable Chart.js wrapper with PiLot design system defaults.
 *
 * Colours:  efficiency=#34d399  charging=#60a5fa  consumption=#fb923c
 * Grid:     #2e3344
 * Text:     #9aa0b0
 * Animation: 300 ms
 */
var PilotCharts = (function () {
  'use strict';

  var GRID   = '#2e3344';
  var TEXT   = '#9aa0b0';
  var ANIM   = 300;

  var PALETTE = [
    '#34d399', '#60a5fa', '#fb923c', '#a78bfa',
    '#f472b6', '#facc15', '#38bdf8', '#fb7185'
  ];

  /** Merge user options on top of PiLot defaults (shallow). */
  function _merge(defaults, user) {
    if (!user) return defaults;
    var out = {};
    var key;
    for (key in defaults) { out[key] = defaults[key]; }
    for (key in user) {
      if (typeof user[key] === 'object' && user[key] !== null && !Array.isArray(user[key]) &&
          typeof defaults[key] === 'object' && defaults[key] !== null) {
        out[key] = _merge(defaults[key], user[key]);
      } else {
        out[key] = user[key];
      }
    }
    return out;
  }

  function _baseScaleOpts() {
    return {
      grid: { color: GRID },
      ticks: { color: TEXT, font: { size: 11 } },
      title: { color: TEXT, font: { size: 12 } }
    };
  }

  // ─── Line Chart ──────────────────────────────────────────────
  function line(canvasId, labels, datasets, userOpts) {
    var el = document.getElementById(canvasId);
    if (!el) return null;

    datasets.forEach(function (ds, i) {
      ds.borderWidth  = ds.borderWidth  || 2;
      ds.pointRadius  = ds.pointRadius  || 3;
      ds.borderColor  = ds.borderColor  || PALETTE[i % PALETTE.length];
    });

    var defaults = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: ANIM },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: TEXT, boxWidth: 12 } }
      },
      scales: {
        x: _baseScaleOpts(),
        y: _baseScaleOpts()
      }
    };

    var opts = _merge(defaults, userOpts);

    // Ensure extra y-axes also get base styling
    if (opts.scales) {
      Object.keys(opts.scales).forEach(function (key) {
        if (key !== 'x' && key !== 'y') {
          opts.scales[key] = _merge(_baseScaleOpts(), opts.scales[key]);
        }
      });
    }

    return new Chart(el, {
      type: 'line',
      data: { labels: labels, datasets: datasets },
      options: opts
    });
  }

  // ─── Bar Chart ───────────────────────────────────────────────
  function bar(canvasId, labels, data, userOpts) {
    var el = document.getElementById(canvasId);
    if (!el) return null;

    var color = (userOpts && userOpts.color) || PALETTE[1];
    var label = (userOpts && userOpts.label) || '';

    var defaults = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: ANIM },
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: _merge(_baseScaleOpts(), {
          title: { display: !!(userOpts && userOpts.xLabel), text: (userOpts && userOpts.xLabel) || '' }
        }),
        y: _merge(_baseScaleOpts(), {
          title: { display: !!(userOpts && userOpts.yLabel), text: (userOpts && userOpts.yLabel) || '' }
        })
      }
    };

    return new Chart(el, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: label,
          data: data,
          backgroundColor: color + 'cc',
          borderColor: color,
          borderWidth: 1,
          borderRadius: 3
        }]
      },
      options: defaults
    });
  }

  // ─── Scatter Chart ───────────────────────────────────────────
  function scatter(canvasId, data, userOpts) {
    var el = document.getElementById(canvasId);
    if (!el) return null;

    var color = (userOpts && userOpts.color) || PALETTE[0];

    var defaults = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: ANIM },
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: _merge(_baseScaleOpts(), {
          title: { display: !!(userOpts && userOpts.xLabel), text: (userOpts && userOpts.xLabel) || '' }
        }),
        y: _merge(_baseScaleOpts(), {
          title: { display: !!(userOpts && userOpts.yLabel), text: (userOpts && userOpts.yLabel) || '' }
        })
      }
    };

    return new Chart(el, {
      type: 'scatter',
      data: {
        datasets: [{
          data: data,
          backgroundColor: color + '99',
          borderColor: color,
          pointRadius: 4,
          pointHoverRadius: 6
        }]
      },
      options: defaults
    });
  }

  // ─── Doughnut Chart ──────────────────────────────────────────
  function doughnut(canvasId, labels, data, userOpts) {
    var el = document.getElementById(canvasId);
    if (!el) return null;

    var colors = (userOpts && userOpts.colors) || PALETTE.slice(0, labels.length);

    var defaults = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: ANIM },
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: TEXT, boxWidth: 12, padding: 16 }
        }
      }
    };

    return new Chart(el, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors,
          borderColor: 'transparent',
          borderWidth: 0
        }]
      },
      options: defaults
    });
  }

  // ─── Public API ──────────────────────────────────────────────
  return {
    line: line,
    bar: bar,
    scatter: scatter,
    doughnut: doughnut
  };
})();
