/* AI Analysis Lab — frontend for Stage 1 + Stage 2 backends:
 *   Smart Understanding  -> POST /api/smart_analyze_v2
 *   Code Understanding   -> POST /api/code/analyze
 *   Performance          -> POST /api/code/performance
 */
(function () {
    "use strict";

    function $(id) { return document.getElementById(id); }

    function esc(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function setStatus(el, msg, kind) {
        el.textContent = msg || "";
        el.className = "lab-status" + (kind ? " " + kind : "");
    }

    // POST JSON to an authenticated endpoint, handling login redirects gracefully.
    async function postJSON(url, payload) {
        const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify(payload),
        });
        if (res.redirected || res.status === 401 || res.status === 403) {
            throw new Error("Please log in to use the AI Analysis Lab.");
        }
        let data = null;
        let parseFailed = false;
        try {
            data = await res.json();
        } catch (e) {
            parseFailed = true;
        }
        if (!res.ok) {
            throw new Error(data && data.error ? data.error : "Request failed (" + res.status + ").");
        }
        if (parseFailed) {
            throw new Error("Unexpected server response (status " + res.status + ").");
        }
        return data;
    }

    // ---------------- Tabs ----------------
    function initTabs() {
        const tabs = document.querySelectorAll(".lab-tab");
        tabs.forEach(function (tab) {
            tab.addEventListener("click", function () {
                tabs.forEach(function (t) { t.classList.remove("active"); });
                document.querySelectorAll(".lab-panel").forEach(function (p) { p.classList.remove("active"); });
                tab.classList.add("active");
                const panel = $("panel-" + tab.getAttribute("data-tab"));
                if (panel) panel.classList.add("active");
            });
        });
    }

    function pct(x) { return Math.round((Number(x) || 0) * 100); }

    // ---------------- Smart Understanding ----------------
    function renderUnderstanding(d) {
        const ctx = d.context || {};
        $("suLang").textContent = (ctx.language || "?").toUpperCase();
        $("suLevel").textContent = ctx.level || "?";
        $("suDomain").textContent = ctx.domain || "?";
        const conf = pct(ctx.domain_confidence);
        $("suDomainConf").style.width = conf + "%";
        $("suDomainConfVal").textContent = conf + "% confidence";

        const ents = (d.entities && d.entities.entities) || [];
        $("suConceptCount").textContent = ents.length;
        $("suConcepts").innerHTML = ents.length
            ? ents.map(function (e) {
                return '<span class="chip" title="' + esc(e.method || "") + '">' +
                    esc(e.text) + '<span class="chip-tag">' + esc(e.type || "") + '</span></span>';
            }).join("")
            : '<div class="empty">No concepts detected.</div>';

        const clusters = (d.clusters && d.clusters.clusters) || [];
        $("suClusterCount").textContent = clusters.length;
        $("suClusters").innerHTML = clusters.length
            ? clusters.map(function (c) {
                const members = (c.members || []).map(function (m) {
                    return '<span class="chip small">' + esc(m) + '</span>';
                }).join("");
                return '<div class="cluster-card">' +
                    '<div class="cluster-name"><i class="fas fa-layer-group"></i> ' +
                    esc(c.suggested_name || ("Cluster " + c.cluster_id)) +
                    '<span class="count-badge">' + (c.size || 0) + '</span></div>' +
                    '<div class="chip-cloud">' + members + '</div></div>';
            }).join("")
            : '<div class="empty">Not enough concepts to cluster.</div>';

        const rels = d.relations || [];
        $("suRelationCount").textContent = rels.length;
        $("suRelations").innerHTML = rels.length
            ? rels.map(function (r) {
                return '<div class="relation-row">' +
                    '<span class="rel-node">' + esc(r.source) + '</span>' +
                    '<span class="rel-edge">' + esc(r.type) + ' <i class="fas fa-arrow-right"></i></span>' +
                    '<span class="rel-node">' + esc(r.target) + '</span></div>';
            }).join("")
            : '<div class="empty">No relations detected.</div>';

        $("suResults").style.display = "block";
    }

    async function runUnderstanding() {
        const text = $("suInput").value.trim();
        const status = $("suStatus");
        if (text.length < 20) { setStatus(status, "Enter at least 20 characters.", "warn"); return; }
        setStatus(status, "Analyzing…", "loading");
        $("suAnalyzeBtn").disabled = true;
        try {
            const d = await postJSON("/api/smart_analyze_v2", { text: text });
            renderUnderstanding(d);
            setStatus(status, "Done.", "ok");
        } catch (e) {
            setStatus(status, e.message, "error");
        } finally {
            $("suAnalyzeBtn").disabled = false;
        }
    }

    // ---------------- Code Understanding ----------------
    function metricCard(label, value) {
        return '<div class="meta-card"><div class="meta-label">' + esc(label) +
            '</div><div class="meta-value">' + esc(value) + '</div></div>';
    }

    function complexityClass(c) {
        c = Number(c) || 0;
        if (c >= 10) return "cx-high";
        if (c >= 5) return "cx-mid";
        return "cx-low";
    }

    function renderCode(d) {
        const m = d.metrics || {};
        $("codeMetrics").innerHTML =
            metricCard("Functions", m.total_functions) +
            metricCard("Classes", m.total_classes) +
            metricCard("Imports", m.total_imports) +
            metricCard("Max complexity", m.max_complexity) +
            metricCard("Avg complexity", m.avg_complexity) +
            metricCard("Max nesting", m.max_nesting);

        const funcs = (d.structure && d.structure.functions) || [];
        $("codeFuncCount").textContent = funcs.length;
        $("codeFunctions").innerHTML = funcs.length
            ? funcs.map(function (f) {
                const params = (f.parameters || []).join(", ");
                return '<div class="func-row">' +
                    '<div class="func-sig"><span class="func-name">' + esc(f.name) + '</span>' +
                    '<span class="func-params">(' + esc(params) + ')</span></div>' +
                    '<div class="func-meta">' +
                    '<span class="complexity-badge ' + complexityClass(f.complexity) + '">cc ' + esc(f.complexity) + '</span>' +
                    '<span class="nest-badge">nesting ' + esc(f.max_nesting) + '</span>' +
                    '<span class="line-badge">L' + esc(f.start_line) + '–' + esc(f.end_line) + '</span>' +
                    '</div></div>';
            }).join("")
            : '<div class="empty">No functions found.</div>';

        const classes = (d.structure && d.structure.classes) || [];
        $("codeClassCount").textContent = classes.length;
        $("codeClassBlock").style.display = classes.length ? "block" : "none";
        $("codeClasses").innerHTML = classes.map(function (c) {
            const methods = (c.methods || []).length;
            return '<span class="chip">' + esc(c.name) +
                '<span class="chip-tag">' + methods + ' methods</span></span>';
        }).join("");

        const cg = d.call_graph || [];
        $("codeCallCount").textContent = cg.length;
        $("codeCallGraph").innerHTML = cg.length
            ? cg.map(function (c) {
                return '<div class="relation-row">' +
                    '<span class="rel-node">' + esc(c.caller) + '</span>' +
                    '<span class="rel-edge">calls <i class="fas fa-arrow-right"></i></span>' +
                    '<span class="rel-node">' + esc(c.callee) + '</span></div>';
            }).join("")
            : '<div class="empty">No calls detected.</div>';

        $("codeResults").style.display = "block";
    }

    async function runCode() {
        const code = $("codeInput").value;
        const status = $("codeStatus");
        if (code.trim().length < 5) { setStatus(status, "Enter some code first.", "warn"); return; }
        setStatus(status, "Parsing…", "loading");
        $("codeAnalyzeBtn").disabled = true;
        try {
            const d = await postJSON("/api/code/analyze", { code: code, language: $("codeLang").value });
            renderCode(d);
            setStatus(status, d.summary || "Done.", "ok");
        } catch (e) {
            setStatus(status, e.message, "error");
        } finally {
            $("codeAnalyzeBtn").disabled = false;
        }
    }

    // ---------------- Performance ----------------
    function scoreColor(s) {
        if (s >= 80) return "#2ecc71";
        if (s >= 60) return "#f1c40f";
        if (s >= 40) return "#e67e22";
        return "#e74c3c";
    }

    function renderPerf(d) {
        const score = Number(d.performance_score) || 0;
        const ring = $("perfScoreRing");
        const col = scoreColor(score);
        const deg = score * 3.6;
        ring.style.background = "conic-gradient(" + col + " 0deg, " + col + " " + deg +
            "deg, rgba(255,255,255,0.08) " + deg + "deg, rgba(255,255,255,0.08) 360deg)";
        $("perfScore").textContent = score;
        $("perfOverall").textContent = d.overall_complexity || "O(1)";

        const funcs = d.functions || [];
        $("perfFuncCount").textContent = funcs.length;
        $("perfFunctions").innerHTML = funcs.length
            ? funcs.map(function (f) {
                const issues = (f.issues || []).map(function (i) {
                    return '<span class="issue-pill">' + esc(i) + '</span>';
                }).join("");
                return '<div class="func-row">' +
                    '<div class="func-sig"><span class="func-name">' + esc(f.name) + '</span>' +
                    '<span class="complexity-badge ' + (f.issues && f.issues.length ? "cx-high" : "cx-low") + '">' +
                    esc(f.time_complexity) + '</span></div>' +
                    '<div class="func-meta">' +
                    '<span class="nest-badge">loops ' + esc(f.loop_depth) + '</span>' +
                    '<span class="nest-badge">cc ' + esc(f.cyclomatic_complexity) + '</span>' +
                    (f.is_recursive ? '<span class="rec-badge">recursive ×' + esc(f.recursive_calls) + '</span>' : '') +
                    '<span class="line-badge">' + esc(f.length) + ' lines</span>' +
                    '</div>' +
                    (issues ? '<div class="issue-row">' + issues + '</div>' : '') +
                    '</div>';
            }).join("")
            : '<div class="empty">No functions found.</div>';

        const bn = d.bottlenecks || [];
        $("perfBottleneckCount").textContent = bn.length;
        $("perfBottleneckBlock").style.display = bn.length ? "block" : "none";
        $("perfBottlenecks").innerHTML = bn.map(function (b) {
            const issues = (b.issues || []).map(function (i) {
                return '<span class="issue-pill">' + esc(i) + '</span>';
            }).join("");
            return '<div class="bottleneck-row">' +
                '<div class="bn-head"><i class="fas fa-triangle-exclamation"></i> ' +
                '<span class="func-name">' + esc(b.name) + '</span>' +
                '<span class="complexity-badge cx-high">' + esc(b.time_complexity) + '</span></div>' +
                '<div class="issue-row">' + issues + '</div></div>';
        }).join("");

        const sg = d.suggestions || [];
        $("perfSuggestCount").textContent = sg.length;
        $("perfSuggestBlock").style.display = sg.length ? "block" : "none";
        $("perfSuggestions").innerHTML = sg.map(function (s) {
            return '<div class="suggestion-row"><i class="fas fa-lightbulb"></i> ' + esc(s) + '</div>';
        }).join("");

        $("perfResults").style.display = "block";
    }

    async function runPerf() {
        const code = $("perfInput").value;
        const status = $("perfStatus");
        if (code.trim().length < 5) { setStatus(status, "Enter some code first.", "warn"); return; }
        setStatus(status, "Analyzing performance…", "loading");
        $("perfAnalyzeBtn").disabled = true;
        try {
            const d = await postJSON("/api/code/performance", { code: code, language: $("perfLang").value });
            renderPerf(d);
            setStatus(status, d.summary || "Done.", "ok");
        } catch (e) {
            setStatus(status, e.message, "error");
        } finally {
            $("perfAnalyzeBtn").disabled = false;
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!$("analysisLab")) return;
        initTabs();
        $("suAnalyzeBtn").addEventListener("click", runUnderstanding);
        $("codeAnalyzeBtn").addEventListener("click", runCode);
        $("perfAnalyzeBtn").addEventListener("click", runPerf);
    });
})();
