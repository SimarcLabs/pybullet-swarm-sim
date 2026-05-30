document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const algoGrid = document.getElementById("algo-grid");
    
    const dronesSlider = document.getElementById("drones-slider");
    const dronesVal = document.getElementById("drones-val");
    const btnDroneMinus = document.getElementById("btn-drone-minus");
    const btnDronePlus = document.getElementById("btn-drone-plus");
    
    const durationSlider = document.getElementById("duration-slider");
    const durationVal = document.getElementById("duration-val");
    const btnTimeMinus = document.getElementById("btn-time-minus");
    const btnTimePlus = document.getElementById("btn-time-plus");
    
    const btnLaunch = document.getElementById("btn-launch");
    const btnReset = document.getElementById("btn-reset");
    
    const extraOptionsGroup = document.getElementById("extra-options-container");
    const formSelectGroup = document.getElementById("formation-select-group");
    const customUploadGroup = document.getElementById("custom-upload-group");
    const formationType = document.getElementById("formation-type");
    const customFile = document.getElementById("custom-file");
    
    const panelSelect = document.getElementById("panel-select");
    const panelResults = document.getElementById("panel-results");
    const terminalContainer = document.getElementById("terminal-container");
    const terminalOutput = document.getElementById("terminal-output");
    
    // Overview Panel Stats
    const ovDrones = document.getElementById("ov-drones");
    const ovDuration = document.getElementById("ov-duration");
    const ovStatus = document.getElementById("ov-status");
    const ovProgress = document.getElementById("ov-progress");

    let selectedAlgo = null;
    let eventSource = null;

    // --- Slider Logic ---
    function updateDroneVal() {
        dronesVal.textContent = dronesSlider.value;
        ovDrones.textContent = dronesSlider.value;
    }
    function updateDurationVal() {
        durationVal.textContent = durationSlider.value;
        ovDuration.innerHTML = `${durationSlider.value}<span style="font-size: 0.5em">s</span>`;
    }

    dronesSlider.addEventListener("input", updateDroneVal);
    durationSlider.addEventListener("input", updateDurationVal);

    btnDroneMinus.addEventListener("click", () => {
        dronesSlider.value = Math.max(parseInt(dronesSlider.min), parseInt(dronesSlider.value) - 1);
        updateDroneVal();
    });
    btnDronePlus.addEventListener("click", () => {
        dronesSlider.value = Math.min(parseInt(dronesSlider.max), parseInt(dronesSlider.value) + 1);
        updateDroneVal();
    });

    btnTimeMinus.addEventListener("click", () => {
        durationSlider.value = Math.max(parseInt(durationSlider.min), parseInt(durationSlider.value) - parseInt(durationSlider.step));
        updateDurationVal();
    });
    btnTimePlus.addEventListener("click", () => {
        durationSlider.value = Math.min(parseInt(durationSlider.max), parseInt(durationSlider.value) + parseInt(durationSlider.step));
        updateDurationVal();
    });

    // --- Fetch Algorithms ---
    fetch("/algorithms")
        .then(res => res.json())
        .then(algos => {
            algos.forEach(algo => {
                const card = document.createElement("div");
                card.className = "algo-card";
                if (algo.is_custom) {
                    card.classList.add("custom-card");
                }
                
                // Construct inner HTML matching blueprint theme
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
        
        // Show/hide specific config options
        if (algo.has_shapes || algo.is_custom) {
            extraOptionsGroup.classList.remove("hidden");
            formSelectGroup.classList.toggle("hidden", !algo.has_shapes);
            customUploadGroup.classList.toggle("hidden", !algo.is_custom);
        } else {
            extraOptionsGroup.classList.add("hidden");
        }
    }

    function switchPanel(targetPanel) {
        return new Promise((resolve) => {
            [panelSelect, panelResults].forEach(p => p.classList.remove("active", "hidden"));
            
            [panelSelect, panelResults].forEach(p => {
                if(p !== targetPanel) p.classList.add("hidden");
            });
            
            setTimeout(() => {
                targetPanel.classList.add("active");
                resolve();
            }, 50);
        });
    }

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

        // Switch UI to running state within Panel 1
        btnLaunch.disabled = true;
        ovStatus.textContent = "RUNNING";
        ovStatus.style.color = "#FF4D00";
        terminalContainer.classList.remove("hidden");
        terminalOutput.innerHTML = "";
        ovProgress.textContent = "0%";

        try {
            const res = await fetch("/run", {
                method: "POST",
                body: formData
            });
            const data = await res.json();
            streamLogs(data.job_id);
        } catch (e) {
            terminalOutput.innerHTML += `<div>Error launching simulation: ${e}</div>`;
            btnLaunch.disabled = false;
            ovStatus.textContent = "ERROR";
        }
    });

    function streamLogs(jobId) {
        eventSource = new EventSource(`/stream/${jobId}`);
        
        eventSource.onmessage = (e) => {
            const line = document.createElement("div");
            line.textContent = `> ${e.data}`;
            terminalOutput.appendChild(line);
            terminalOutput.scrollTop = terminalOutput.scrollHeight;
        };
        
        eventSource.addEventListener("progress", (e) => {
            ovProgress.textContent = `${e.data}%`;
        });
        
        eventSource.addEventListener("done", (e) => {
            eventSource.close();
            ovStatus.textContent = "COMPLETE";
            setTimeout(() => loadResults(jobId), 1000); // slight delay to allow file writing
        });
        
        eventSource.onerror = (e) => {
            console.error("SSE Error", e);
            eventSource.close();
            btnLaunch.disabled = false;
            ovStatus.textContent = "ERROR";
        };
    }

    async function loadResults(jobId) {
        await switchPanel(panelResults);
        
        try {
            const res = await fetch(`/results/${jobId}`);
            const data = await res.json();
            
            if (data.error) {
                alert(data.error);
                return;
            }
            
            // Render Stats
            document.getElementById("stat-algo").textContent = data.metrics.algo.toUpperCase();
            document.getElementById("stat-drones").textContent = data.metrics.num_drones;
            document.getElementById("stat-duration").textContent = `${data.metrics.duration}s`;
            document.getElementById("stat-health").textContent = `${(data.metrics.health_score * 100).toFixed(1)}%`;
            
            // Render Plotly
            Plotly.newPlot('plotly-div', data.plotly_data.data, data.plotly_data.layout).then(() => {
                window.dispatchEvent(new Event('resize'));
            });
            
        } catch (e) {
            console.error("Failed to load results", e);
            alert("Failed to load results.");
        }
    }

    btnReset.addEventListener("click", () => {
        switchPanel(panelSelect);
        Plotly.purge('plotly-div');
        
        // Reset state
        btnLaunch.disabled = false;
        ovStatus.textContent = "READY";
        ovStatus.style.color = "";
        ovProgress.textContent = "NOT STARTED";
        terminalContainer.classList.add("hidden");
    });
});
