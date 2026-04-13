/**
 * PiLot WebSocket Client
 *
 * Connects to /ws, dispatches 'pilot-update' CustomEvent on each
 * message.  Implements exponential backoff reconnection with jitter.
 */
(function () {
  "use strict";

  var WS_PATH = "/ws";

  // Backoff configuration
  var BASE_DELAY   = 1000;   // 1 s
  var MAX_DELAY    = 30000;  // 30 s
  var JITTER_RATIO = 0.3;

  var ws       = null;
  var attempt  = 0;
  var timer    = null;
  var disposed = false;

  /** Compute delay with exponential backoff + jitter. */
  function backoffDelay() {
    var exp   = Math.min(BASE_DELAY * Math.pow(2, attempt), MAX_DELAY);
    var jitter = exp * JITTER_RATIO * (Math.random() * 2 - 1);
    return Math.max(0, exp + jitter);
  }

  /** Update the connection indicator in the status bar. */
  function setStatus(connected) {
    var el = document.getElementById("ws-status");
    if (!el) return;
    if (connected) {
      el.classList.add("connected");
      el.title = "WebSocket connected";
    } else {
      el.classList.remove("connected");
      el.title = "WebSocket disconnected";
    }
  }

  /** Build the WebSocket URL from the current location. */
  function wsUrl() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    return proto + "//" + location.host + WS_PATH;
  }

  /** Dispatch a CustomEvent with the parsed message data. */
  function dispatchUpdate(data) {
    document.dispatchEvent(
      new CustomEvent("pilot-update", { detail: data })
    );
  }

  /** Update status-bar widgets from incoming data. */
  function updateStatusBar(data) {
    if (data.vehicle_name) {
      var el = document.getElementById("vehicle-name");
      if (el) el.textContent = data.vehicle_name;
    }
    if (data.state) {
      var stateEl = document.getElementById("vehicle-state");
      if (stateEl) stateEl.textContent = data.state;
    }
    if (data.battery_level != null) {
      var socEl = document.getElementById("status-soc");
      if (socEl) socEl.textContent = data.battery_level;
    }
    if (data.battery_range != null) {
      var rangeEl = document.getElementById("status-range");
      if (rangeEl) rangeEl.textContent = Math.round(data.battery_range);
    }
  }

  function connect() {
    if (disposed) return;

    ws = new WebSocket(wsUrl());

    ws.onopen = function () {
      attempt = 0;
      setStatus(true);
      console.info("[pilot-ws] connected");
    };

    ws.onmessage = function (event) {
      try {
        var data = JSON.parse(event.data);
        updateStatusBar(data);
        dispatchUpdate(data);
      } catch (err) {
        console.warn("[pilot-ws] bad message:", err);
      }
    };

    ws.onclose = function (event) {
      setStatus(false);
      if (disposed) return;
      attempt++;
      var delay = backoffDelay();
      console.info(
        "[pilot-ws] closed (code " + event.code + "), reconnecting in " +
        Math.round(delay) + " ms (attempt " + attempt + ")"
      );
      timer = setTimeout(connect, delay);
    };

    ws.onerror = function () {
      // onclose will fire right after, which handles reconnection
      setStatus(false);
    };
  }

  /** Public: close the socket and stop reconnecting. */
  function dispose() {
    disposed = true;
    clearTimeout(timer);
    if (ws) {
      ws.onclose = null;
      ws.close();
    }
  }

  // ---- Boot ----
  document.addEventListener("DOMContentLoaded", function () {
    connect();
  });

  // Clean up on page unload
  window.addEventListener("beforeunload", dispose);

  // Expose for programmatic use
  window.pilotWs = {
    dispose: dispose,
    reconnect: function () {
      dispose();
      disposed = false;
      attempt = 0;
      connect();
    }
  };
})();
