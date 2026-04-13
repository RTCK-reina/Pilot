/**
 * PiLot SPA Navigation
 *
 * Intercepts sidebar / bottom-nav link clicks, fetches the /fragment/*
 * endpoint, swaps the #content innerHTML, and updates history via
 * pushState.  Falls back to full page load on error.
 */
(function () {
  "use strict";

  const CONTENT_ID = "content";

  /** Map full-page paths to their fragment equivalents. */
  function toFragment(href) {
    const url = new URL(href, location.origin);
    const path = url.pathname === "/" ? "/home" : url.pathname;
    return "/fragment" + path;
  }

  /**
   * Fetch a fragment and swap it into #content.
   * Returns true on success, false on failure.
   */
  async function navigate(href, pushHistory) {
    const fragmentUrl = toFragment(href);
    const content = document.getElementById(CONTENT_ID);
    if (!content) return false;

    try {
      const res = await fetch(fragmentUrl);
      if (!res.ok) throw new Error(res.statusText);
      const html = await res.text();

      content.innerHTML = html;

      // Update active state on nav links
      updateActiveLinks(href);

      if (pushHistory) {
        history.pushState({ href: href }, "", href);
      }

      // Scroll to top of content
      content.scrollTo({ top: 0, behavior: "instant" });

      // Re-run any inline <script> in the fragment (rare but possible)
      content.querySelectorAll("script").forEach(function (old) {
        var s = document.createElement("script");
        s.textContent = old.textContent;
        old.replaceWith(s);
      });

      // Dispatch event so other modules can react
      document.dispatchEvent(
        new CustomEvent("pilot-navigate", { detail: { href: href } })
      );

      return true;
    } catch (err) {
      console.warn("[pilot] SPA navigation failed, falling back:", err);
      return false;
    }
  }

  /** Sync the --active class on both sidebar and bottom-nav links. */
  function updateActiveLinks(href) {
    var url = new URL(href, location.origin);
    var path = url.pathname;

    document.querySelectorAll("[data-nav]").forEach(function (link) {
      var linkPath = new URL(link.href, location.origin).pathname;
      var isActive = linkPath === path;

      // Sidebar
      link.classList.toggle("sidebar__link--active", isActive);
      // Bottom nav
      link.classList.toggle("bottom-nav__link--active", isActive);
    });
  }

  /** Attach click listeners to all [data-nav] links. */
  function bindNavLinks() {
    document.addEventListener("click", function (e) {
      var link = e.target.closest("[data-nav]");
      if (!link) return;

      e.preventDefault();
      var href = link.getAttribute("href");
      navigate(href, true).then(function (ok) {
        if (!ok) {
          location.href = href; // fallback
        }
      });
    });
  }

  /** Handle browser back/forward. */
  function bindPopstate() {
    window.addEventListener("popstate", function (e) {
      var href = (e.state && e.state.href) || location.pathname;
      navigate(href, false);
    });
  }

  /** Replace initial state so popstate works for the landing page. */
  function initState() {
    history.replaceState({ href: location.pathname }, "", location.pathname);
  }

  // ---- Boot ----
  document.addEventListener("DOMContentLoaded", function () {
    initState();
    bindNavLinks();
    bindPopstate();
  });
})();
