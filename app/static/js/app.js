(() => {
  "use strict";

  const sidebar = document.getElementById("main-sidebar");
  const openers = document.querySelectorAll("[data-open-drawer]");
  const closers = document.querySelectorAll("[data-close-drawer]");

  function setDrawer(open) {
    document.body.classList.toggle("drawer-open", Boolean(open));
    if (sidebar) sidebar.setAttribute("aria-hidden", String(!open && window.matchMedia("(max-width: 900px)").matches));
    if (open && sidebar) {
      const firstLink = sidebar.querySelector("a[href]");
      if (firstLink && window.matchMedia("(max-width: 900px)").matches) firstLink.focus();
    }
  }

  openers.forEach((button) => button.addEventListener("click", () => setDrawer(true)));
  closers.forEach((button) => button.addEventListener("click", () => setDrawer(false)));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setDrawer(false);
  });

  const sections = [...document.querySelectorAll("[data-nav-section]")];
  const storageKey = "bakary.navigation.openSection";
  let savedSection = null;
  try { savedSection = window.localStorage.getItem(storageKey); } catch (_) {}

  function setSection(section, expanded, persist = true) {
    const button = section.querySelector("[data-nav-toggle]");
    const children = section.querySelector(".tree-children");
    if (!button || !children) return;
    button.setAttribute("aria-expanded", String(expanded));
    children.hidden = !expanded;
    section.classList.toggle("is-open", expanded);
    if (persist) {
      try {
        if (expanded) window.localStorage.setItem(storageKey, section.dataset.navSection);
        else if (window.localStorage.getItem(storageKey) === section.dataset.navSection) window.localStorage.removeItem(storageKey);
      } catch (_) {}
    }
  }

  sections.forEach((section) => {
    const button = section.querySelector("[data-nav-toggle]");
    if (button) {
      button.addEventListener("click", () => {
        const expanded = button.getAttribute("aria-expanded") !== "true";
        sections.forEach((other) => setSection(other, other === section ? expanded : false, other === section));
      });
    }
  });

  let activeSection = null;
  document.querySelectorAll("[data-nav-link]").forEach((link) => {
    try {
      const target = new URL(link.href, window.location.origin);
      if (target.pathname === window.location.pathname) {
        link.classList.add("is-active");
        activeSection = link.closest("[data-nav-section]");
      }
    } catch (_) {}
  });

  if (activeSection) {
    sections.forEach((section) => setSection(section, section === activeSection, false));
    try { window.localStorage.setItem(storageKey, activeSection.dataset.navSection); } catch (_) {}
  } else if (savedSection) {
    const found = sections.find((section) => section.dataset.navSection === savedSection);
    if (found) sections.forEach((section) => setSection(section, section === found, false));
  }

  document.querySelectorAll("[data-bottom-link]").forEach((link) => {
    try {
      if (new URL(link.href, window.location.origin).pathname === window.location.pathname) {
        link.classList.add("is-active");
      }
    } catch (_) {}
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm || "هل أنت متأكد؟")) event.preventDefault();
    });
  });

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (event.defaultPrevented) return;
      const button = form.querySelector("button[type='submit'], input[type='submit']");
      if (!button || button.disabled) return;
      if (form.checkValidity && !form.checkValidity()) return;
      if (button.dataset.loadingLabel) {
        button.dataset.originalLabel = button.textContent;
        button.textContent = button.dataset.loadingLabel;
        button.disabled = true;
        button.classList.add("is-loading");
      }
    });
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // The server-rendered application remains usable if installation is unavailable.
      });
    });
  }
})();
