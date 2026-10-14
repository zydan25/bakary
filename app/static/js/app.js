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

  function normalizePath(path) {
    let value = path || "/";
    while (value.length > 1 && value.endsWith("/")) value = value.slice(0, -1);
    return value;
  }
  const currentPath = normalizePath(window.location.pathname);
  const routeCandidates = [...document.querySelectorAll("[data-nav-link]")].map((link) => {
    try {
      const target = new URL(link.href, window.location.origin);
      const linkPath = normalizePath(target.pathname);
      const matches = currentPath === linkPath || (linkPath !== "/" && currentPath.startsWith(linkPath + "/"));
      return matches ? { link, linkPath, section: link.closest("[data-nav-section]") } : null;
    } catch (_) {
      return null;
    }
  }).filter(Boolean).sort((a, b) => b.linkPath.length - a.linkPath.length);

  const activeCandidate = routeCandidates[0];
  const activeSection = activeCandidate ? activeCandidate.section : null;
  if (activeCandidate) activeCandidate.link.classList.add("is-active");

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

  // Reusable dialogs: account settings, forms, and app-style confirmations.
  document.querySelectorAll("[data-open-dialog]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const dialog = document.getElementById(trigger.dataset.openDialog);
      if (!dialog) return;
      try { if (!dialog.open) dialog.showModal(); } catch (_) {}
    });
  });
  document.querySelectorAll("dialog[data-auto-open='true']").forEach((dialog) => {
    try { if (!dialog.open) dialog.showModal(); } catch (_) {}
  });
  document.querySelectorAll("dialog.form-dialog, dialog.app-form-dialog, dialog.app-confirm-dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    dialog.querySelectorAll("[data-close-dialog]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
  });

  const logoutForm = document.querySelector("form[data-app-logout]");
  const logoutDialog = document.getElementById("logout-confirm-dialog");
  if (logoutForm && logoutDialog) {
    const cancelLogout = logoutDialog.querySelector("[data-cancel-logout]");
    const confirmLogout = logoutDialog.querySelector("[data-confirm-logout]");
    logoutForm.addEventListener("submit", (event) => {
      if (logoutForm.dataset.confirmed === "true") return;
      event.preventDefault();
      try { if (!logoutDialog.open) logoutDialog.showModal(); } catch (_) {}
    });
    if (cancelLogout) cancelLogout.addEventListener("click", () => logoutDialog.close());
    if (confirmLogout) confirmLogout.addEventListener("click", () => {
      logoutDialog.close();
      logoutForm.dataset.confirmed = "true";
      if (logoutForm.requestSubmit) logoutForm.requestSubmit();
      else logoutForm.submit();
    });
  }

  // App exit is independent from logout. If the PWA host blocks window.close(),
  // replace the current view with a blank page so the app UI is dismissed without logging out.
  const exitDialog = document.getElementById("exit-confirm-dialog");
  if (exitDialog) {
    const cancelExit = exitDialog.querySelector("[data-cancel-exit]");
    const confirmExit = exitDialog.querySelector("[data-confirm-exit]");

    if (cancelExit) cancelExit.addEventListener("click", () => exitDialog.close());
    if (confirmExit) confirmExit.addEventListener("click", () => {
      exitDialog.close();

      try {
        if (window.navigator.app && typeof window.navigator.app.exitApp === "function") {
          window.navigator.app.exitApp();
          return;
        }
      } catch (_) {}

      try { window.close(); } catch (_) {}

      // The web platform has no universal PWA close API. Replace this view rather than
      // displaying a repeated warning or logging the manager out.
      window.setTimeout(() => {
        if (document.visibilityState !== "hidden") {
          window.location.replace("about:blank");
        }
      }, 180);
    });
  }

  // Instant Arabic amount and quantity wording. The server still validates monetary values.
  const digitMap = { "٠":"0", "١":"1", "٢":"2", "٣":"3", "٤":"4", "٥":"5", "٦":"6", "٧":"7", "٨":"8", "٩":"9",
    "۰":"0", "۱":"1", "۲":"2", "۳":"3", "۴":"4", "۵":"5", "۶":"6", "۷":"7", "۸":"8", "۹":"9" };
  function numericText(value) {
    return String(value || "").replace(/[٠-٩۰-۹]/g, (digit) => digitMap[digit])
      .replace(/٬/g, "").replace(/٫/g, ".").replace(/,/g, "").trim();
  }
  const ones = ["صفر","واحد","اثنان","ثلاثة","أربعة","خمسة","ستة","سبعة","ثمانية","تسعة"];
  const teens = ["عشرة","أحد عشر","اثنا عشر","ثلاثة عشر","أربعة عشر","خمسة عشر","ستة عشر","سبعة عشر","ثمانية عشر","تسعة عشر"];
  const tens = ["","","عشرون","ثلاثون","أربعون","خمسون","ستون","سبعون","ثمانون","تسعون"];
  const hundreds = ["","مائة","مائتان","ثلاثمائة","أربعمائة","خمسمائة","ستمائة","سبعمائة","ثمانمائة","تسعمائة"];
  function underThousand(number) {
    number = Math.floor(number);
    const parts = [];
    const h = Math.floor(number / 100);
    const r = number % 100;
    if (h) parts.push(hundreds[h]);
    if (r >= 1 && r <= 9) parts.push(ones[r]);
    else if (r >= 10 && r <= 19) parts.push(teens[r - 10]);
    else if (r >= 20) {
      const u = r % 10;
      if (u) parts.push(ones[u]);
      parts.push(tens[Math.floor(r / 10)]);
    }
    return parts.join(" و ");
  }
  function integerWords(value) {
    let number = Math.abs(Math.floor(value));
    if (!number) return "صفر";
    const scales = [
      [1000000000, "مليار", "ملياران", "مليارات"],
      [1000000, "مليون", "مليونان", "ملايين"],
      [1000, "ألف", "ألفان", "آلاف"]
    ];
    const parts = [];
    for (const [scale, singular, dual, plural] of scales) {
      const group = Math.floor(number / scale);
      number %= scale;
      if (!group) continue;
      if (group === 1) parts.push(singular);
      else if (group === 2) parts.push(dual);
      else if (group >= 3 && group <= 10) parts.push(underThousand(group) + " " + plural);
      else parts.push(underThousand(group) + " " + singular);
    }
    if (number) parts.push(underThousand(number));
    return parts.join(" و ");
  }
  function amountWords(raw, currency) {
    const text = numericText(raw);
    if (!text || !/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(text)) return "";
    const number = Number(text);
    if (!Number.isFinite(number) || Math.abs(number) > 999999999999.99) return "";
    const cents = Math.round(Math.abs(number) * 100);
    const whole = Math.floor(cents / 100);
    const fraction = cents % 100;
    let phrase = integerWords(whole) + " " + (currency || "ريال");
    if (fraction) phrase += " و " + integerWords(fraction) + " فلس";
    return number < 0 ? "سالب " + phrase : phrase;
  }
  function quantityWords(raw, unit) {
    const text = numericText(raw);
    if (!text || !/^[+]?(?:\d+\.?\d*|\.\d+)$/.test(text)) return "";
    const number = Number(text);
    if (!Number.isFinite(number) || number < 0 || number > 999999999999) return "";
    const whole = Math.floor(number);
    const fraction = Number((number - whole).toFixed(3));
    let phrase = integerWords(whole) + " " + (unit || "حبة");
    if (fraction) {
      const digits = String(fraction).split(".")[1] || "";
      phrase += " و " + integerWords(Number(digits)) + " من " +
        (digits.length === 1 ? "عشرة" : digits.length === 2 ? "مائة" : "ألف") + " " + (unit || "حبة");
    }
    return phrase;
  }
  document.querySelectorAll("[data-amount-words='true'], [data-quantity-words='true']").forEach((input) => {
    const parent = input.parentElement;
    if (!parent) return;
    let output = [...parent.children].find((child) => child.matches("[data-words-output]"));
    if (!output) {
      output = document.createElement("small");
      output.dataset.wordsOutput = "true";
      output.className = "amount-words";
      output.setAttribute("aria-live", "polite");
      input.insertAdjacentElement("afterend", output);
    }
    const refresh = () => {
      const phrase = input.dataset.quantityWords === "true"
        ? quantityWords(input.value, input.dataset.unit || "حبة")
        : amountWords(input.value, input.dataset.currency || "ريال");
      output.textContent = phrase;
      output.hidden = !phrase;
    };
    input.addEventListener("input", refresh);
    input.addEventListener("change", refresh);
    refresh();
  });

  // Save a compact receipt to PNG using browser canvas; no external image service is required.
  document.querySelectorAll("[data-save-receipt]").forEach((button) => {
    button.addEventListener("click", () => {
      const lines = [
        button.dataset.receiptTitle || "إيصال",
        "نظام إدارة المخبز",
        "الحساب: " + (button.dataset.receiptParty || ""),
        "التاريخ: " + (button.dataset.receiptDate || ""),
        "الكمية: " + (button.dataset.receiptQuantity || ""),
        "الإجمالي/المدفوع: " + (button.dataset.receiptTotal || "") + " ريال",
        button.dataset.receiptDetail || "",
        "برمجة وتصميم م. زيدان العطاب",
        "يمن كود للتقنيات الذكية"
      ].filter(Boolean);
      const canvas = document.createElement("canvas");
      const width = 900;
      const rowHeight = 58;
      canvas.width = width * 2;
      canvas.height = (lines.length * rowHeight + 70) * 2;
      const context = canvas.getContext("2d");
      context.scale(2, 2);
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, width, canvas.height / 2);
      context.fillStyle = "#1a56db";
      context.fillRect(0, 0, width, 12);
      context.direction = "rtl";
      context.textAlign = "right";
      context.fillStyle = "#182235";
      context.font = "bold 28px Tahoma, Arial, sans-serif";
      lines.forEach((line, index) => {
        context.font = index === 0 ? "bold 30px Tahoma, Arial, sans-serif" : "bold 22px Tahoma, Arial, sans-serif";
        context.fillStyle = index === 0 ? "#1a56db" : "#273246";
        context.fillText(line, width - 36, 56 + index * rowHeight, width - 72);
        if (index < lines.length - 1) {
          context.strokeStyle = "#e2e7ef";
          context.beginPath();
          context.moveTo(30, 72 + index * rowHeight);
          context.lineTo(width - 30, 72 + index * rowHeight);
          context.stroke();
        }
      });
      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "bakary-receipt-" + (button.dataset.receiptDate || "today") + ".png";
        anchor.click();
        URL.revokeObjectURL(url);
      }, "image/png");
    });
  });

  // Whole profile cards can be opened by clicking empty space or using Enter/Space.
  document.querySelectorAll("[data-card-navigation]").forEach((card) => {
    card.addEventListener("click", (event) => {
      if (event.target.closest("a, button, form, input, select, textarea, label, summary")) return;
      window.location.href = card.dataset.cardNavigation;
    });
    card.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && event.target === card) {
        event.preventDefault();
        window.location.href = card.dataset.cardNavigation;
      }
    });
    card.style.cursor = "pointer";
  });

  // Live card filtering with no full-page reload while typing.
  document.querySelectorAll("form[data-live-filter-target]").forEach((form) => {
    const search = form.querySelector("[name='q']");
    const target = document.querySelector(form.dataset.liveFilterTarget);
    if (search && target) {
      search.addEventListener("input", () => {
        const needle = search.value.trim().toLocaleLowerCase();
        target.querySelectorAll("[data-searchable-card]").forEach((card) => {
          const text = (card.dataset.searchText || card.textContent || "").toLocaleLowerCase();
          card.hidden = Boolean(needle) && !text.includes(needle);
        });
      });
    }
    form.querySelectorAll("select[data-live-submit]").forEach((select) => {
      select.addEventListener("change", () => form.requestSubmit());
    });
  });

  // White searchable dropdown for selects explicitly marked by templates.
  document.querySelectorAll("select[data-searchable='true']").forEach((select) => {
    if (select.dataset.searchEnhanced === "true") return;
    select.dataset.searchEnhanced = "true";
    const parent = select.parentElement;
    if (!parent) return;
    const wrapper = document.createElement("div");
    wrapper.className = "smart-select";
    parent.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    select.classList.add("smart-select-native");
    select.setAttribute("aria-hidden", "true");
    select.tabIndex = -1;

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "smart-select-trigger";
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-haspopup", "listbox");
    const menu = document.createElement("div");
    menu.className = "smart-select-menu";
    menu.hidden = true;
    const search = document.createElement("input");
    search.type = "search";
    search.className = "smart-select-search";
    search.placeholder = "بحث فوري...";
    search.setAttribute("aria-label", "بحث في الخيارات");
    const options = document.createElement("div");
    options.className = "smart-select-options";
    options.setAttribute("role", "listbox");
    menu.append(search, options);
    wrapper.append(trigger, menu);

    function syncValue() {
      const selected = select.options[select.selectedIndex];
      trigger.textContent = selected ? selected.textContent.trim() : "اختر...";
      options.querySelectorAll("button").forEach((button) => {
        button.classList.toggle("is-selected", button.dataset.value === select.value);
        button.setAttribute("aria-selected", String(button.dataset.value === select.value));
      });
    }
    function closeMenu() {
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
      wrapper.classList.remove("is-open");
    }
    function openMenu() {
      menu.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      wrapper.classList.add("is-open");
      search.value = "";
      options.querySelectorAll("button").forEach((button) => { button.hidden = false; });
      search.focus();
    }
    [...select.options].forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "smart-select-option";
      button.textContent = option.textContent.trim();
      button.dataset.value = option.value;
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(option.selected));
      button.disabled = option.disabled;
      button.addEventListener("click", () => {
        select.value = option.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncValue();
        closeMenu();
      });
      options.appendChild(button);
    });
    trigger.addEventListener("click", () => menu.hidden ? openMenu() : closeMenu());
    trigger.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") { event.preventDefault(); openMenu(); }
    });
    search.addEventListener("input", () => {
      const needle = search.value.trim().toLocaleLowerCase();
      options.querySelectorAll("button").forEach((button) => {
        button.hidden = !button.textContent.toLocaleLowerCase().includes(needle);
      });
    });
    select.addEventListener("change", syncValue);
    document.addEventListener("click", (event) => {
      if (!wrapper.contains(event.target)) closeMenu();
    });
    syncValue();
  });

})();
