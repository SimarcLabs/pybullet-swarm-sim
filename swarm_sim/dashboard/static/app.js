/* ═══════════════════════════════════════════════════════════════════════
   PyBullet Swarm Sim — Dashboard Controller
   Workflow: Configure → Run → Observe → Analyze → Benchmark → Export
   ═══════════════════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", () => {

    // ─── State ───
    let selectedAlgo = null;
    let eventSource = null;
    let currentJobId = null;
    let replayData = null;
    let replayAnimId = null;
    let replayIdx = 0;
    let replayPlaying = false;

    const WORKFLOW_STEPS = ["configure", "run", "observe", "analyze", "benchmark", "export"];

    // ─── Element refs ───
    const panels = {
        configure: document.getElementById("panel-configure"),
        observe:   document.getElementById("panel-observe"),
        analyze:   document.getElementById("panel-analyze"),
        benchmark: document.getElementById("panel-benchmark"),
        export:    document.getElementById("panel-export"),
    };

    const algoGrid          = document.getElementById("algo-grid");
    const dronesSlider      = document.getElementById("drones-slider");
    const dronesVal         = document.getElementById("drones-val");
    const btnDroneMinus     = document.getElementById("btn-drone-minus");
    const btnDronePlus      = document.getElementById("btn-drone-plus");
    const durationSlider    = document.getElementById("duration-slider");
    const durationVal       = document.getElementById("duration-val");
    const btnTimeMinus      = document.getElementById("btn-time-minus");
    const btnTimePlus       = document.getElementById("btn-time-plus");
    const btnLaunch         = document.getElementById("btn-launch");
    const extraOptionsGroup = document.getElementById("extra-options-container");
    const formSelectGroup   = document.getElementById("formation-select-group");
    const customUploadGroup = document.getElementById("custom-upload-group");
    const formationType     = document.getElementById("formation-type");
    const customFile        = document.getElementById("custom-file");
    const terminalContainer = document.getElementById("terminal-container");
    const terminalOutput    = document.getElementById("terminal-output");
    const terminalBadge     = document.getElementById("terminal-badge");

    const ovDrones   = document.getElementById("ov-drones");
    const ovDuration = document.getElementById("ov-duration");
    const ovStatus   = document.getElementById("ov-status");
    const ovProgress = document.getElementById("ov-progress");

    // ═══════════════════ WORKFLOW NAVIGATION ═══════════════════

    function navigateTo(stepName) {
        // Hide all panels
        Object.values(panels).forEach(p => {
            p.classList.remove("active");
        });

        // Show target panel
        const target = panels[stepName];
        if (target) {
            setTimeout(() => target.classList.add("active"), 30);
        }

        // Update workflow bar
        const steps = document.querySelectorAll(".workflow-step");
        const connectors = document.querySelectorAll(".workflow-connector");
        const targetIdx = WORKFLOW_STEPS.indexOf(stepName);

        steps.forEach((step, i) => {
            step.classList.remove("active", "completed");
            if (i < targetIdx) step.classList.add("completed");
            if (i === targetIdx) step.classList.add("active");
        });

        connectors.forEach((conn, i) => {
            conn.classList.toggle("filled", i < targetIdx);
        });
    }

    // Clickable workflow steps (only allow going to completed/active steps)
    document.querySelectorAll(".workflow-step").forEach(step => {
        step.addEventListener("click", () => {
            if (step.classList.contains("completed") || step.classList.contains("active")) {
                navigateTo(step.dataset.step);
            }
        });
    });

    // Panel navigation buttons
    document.getElementById("btn-to-analyze").addEventListener("click", () => {
        navigateTo("analyze");
        loadAnalysis();
    });
    document.getElementById("btn-back-observe").addEventListener("click", () => navigateTo("observe"));
    document.getElementById("btn-to-benchmark").addEventListener("click", () => {
        navigateTo("benchmark");
        loadBenchmark();
    });
    document.getElementById("btn-back-analyze").addEventListener("click", () => navigateTo("analyze"));
    document.getElementById("btn-to-export").addEventListener("click", () => navigateTo("export"));
    document.getElementById("btn-back-benchmark").addEventListener("click", () => navigateTo("benchmark"));
    document.getElementById("btn-new-run").addEventListener("click", resetToStart);

    // ═══════════════════ SLIDER LOGIC ═══════════════════

    function updateDroneVal() {
        dronesVal.textContent = dronesSlider.value;
        ovDrones.textContent = dronesSlider.value;
    }
    function updateDurationVal() {
        durationVal.textContent = durationSlider.value;
        ovDuration.innerHTML = `${durationSlider.value}<span class="unit">s</span>`;
    }

    dronesSlider.addEventListener("input", updateDroneVal);
    durationSlider.addEventListener("input", updateDurationVal);

    btnDroneMinus.addEventListener("click", () => {
        dronesSlider.value = Math.max(+dronesSlider.min, +dronesSlider.value - 1);
        updateDroneVal();
    });
    btnDronePlus.addEventListener("click", () => {
        dronesSlider.value = Math.min(+dronesSlider.max, +dronesSlider.value + 1);
        updateDroneVal();
    });
    btnTimeMinus.addEventListener("click", () => {
        dronesSlider.value; // force read
        durationSlider.value = Math.max(+durationSlider.min, +durationSlider.value - +durationSlider.step);
        updateDurationVal();
    });
    btnTimePlus.addEventListener("click", () => {
        durationSlider.value = Math.min(+durationSlider.max, +durationSlider.value + +durationSlider.step);
        updateDurationVal();
    });

    // ═══════════════════ ALGORITHM SELECTION ═══════════════════

    fetch("/algorithms")
        .then(res => res.json())
        .then(algos => {
            algos.forEach(algo => {
                const card = document.createElement("div");
                card.className = "algo-card";
                if (algo.is_custom) card.classList.add("custom-card");

                card.innerHTML = `
                    <div class="card-icon"><i class="${algo.icon}"></i></div>
                    <h3>${algo.name}</h3>
                    <p>${algo.desc}</p>
                `;

                card.addEventListener("click", () => selectAlgo(card, algo));
                algoGrid.appendChild(card);
            });
        });

    function selectAlgo(cardElem, algo) {
        document.querySelectorAll(".algo-card").forEach(c => c.classList.remove("selected"));
        document.querySelectorAll(".card-icon").forEach(icon => icon.classList.remove("orange"));

        cardElem.classList.add("selected");
        cardElem.querySelector(".card-icon").classList.add("orange");

        selectedAlgo = algo;
        btnLaunch.disabled = false;

        if (algo.has_shapes || algo.is_custom) {
            extraOptionsGroup.classList.remove("hidden");
            formSelectGroup.classList.toggle("hidden", !algo.has_shapes);
            customUploadGroup.classList.toggle("hidden", !algo.is_custom);
        } else {
            extraOptionsGroup.classList.add("hidden");
        }
    }

    // ═══════════════════ LAUNCH SIMULATION ═══════════════════

    btnLaunch.addEventListener("click", async () => {
        if (!selectedAlgo) return;

        const formData = new FormData();
        formData.append("algo", selectedAlgo.id);
        formData.append("drones", dronesSlider.value);
        formData.append("duration", durationSlider.value);

        if (selectedAlgo.has_shapes) {
            formData.append("formation_type", formationType.value);
        }

        if (selectedAlgo.is_custom) {
            if (customFile.files.length === 0) {
                alert("Please select a .py file to upload.");
                return;
            }
            formData.append("custom_file", customFile.files[0]);
        }

        // UI → running state
        btnLaunch.disabled = true;
        ovStatus.textContent = "RUNNING";
        terminalContainer.classList.remove("hidden");
        terminalOutput.innerHTML = "";
        terminalBadge.textContent = "RUNNING";
        ovProgress.textContent = "0%";

        // Mark "run" step active
        const steps = document.querySelectorAll(".workflow-step");
        steps[0].classList.add("completed");
        steps[0].classList.remove("active");
        steps[1].classList.add("active");
        document.querySelectorAll(".workflow-connector")[0].classList.add("filled");

        try {
            const res = await fetch("/run", { method: "POST", body: formData });
            const data = await res.json();
            currentJobId = data.job_id;
            streamLogs(data.job_id);
        } catch (e) {
            terminalOutput.innerHTML += `<div style="color:#ef4444">> Error: ${e}</div>`;
            btnLaunch.disabled = false;
            ovStatus.textContent = "ERROR";
            terminalBadge.textContent = "ERROR";
        }
    });

    // ═══════════════════ LOG STREAMING ═══════════════════

    function streamLogs(jobId) {
        eventSource = new EventSource(`/stream/${jobId}`);

        eventSource.onmessage = (e) => {
            const line = document.createElement("div");
            line.textContent = `> ${e.data}`;
            terminalOutput.appendChild(line);
            terminalOutput.scrollTop = terminalOutput.scrollHeight;
        };

        eventSource.addEventListener("progress", (e) => {
            const pct = e.data.replace("%", "");
            ovProgress.textContent = `${pct}%`;
        });

        eventSource.addEventListener("done", () => {
            eventSource.close();
            ovStatus.textContent = "COMPLETE";
            terminalBadge.textContent = "DONE";
            terminalBadge.style.background = "rgba(34,197,94,0.15)";
            terminalBadge.style.color = "#22c55e";

            // Brief delay then transition to observe
            setTimeout(() => loadResults(jobId), 1200);
        });

        eventSource.onerror = () => {
            eventSource.close();
            btnLaunch.disabled = false;
            ovStatus.textContent = "ERROR";
            terminalBadge.textContent = "ERROR";
        };
    }

    // ═══════════════════ LOAD RESULTS (OBSERVE PANEL) ═══════════════════

    async function loadResults(jobId) {
        navigateTo("observe");

        try {
            const res = await fetch(`/results/${jobId}`);
            const data = await res.json();

            if (data.error) {
                alert(data.error);
                return;
            }

            // Stats
            document.getElementById("obs-algo").textContent = data.metrics.algo.toUpperCase();
            document.getElementById("obs-drones").textContent = data.metrics.num_drones;
            document.getElementById("obs-duration").textContent = `${data.metrics.duration}s`;
            document.getElementById("obs-health").textContent =
                `${(data.metrics.health_score * 100).toFixed(1)}%`;

            // 3D Trajectory
            Plotly.newPlot("plotly-trajectory", data.plotly_data.data, data.plotly_data.layout, {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['toImage'],
                displaylogo: false,
            });

            // Load replay data
            loadReplay(jobId);

        } catch (e) {
            console.error("Failed to load results", e);
            alert("Failed to load results.");
        }
    }

    // ═══════════════════ 2D REPLAY ═══════════════════

    async function loadReplay(jobId) {
        try {
            const res = await fetch(`/replay/${jobId}`);
            replayData = await res.json();
            replayIdx = 0;
            drawReplayFrame(0);
        } catch (e) {
            console.error("Failed to load replay data", e);
        }
    }

    function drawReplayFrame(idx) {
        if (!replayData || !replayData.frames.length) return;

        const canvas = document.getElementById("replay-canvas");
        const ctx = canvas.getContext("2d");

        // Match canvas resolution to display size
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * window.devicePixelRatio;
        canvas.height = rect.height * window.devicePixelRatio;
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        const W = rect.width;
        const H = rect.height;

        const frame = replayData.frames[Math.min(idx, replayData.frames.length - 1)];
        const lo = replayData.bounds.lo;
        const hi = replayData.bounds.hi;

        ctx.clearRect(0, 0, W, H);

        // Background
        ctx.fillStyle = "#0a0a0a";
        ctx.fillRect(0, 0, W, H);

        // Grid
        ctx.strokeStyle = "#1a1a1a";
        ctx.lineWidth = 1;
        const gridStep = 40;
        for (let x = 0; x < W; x += gridStep) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
        }
        for (let y = 0; y < H; y += gridStep) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
        }

        const colors = [
            '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
            '#10b981', '#06b6d4', '#0ea5e9', '#3b82f6', '#6366f1',
            '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e'
        ];

        function mapX(v) { return ((v - lo[0]) / (hi[0] - lo[0])) * (W - 40) + 20; }
        function mapY(v) { return H - (((v - lo[1]) / (hi[1] - lo[1])) * (H - 40) + 20); }

        // Draw proximity lines
        const N = frame.pos.length;
        for (let i = 0; i < N; i++) {
            for (let j = i + 1; j < N; j++) {
                const dx = frame.pos[i][0] - frame.pos[j][0];
                const dy = frame.pos[i][1] - frame.pos[j][1];
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 2.0) {
                    const alpha = Math.max(0, 1 - dist / 2.0) * 0.3;
                    ctx.strokeStyle = `rgba(255, 77, 0, ${alpha})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(mapX(frame.pos[i][0]), mapY(frame.pos[i][1]));
                    ctx.lineTo(mapX(frame.pos[j][0]), mapY(frame.pos[j][1]));
                    ctx.stroke();
                }
            }
        }

        // Draw trail (last few frames)
        const trailLen = 8;
        for (let t = Math.max(0, idx - trailLen); t < idx; t++) {
            const f = replayData.frames[t];
            const age = (idx - t) / trailLen;
            const a = (1 - age) * 0.25;
            for (let i = 0; i < f.pos.length; i++) {
                const c = colors[i % colors.length];
                ctx.fillStyle = c.replace(')', `, ${a})`).replace('rgb', 'rgba');
                ctx.beginPath();
                ctx.arc(mapX(f.pos[i][0]), mapY(f.pos[i][1]), 2, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Draw drones
        for (let i = 0; i < frame.pos.length; i++) {
            const px = mapX(frame.pos[i][0]);
            const py = mapY(frame.pos[i][1]);
            const c = colors[i % colors.length];

            // Glow
            const grad = ctx.createRadialGradient(px, py, 0, px, py, 12);
            grad.addColorStop(0, c + "55");
            grad.addColorStop(1, c + "00");
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(px, py, 12, 0, Math.PI * 2);
            ctx.fill();

            // Core
            ctx.fillStyle = c;
            ctx.beginPath();
            ctx.arc(px, py, 4, 0, Math.PI * 2);
            ctx.fill();
        }

        // Timestamp label
        document.getElementById("replay-time").textContent = `t = ${frame.t.toFixed(3)}s`;
    }

    function playReplay() {
        if (!replayData || replayPlaying) return;
        replayPlaying = true;

        function tick() {
            if (!replayPlaying) return;
            if (replayIdx >= replayData.frames.length - 1) {
                replayPlaying = false;
                return;
            }
            replayIdx++;
            drawReplayFrame(replayIdx);
            replayAnimId = requestAnimationFrame(tick);
        }
        tick();
    }

    document.getElementById("btn-replay-play").addEventListener("click", playReplay);
    document.getElementById("btn-replay-pause").addEventListener("click", () => {
        replayPlaying = false;
        if (replayAnimId) cancelAnimationFrame(replayAnimId);
    });
    document.getElementById("btn-replay-reset").addEventListener("click", () => {
        replayPlaying = false;
        if (replayAnimId) cancelAnimationFrame(replayAnimId);
        replayIdx = 0;
        drawReplayFrame(0);
    });

    // ═══════════════════ LOAD ANALYSIS ═══════════════════

    async function loadAnalysis() {
        if (!currentJobId) return;

        try {
            const res = await fetch(`/analysis/${currentJobId}`);
            const data = await res.json();

            if (data.error) { console.error(data.error); return; }

            // Summary strip
            document.getElementById("sum-cohesion").textContent =
                `${data.summary.final_cohesion.toFixed(2)}m`;
            document.getElementById("sum-connectivity").textContent =
                data.summary.final_connectivity.toFixed(3);
            document.getElementById("sum-speed").textContent =
                `${data.summary.mean_speed.toFixed(2)}m/s`;
            document.getElementById("sum-min-dist").textContent =
                `${data.summary.min_safe_distance.toFixed(3)}m`;
            document.getElementById("sum-coverage").textContent =
                `${data.summary.final_coverage.toFixed(1)}%`;

            // Charts
            const plotConfig = { responsive: true, displayModeBar: false };

            Plotly.newPlot("chart-cohesion",
                data.charts.cohesion.data, data.charts.cohesion.layout, plotConfig);
            Plotly.newPlot("chart-connectivity",
                data.charts.connectivity.data, data.charts.connectivity.layout, plotConfig);
            Plotly.newPlot("chart-speed",
                data.charts.speed.data, data.charts.speed.layout, plotConfig);
            Plotly.newPlot("chart-collision",
                data.charts.collision.data, data.charts.collision.layout, plotConfig);
            Plotly.newPlot("chart-coverage",
                data.charts.coverage.data, data.charts.coverage.layout, plotConfig);

        } catch (e) {
            console.error("Failed to load analysis", e);
        }
    }

    // ═══════════════════ LOAD BENCHMARK ═══════════════════

    async function loadBenchmark() {
        if (!currentJobId) return;

        try {
            const res = await fetch(`/benchmark/${currentJobId}`);
            const data = await res.json();

            if (data.error) { console.error(data.error); return; }

            // Gauge
            Plotly.newPlot("gauge-chart", data.gauge_chart.data, data.gauge_chart.layout, {
                responsive: true, displayModeBar: false,
            });

            // Grade
            const gradeEl = document.getElementById("bench-grade");
            gradeEl.textContent = data.health_grade;
            gradeEl.className = `grade-badge grade-${data.health_grade}`;

            // Metric cards
            const container = document.getElementById("benchmark-cards-container");
            container.innerHTML = "";

            const barColors = {
                "Coverage": "#22c55e",
                "Cohesion": "#06b6d4",
                "Connectivity": "#8b5cf6",
                "Safety": "#ef4444",
            };

            data.metric_cards.forEach(m => {
                const color = barColors[m.label] || "#FF4D00";
                const card = document.createElement("div");
                card.className = "metric-score-card";
                card.innerHTML = `
                    <div class="metric-card-top">
                        <i class="${m.icon}"></i>
                        <span>${m.label}</span>
                    </div>
                    <div class="metric-card-score">
                        <span class="score-num" style="color:${color}">${m.score.toFixed(1)}</span>
                        <span class="score-unit">/ 100</span>
                    </div>
                    <div class="metric-bar">
                        <div class="metric-bar-fill" style="width:${m.score}%;background:${color}"></div>
                    </div>
                    <div class="metric-card-desc">${m.desc}</div>
                `;
                container.appendChild(card);
            });

            // Emergence
            const emergContainer = document.getElementById("emergence-container");
            emergContainer.innerHTML = "";

            if (data.emergence && data.emergence.length) {
                data.emergence.forEach(em => {
                    const item = document.createElement("div");
                    item.className = "emergence-item";

                    const confPct = (em.confidence * 100).toFixed(1);
                    const timeStr = em.time_range
                        ? `${em.time_range[0].toFixed(2)}s — ${em.time_range[1].toFixed(2)}s`
                        : "Not detected";

                    item.innerHTML = `
                        <span class="emergence-label">${em.behavior}</span>
                        <span class="emergence-confidence">${confPct}%</span>
                        <span class="emergence-range">${timeStr}</span>
                    `;
                    emergContainer.appendChild(item);
                });
            } else {
                emergContainer.innerHTML = `<div style="padding:0.5rem;color:#666;font-size:0.8rem;">No emergence data available.</div>`;
            }

        } catch (e) {
            console.error("Failed to load benchmark", e);
        }
    }

    // ═══════════════════ EXPORTS ═══════════════════

    document.getElementById("export-report").addEventListener("click", () => {
        if (currentJobId) window.open(`/export/${currentJobId}/report`, "_blank");
    });
    document.getElementById("export-metrics").addEventListener("click", () => {
        if (currentJobId) window.open(`/export/${currentJobId}/metrics`, "_blank");
    });
    document.getElementById("export-telemetry").addEventListener("click", () => {
        if (currentJobId) window.open(`/export/${currentJobId}/telemetry`, "_blank");
    });
    document.getElementById("export-manifest").addEventListener("click", () => {
        if (currentJobId) window.open(`/export/${currentJobId}/manifest`, "_blank");
    });

    // ═══════════════════ RESET ═══════════════════

    function resetToStart() {
        navigateTo("configure");

        // Purge all plots
        ["plotly-trajectory", "chart-cohesion", "chart-connectivity",
         "chart-speed", "chart-collision", "chart-coverage", "gauge-chart"]
            .forEach(id => {
                const el = document.getElementById(id);
                if (el) Plotly.purge(el);
            });

        // Reset state
        currentJobId = null;
        selectedAlgo = null;
        replayData = null;
        replayPlaying = false;
        if (replayAnimId) cancelAnimationFrame(replayAnimId);

        btnLaunch.disabled = true;
        ovStatus.textContent = "READY";
        ovProgress.textContent = "0%";
        terminalContainer.classList.add("hidden");
        terminalOutput.innerHTML = "";
        terminalBadge.textContent = "RUNNING";
        terminalBadge.style.background = "";
        terminalBadge.style.color = "";

        // Deselect algo cards
        document.querySelectorAll(".algo-card").forEach(c => c.classList.remove("selected"));
        document.querySelectorAll(".card-icon").forEach(icon => icon.classList.remove("orange"));
        extraOptionsGroup.classList.add("hidden");

        // Reset workflow bar
        document.querySelectorAll(".workflow-step").forEach(s => s.classList.remove("active", "completed"));
        document.querySelectorAll(".workflow-step")[0].classList.add("active");
        document.querySelectorAll(".workflow-connector").forEach(c => c.classList.remove("filled"));
    }
});
