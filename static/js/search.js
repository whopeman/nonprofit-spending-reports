/*
  static/js/search.js
  Project : Non-Profit Spending Reports
  Date    : 2026-10-26
  Purpose : Client-side search over search/orgs.json (every organization
            with a page). Results are built with DOM methods only (no innerHTML).
  Change log:
    2026-10-26  0.1.0  Initial version.
    2026-10-28  0.1.0  Organizations only; no people search.
*/
(function () {
  "use strict";
  var input = document.getElementById("q");
  var list = document.getElementById("results");
  var status = document.getElementById("search-status");
  if (!input || !list || !status) return;
  var root = input.getAttribute("data-root") || "";
  var cache = {};
  var MAX = 50;
  var timer = null;

  status.textContent = "Type at least 2 letters.";

  function load(name) {
    if (!cache[name]) {
      cache[name] = fetch(root + "search/" + name + ".json")
        .then(function (r) { return r.ok ? r.json() : []; })
        .catch(function () { return []; });
    }
    return cache[name];
  }

  function norm(s) {
    return s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  function matches(name, words) {
    var n = norm(name);
    for (var i = 0; i < words.length; i++) {
      if (n.indexOf(words[i]) === -1) return false;
    }
    return true;
  }

  function item(href, text, kind) {
    var li = document.createElement("li");
    var a = document.createElement("a");
    a.href = root + href;
    a.textContent = text;
    var span = document.createElement("span");
    span.className = "kind";
    span.textContent = kind;
    li.appendChild(a);
    li.appendChild(span);
    return li;
  }

  function run() {
    var q = norm(input.value.trim());
    var words = q.split(/\s+/).filter(Boolean);
    list.replaceChildren();
    if (q.length < 2) { status.textContent = "Type at least 2 letters."; return; }
    load("orgs").then(function (all) {
      if (norm(input.value.trim()) !== q) return; // a newer search is running
      var orgs = all.filter(function (o) { return matches(o[0], words); });
      var shown = 0;
      orgs.slice(0, MAX).forEach(function (o) {
        var place = [o[1], o[2]].filter(Boolean).join(", ");
        list.appendChild(item(o[4], o[0], "Organization" + (place ? ", " + place : "") + ", rank " + o[3]));
        shown++;
      });
      var total = orgs.length;
      status.textContent = total === 0 ? "No matches."
        : total > shown ? "Showing " + shown + " of " + total + " matches. Add words to narrow it."
        : total + (total === 1 ? " match." : " matches.");
    });
  }

  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(run, 150);
  });
})();
