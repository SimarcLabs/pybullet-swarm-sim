/* PyBullet Swarm Sim — Dashboard Controller v8
   Configure → Run → Observe → Analyze → Benchmark → Export
   + Hero Canvas, Presets, History, Compare */

document.addEventListener("DOMContentLoaded", () => {

// ─── State ───
let selectedAlgo = null, eventSource = null, currentJobId = null;
let replayData = null, replayAnimId = null, replayIdx = 0, replayPlaying = false;
const WORKFLOW_STEPS = ["configure","run","observe","analyze","benchmark","export"];

const $ = id => document.getElementById(id);
const panels = {
    configure: $("panel-configure"), observe: $("panel-observe"),
    analyze: $("panel-analyze"), benchmark: $("panel-benchmark"), export: $("panel-export"),
};
const algoGrid=$("algo-grid"), dronesSlider=$("drones-slider"), dronesVal=$("drones-val");
const durationSlider=$("duration-slider"), durationVal=$("duration-val");
const btnLaunch=$("btn-launch"), extraOptionsGroup=$("extra-options-container");
const formSelectGroup=$("formation-select-group"), customUploadGroup=$("custom-upload-group");
const formationType=$("formation-type"), customFile=$("custom-file");
const terminalContainer=$("terminal-container"), terminalOutput=$("terminal-output"), terminalBadge=$("terminal-badge");
const ovDrones=$("ov-drones"), ovDuration=$("ov-duration"), ovStatus=$("ov-status"), ovProgress=$("ov-progress");

// ═══════════════════ WORKFLOW NAV ═══════════════════
function navigateTo(stepName){
    Object.values(panels).forEach(p=>p.classList.remove("active"));
    const t=panels[stepName]; if(t) setTimeout(()=>t.classList.add("active"),30);
    const steps=document.querySelectorAll(".workflow-step");
    const conns=document.querySelectorAll(".workflow-connector");
    const idx=WORKFLOW_STEPS.indexOf(stepName);
    steps.forEach((s,i)=>{s.classList.remove("active","completed");if(i<idx)s.classList.add("completed");if(i===idx)s.classList.add("active");});
    conns.forEach((c,i)=>c.classList.toggle("filled",i<idx));
}
document.querySelectorAll(".workflow-step").forEach(s=>s.addEventListener("click",()=>{
    if(s.classList.contains("completed")||s.classList.contains("active")) navigateTo(s.dataset.step);
}));
$("btn-to-analyze").addEventListener("click",()=>{navigateTo("analyze");loadAnalysis();});
$("btn-back-observe").addEventListener("click",()=>navigateTo("observe"));
$("btn-to-benchmark").addEventListener("click",()=>{navigateTo("benchmark");loadBenchmark();});
$("btn-back-analyze").addEventListener("click",()=>navigateTo("analyze"));
$("btn-to-export").addEventListener("click",()=>navigateTo("export"));
$("btn-back-benchmark").addEventListener("click",()=>navigateTo("benchmark"));
$("btn-new-run").addEventListener("click",resetToStart);

// ═══════════════════ SLIDERS ═══════════════════
function updateDroneVal(){dronesVal.textContent=dronesSlider.value;ovDrones.textContent=dronesSlider.value;}
function updateDurationVal(){durationVal.textContent=durationSlider.value;ovDuration.innerHTML=`${durationSlider.value}<span class="unit">s</span>`;}
dronesSlider.addEventListener("input",updateDroneVal);
durationSlider.addEventListener("input",updateDurationVal);
$("btn-drone-minus").addEventListener("click",()=>{dronesSlider.value=Math.max(+dronesSlider.min,+dronesSlider.value-1);updateDroneVal();});
$("btn-drone-plus").addEventListener("click",()=>{dronesSlider.value=Math.min(+dronesSlider.max,+dronesSlider.value+1);updateDroneVal();});
$("btn-time-minus").addEventListener("click",()=>{durationSlider.value=Math.max(+durationSlider.min,+durationSlider.value-+durationSlider.step);updateDurationVal();});
$("btn-time-plus").addEventListener("click",()=>{durationSlider.value=Math.min(+durationSlider.max,+durationSlider.value+ +durationSlider.step);updateDurationVal();});

// ═══════════════════ PRESETS ═══════════════════
fetch("/presets").then(r=>r.json()).then(presets=>{
    const grid=$("preset-grid");
    presets.forEach(p=>{
        const card=document.createElement("div");
        card.className="preset-card";
        card.innerHTML=`
            <div class="preset-icon" style="background:${p.color}15;color:${p.color}"><i class="${p.icon}"></i></div>
            <div class="preset-info">
                <h4>${p.name}</h4>
                <p>${p.desc}</p>
                <div class="preset-meta">
                    <span class="preset-tag">${p.drones} drones</span>
                    <span class="preset-tag">${p.duration}s</span>
                    <span class="preset-tag">${p.algo}</span>
                </div>
            </div>`;
        card.addEventListener("click",()=>launchPreset(p));
        grid.appendChild(card);
    });
});

function launchPreset(p){
    dronesSlider.value=p.drones; updateDroneVal();
    durationSlider.value=p.duration; updateDurationVal();
    formationType.value=p.formation_type;
    selectedAlgo={id:p.algo,has_shapes:p.algo==="formation"};
    if(p.algo==="formation"){extraOptionsGroup.classList.remove("hidden");formSelectGroup.classList.remove("hidden");customUploadGroup.classList.add("hidden");}
    else{extraOptionsGroup.classList.add("hidden");}
    btnLaunch.disabled=false;
    btnLaunch.click();
}

// ═══════════════════ ALGORITHMS ═══════════════════
fetch("/algorithms").then(r=>r.json()).then(algos=>{
    const upcomingGrid=$("upcoming-grid");
    let hasUpcoming=false;
    algos.forEach(algo=>{
        const card=document.createElement("div");
        if(algo.is_upcoming) {
            hasUpcoming=true;
            card.className="algo-card upcoming-card";
            card.innerHTML=`<div class="card-icon"><i class="${algo.icon}"></i></div><h3>${algo.name}</h3><p>${algo.desc}</p><span class="upcoming-badge">IN DEV</span>`;
            card.addEventListener("click",()=>alert(algo.name + " is currently in development! Stay tuned."));
            upcomingGrid.appendChild(card);
        } else {
            card.className="algo-card";
            if(algo.is_custom) card.classList.add("custom-card");
            card.innerHTML=`<div class="card-icon"><i class="${algo.icon}"></i></div><h3>${algo.name}</h3><p>${algo.desc}</p>`;
            card.addEventListener("click",()=>selectAlgo(card,algo));
            algoGrid.appendChild(card);
        }
    });
    // Hide 'Explore Future' section if nothing upcoming
    if(!hasUpcoming){
        const upcomingSection=upcomingGrid.closest(".blueprint-container");
        if(upcomingSection){upcomingSection.style.display="none";upcomingSection.previousElementSibling.style.display="none";}
    }
});
function selectAlgo(el,algo){
    document.querySelectorAll(".algo-card").forEach(c=>c.classList.remove("selected"));
    document.querySelectorAll(".card-icon").forEach(i=>i.classList.remove("orange"));
    el.classList.add("selected"); el.querySelector(".card-icon").classList.add("orange");
    selectedAlgo=algo; btnLaunch.disabled=false;
    if(algo.has_shapes||algo.is_custom){extraOptionsGroup.classList.remove("hidden");formSelectGroup.classList.toggle("hidden",!algo.has_shapes);customUploadGroup.classList.toggle("hidden",!algo.is_custom);}
    else extraOptionsGroup.classList.add("hidden");

    // MARL panel visibility
    const marlPanel=$("marl-panel");
    if(algo.has_marl){
        marlPanel.classList.remove("hidden");
        loadMARLModels();
    } else {
        marlPanel.classList.add("hidden");
    }
}

// ═══════════════════ MARL TRAINING ═══════════════════
async function loadMARLModels(){
    const list=$("marl-model-list");
    try{
        const d=await(await fetch("/marl/models")).json();
        if(!d.models.length){
            list.innerHTML=`<div class="marl-hint" style="text-align:center;padding:1rem 0;">No trained models yet. Train one to get started!</div>`;
            return;
        }
        list.innerHTML="";
        d.models.forEach(m=>{
            const el=document.createElement("div");
            el.className="marl-model-item";
            el.innerHTML=`<div><span class="marl-model-name">${m.filename}</span><br><span class="marl-model-meta">${m.drones} drones · ${m.size_mb} MB</span></div><span class="marl-model-badge">READY</span>`;
            list.appendChild(el);
        });
    }catch(e){list.innerHTML=`<div class="marl-hint" style="color:#ef4444;">Failed to load models.</div>`;}
}

$("btn-marl-train").addEventListener("click",async()=>{
    const ts=$("marl-timesteps").value;
    const drones=dronesSlider.value;
    const btn=$("btn-marl-train");
    btn.disabled=true; btn.innerHTML=`<i class="fa-solid fa-spinner fa-spin"></i> Training...`;
    $("marl-train-status").classList.remove("hidden");
    $("marl-progress-fill").style.width="0%";
    $("marl-progress-text").textContent="0%";

    try{
        const fd=new FormData();
        fd.append("drones",drones);
        fd.append("timesteps",ts);
        const r=await(await fetch("/marl/train",{method:"POST",body:fd})).json();
        if(r.error){alert(r.error);btn.disabled=false;btn.innerHTML=`<i class="fa-solid fa-play"></i> Start Training`;return;}

        // Stream training progress
        const es=new EventSource(`/stream/${r.job_id}`);
        es.addEventListener("progress",e=>{
            const pct=e.data.replace("%","");
            $("marl-progress-fill").style.width=pct+"%";
            $("marl-progress-text").textContent=pct+"%";
        });
        es.addEventListener("done",()=>{
            es.close();
            $("marl-progress-fill").style.width="100%";
            $("marl-progress-text").textContent="100%";
            btn.disabled=false;
            btn.innerHTML=`<i class="fa-solid fa-play"></i> Start Training`;
            loadMARLModels();
        });
        es.onerror=()=>{
            es.close();
            btn.disabled=false;
            btn.innerHTML=`<i class="fa-solid fa-play"></i> Start Training`;
            $("marl-progress-fill").style.width="100%";
            $("marl-progress-text").textContent="Done";
            loadMARLModels();
        };
    }catch(e){
        console.error(e);
        btn.disabled=false;
        btn.innerHTML=`<i class="fa-solid fa-play"></i> Start Training`;
        alert("Failed to start training.");
    }
});

// ═══════════════════ LAUNCH ═══════════════════
btnLaunch.addEventListener("click",async()=>{
    if(!selectedAlgo) return;
    const fd=new FormData();
    fd.append("algo",selectedAlgo.id); fd.append("drones",dronesSlider.value); fd.append("duration",durationSlider.value);
    if(selectedAlgo.has_shapes) fd.append("formation_type",formationType.value);
    if(selectedAlgo.is_custom){if(!customFile.files.length){alert("Please select a .py file.");return;} fd.append("custom_file",customFile.files[0]);}
    btnLaunch.disabled=true; ovStatus.textContent="RUNNING";
    terminalContainer.classList.remove("hidden"); terminalOutput.innerHTML=""; terminalBadge.textContent="RUNNING"; ovProgress.textContent="0%";
    const steps=document.querySelectorAll(".workflow-step");
    steps[0].classList.add("completed"); steps[0].classList.remove("active"); steps[1].classList.add("active");
    document.querySelectorAll(".workflow-connector")[0].classList.add("filled");
    try{const r=await fetch("/run",{method:"POST",body:fd});const d=await r.json();currentJobId=d.job_id;streamLogs(d.job_id);}
    catch(e){terminalOutput.innerHTML+=`<div style="color:#ef4444">> Error: ${e}</div>`;btnLaunch.disabled=false;ovStatus.textContent="ERROR";}
});

function streamLogs(jobId){
    eventSource=new EventSource(`/stream/${jobId}`);
    eventSource.onmessage=e=>{const l=document.createElement("div");l.textContent=`> ${e.data}`;terminalOutput.appendChild(l);terminalOutput.scrollTop=terminalOutput.scrollHeight;};
    eventSource.addEventListener("progress",e=>{ovProgress.textContent=`${e.data.replace("%","")}%`;});
    eventSource.addEventListener("done",()=>{eventSource.close();ovStatus.textContent="COMPLETE";terminalBadge.textContent="DONE";terminalBadge.style.background="rgba(34,197,94,0.15)";terminalBadge.style.color="#22c55e";setTimeout(()=>loadResults(jobId),1200);});
    eventSource.onerror=()=>{eventSource.close();btnLaunch.disabled=false;ovStatus.textContent="ERROR";};
}

// ═══════════════════ OBSERVE ═══════════════════
async function loadResults(jobId){
    navigateTo("observe");
    try{
        const d=(await(await fetch(`/results/${jobId}`)).json());
        if(d.error){alert(d.error);return;}
        $("obs-algo").textContent=d.metrics.algo.toUpperCase();
        $("obs-drones").textContent=d.metrics.num_drones;
        $("obs-duration").textContent=`${d.metrics.duration}s`;
        $("obs-health").textContent=`${(d.metrics.health_score*100).toFixed(1)}%`;
        Plotly.newPlot("plotly-trajectory",d.plotly_data.data,d.plotly_data.layout,{responsive:true,displayModeBar:true,modeBarButtonsToRemove:['toImage'],displaylogo:false});
        loadReplay(jobId);
    }catch(e){console.error(e);alert("Failed to load results.");}
}

// ═══════════════════ 2D REPLAY ═══════════════════
async function loadReplay(jobId){try{replayData=await(await fetch(`/replay/${jobId}`)).json();replayIdx=0;drawReplayFrame(0);}catch(e){console.error(e);}}
const COLORS=['#ef4444','#f97316','#f59e0b','#84cc16','#22c55e','#10b981','#06b6d4','#0ea5e9','#3b82f6','#6366f1','#8b5cf6','#a855f7','#d946ef','#ec4899','#f43f5e'];

function drawReplayFrame(idx){
    if(!replayData||!replayData.frames.length) return;
    const canvas=$("replay-canvas"),ctx=canvas.getContext("2d");
    const rect=canvas.getBoundingClientRect();
    canvas.width=rect.width*devicePixelRatio; canvas.height=rect.height*devicePixelRatio;
    ctx.scale(devicePixelRatio,devicePixelRatio);
    const W=rect.width,H=rect.height;
    const frame=replayData.frames[Math.min(idx,replayData.frames.length-1)];
    const lo=replayData.bounds.lo,hi=replayData.bounds.hi;
    ctx.fillStyle="#0a0a0a";ctx.fillRect(0,0,W,H);
    ctx.strokeStyle="#1a1a1a";ctx.lineWidth=1;
    for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
    for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
    const mx=v=>((v-lo[0])/(hi[0]-lo[0]))*(W-40)+20;
    const my=v=>H-(((v-lo[1])/(hi[1]-lo[1]))*(H-40)+20);
    const N=frame.pos.length;
    for(let i=0;i<N;i++)for(let j=i+1;j<N;j++){
        const dx=frame.pos[i][0]-frame.pos[j][0],dy=frame.pos[i][1]-frame.pos[j][1],d=Math.sqrt(dx*dx+dy*dy);
        if(d<2){ctx.strokeStyle=`rgba(255,77,0,${Math.max(0,1-d/2)*0.3})`;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(mx(frame.pos[i][0]),my(frame.pos[i][1]));ctx.lineTo(mx(frame.pos[j][0]),my(frame.pos[j][1]));ctx.stroke();}
    }
    for(let t=Math.max(0,idx-8);t<idx;t++){const f=replayData.frames[t],a=(1-(idx-t)/8)*0.25;
        for(let i=0;i<f.pos.length;i++){ctx.fillStyle=COLORS[i%COLORS.length]+"40";ctx.beginPath();ctx.arc(mx(f.pos[i][0]),my(f.pos[i][1]),2,0,Math.PI*2);ctx.fill();}}
    for(let i=0;i<N;i++){
        const px=mx(frame.pos[i][0]),py=my(frame.pos[i][1]),c=COLORS[i%COLORS.length];
        const g=ctx.createRadialGradient(px,py,0,px,py,12);g.addColorStop(0,c+"55");g.addColorStop(1,c+"00");
        ctx.fillStyle=g;ctx.beginPath();ctx.arc(px,py,12,0,Math.PI*2);ctx.fill();
        ctx.fillStyle=c;ctx.beginPath();ctx.arc(px,py,4,0,Math.PI*2);ctx.fill();
    }
    $("replay-time").textContent=`t = ${frame.t.toFixed(3)}s`;
}
function playReplay(){if(!replayData||replayPlaying)return;replayPlaying=true;(function tick(){if(!replayPlaying)return;if(replayIdx>=replayData.frames.length-1){replayPlaying=false;return;}replayIdx++;drawReplayFrame(replayIdx);replayAnimId=requestAnimationFrame(tick);})();}
$("btn-replay-play").addEventListener("click",playReplay);
$("btn-replay-pause").addEventListener("click",()=>{replayPlaying=false;if(replayAnimId)cancelAnimationFrame(replayAnimId);});
$("btn-replay-reset").addEventListener("click",()=>{replayPlaying=false;if(replayAnimId)cancelAnimationFrame(replayAnimId);replayIdx=0;drawReplayFrame(0);});

// ═══════════════════ ANALYSIS ═══════════════════
async function loadAnalysis(){
    if(!currentJobId)return;
    try{
        const d=await(await fetch(`/analysis/${currentJobId}`)).json();
        if(d.error)return;
        $("sum-cohesion").textContent=`${d.summary.final_cohesion.toFixed(2)}m`;
        $("sum-connectivity").textContent=d.summary.final_connectivity.toFixed(3);
        $("sum-speed").textContent=`${d.summary.mean_speed.toFixed(2)}m/s`;
        $("sum-min-dist").textContent=`${d.summary.min_safe_distance.toFixed(3)}m`;
        $("sum-coverage").textContent=`${d.summary.final_coverage.toFixed(1)}%`;
        const pc={responsive:true,displayModeBar:false};
        Plotly.newPlot("chart-cohesion",d.charts.cohesion.data,d.charts.cohesion.layout,pc);
        Plotly.newPlot("chart-connectivity",d.charts.connectivity.data,d.charts.connectivity.layout,pc);
        Plotly.newPlot("chart-speed",d.charts.speed.data,d.charts.speed.layout,pc);
        Plotly.newPlot("chart-collision",d.charts.collision.data,d.charts.collision.layout,pc);
        Plotly.newPlot("chart-coverage",d.charts.coverage.data,d.charts.coverage.layout,pc);
    }catch(e){console.error(e);}
}

// ═══════════════════ BENCHMARK ═══════════════════
async function loadBenchmark(){
    if(!currentJobId)return;
    try{
        const d=await(await fetch(`/benchmark/${currentJobId}`)).json();
        if(d.error)return;
        Plotly.newPlot("gauge-chart",d.gauge_chart.data,d.gauge_chart.layout,{responsive:true,displayModeBar:false});
        const ge=$("bench-grade");ge.textContent=d.health_grade;ge.className=`grade-badge grade-${d.health_grade}`;
        const ct=$("benchmark-cards-container");ct.innerHTML="";
        const bc={Coverage:"#22c55e",Cohesion:"#06b6d4",Connectivity:"#8b5cf6",Safety:"#ef4444"};
        d.metric_cards.forEach(m=>{const c=bc[m.label]||"#FF4D00";const el=document.createElement("div");el.className="metric-score-card";
            el.innerHTML=`<div class="metric-card-top"><i class="${m.icon}"></i><span>${m.label}</span></div><div class="metric-card-score"><span class="score-num" style="color:${c}">${m.score.toFixed(1)}</span><span class="score-unit">/ 100</span></div><div class="metric-bar"><div class="metric-bar-fill" style="width:${m.score}%;background:${c}"></div></div><div class="metric-card-desc">${m.desc}</div>`;
            ct.appendChild(el);});
        const ec=$("emergence-container");ec.innerHTML="";
        if(d.emergence&&d.emergence.length){d.emergence.forEach(em=>{const el=document.createElement("div");el.className="emergence-item";
            el.innerHTML=`<span class="emergence-label">${em.behavior}</span><span class="emergence-confidence">${(em.confidence*100).toFixed(1)}%</span><span class="emergence-range">${em.time_range?`${em.time_range[0].toFixed(2)}s — ${em.time_range[1].toFixed(2)}s`:"Not detected"}</span>`;
            ec.appendChild(el);});}
        else ec.innerHTML=`<div style="padding:0.5rem;color:#666;font-size:0.8rem;">No emergence data available.</div>`;
    }catch(e){console.error(e);}
}

// ═══════════════════ EXPORTS ═══════════════════
$("export-report").addEventListener("click",()=>{if(currentJobId)window.open(`/export/${currentJobId}/report`,"_blank");});
$("export-metrics").addEventListener("click",()=>{if(currentJobId)window.open(`/export/${currentJobId}/metrics`,"_blank");});
$("export-telemetry").addEventListener("click",()=>{if(currentJobId)window.open(`/export/${currentJobId}/telemetry`,"_blank");});
$("export-manifest").addEventListener("click",()=>{if(currentJobId)window.open(`/export/${currentJobId}/manifest`,"_blank");});

// ═══════════════════ HISTORY SIDEBAR ═══════════════════
const historySidebar=$("history-sidebar");
$("btn-toggle-history").addEventListener("click",()=>{historySidebar.classList.toggle("open");if(historySidebar.classList.contains("open"))refreshHistory();});
$("btn-close-history").addEventListener("click",()=>historySidebar.classList.remove("open"));

function timeAgo(dateString) {
    const d = new Date(dateString);
    if(isNaN(d.getTime())) return dateString;
    const s = Math.floor((new Date() - d) / 1000);
    if(s < 60) return "Just now";
    if(s < 3600) return Math.floor(s/60) + "m ago";
    if(s < 86400) return Math.floor(s/3600) + "h ago";
    return Math.floor(s/86400) + "d ago";
}

async function refreshHistory(){
    const list=$("history-list");
    try{
        const h=await(await fetch("/history")).json();
        if(!h.length){list.innerHTML=`<div style="padding:1rem;color:#666;font-size:0.8rem;text-align:center;">No runs yet. Launch a simulation to see history.</div>`;return;}
        list.innerHTML="";
        h.forEach(entry=>{
            const el=document.createElement("div");el.className="history-item";
            el.innerHTML=`<div class="history-left"><span class="history-algo">${entry.algo.toUpperCase()}</span><span class="history-meta">${entry.drones}d · ${entry.duration}s · ${timeAgo(entry.timestamp)}</span></div><span class="history-badge ${entry.status}">${entry.status}</span>`;
            if(entry.status==="completed") el.addEventListener("click",()=>{currentJobId=entry.job_id;historySidebar.classList.remove("open");loadResults(entry.job_id);});
            list.appendChild(el);
        });
    }catch(e){list.innerHTML=`<div style="padding:1rem;color:#666;">Failed to load history.</div>`;}
}

// ═══════════════════ COMPARE MODAL ═══════════════════
const compareOverlay=$("compare-overlay");
$("btn-toggle-compare").addEventListener("click",async()=>{compareOverlay.classList.remove("hidden");$("compare-results").classList.add("hidden");
    const cb=$("compare-checkboxes");cb.innerHTML="";
    try{const h=await(await fetch("/history")).json();const completed=h.filter(e=>e.status==="completed");
        if(!completed.length){cb.innerHTML=`<div style="color:#666;font-size:0.8rem;">No completed runs to compare.</div>`;return;}
        completed.forEach(e=>{const lbl=document.createElement("label");
            lbl.innerHTML=`<input type="checkbox" value="${e.job_id}"> <span>${e.algo.toUpperCase()} · ${e.drones}d · ${e.duration}s</span> <span style="color:#666;font-size:0.6rem;margin-left:auto;">${timeAgo(e.timestamp)}</span>`;
            cb.appendChild(lbl);});
    }catch(e){cb.innerHTML=`<div style="color:#666;">Failed to load runs.</div>`;}
});
$("btn-close-compare").addEventListener("click",()=>compareOverlay.classList.add("hidden"));
compareOverlay.addEventListener("click",e=>{if(e.target===compareOverlay)compareOverlay.classList.add("hidden");});

$("btn-run-compare").addEventListener("click",async()=>{
    const checked=[...document.querySelectorAll("#compare-checkboxes input:checked")].map(i=>i.value);
    if(checked.length<2){alert("Select at least 2 runs to compare.");return;}
    try{
        const d=await(await fetch(`/compare?ids=${checked.join(",")}`)).json();
        if(d.error){alert(d.error);return;}
        $("compare-results").classList.remove("hidden");
        Plotly.newPlot("radar-chart",d.radar_chart.data,d.radar_chart.layout,{responsive:true,displayModeBar:false});
        const tbl=$("compare-table");
        let html=`<table><tr><th>Run</th><th>Health</th><th>Coverage</th><th>Cohesion</th><th>Connectivity</th><th>Safety</th></tr>`;
        d.runs.forEach(r=>{html+=`<tr><td>${r.label}</td><td style="color:var(--accent-primary)">${r.health}%</td>${r.values.map(v=>`<td>${v}%</td>`).join("")}</tr>`;});
        html+=`</table>`;tbl.innerHTML=html;
    }catch(e){console.error(e);alert("Comparison failed.");}
});

// ═══════════════════ RESET ═══════════════════
function resetToStart(){
    navigateTo("configure");
    ["plotly-trajectory","chart-cohesion","chart-connectivity","chart-speed","chart-collision","chart-coverage","gauge-chart"].forEach(id=>{const el=$(id);if(el)Plotly.purge(el);});
    currentJobId=null;selectedAlgo=null;replayData=null;replayPlaying=false;
    if(replayAnimId)cancelAnimationFrame(replayAnimId);
    btnLaunch.disabled=true;ovStatus.textContent="READY";ovProgress.textContent="0%";
    terminalContainer.classList.add("hidden");terminalOutput.innerHTML="";
    terminalBadge.textContent="RUNNING";terminalBadge.style.background="";terminalBadge.style.color="";
    document.querySelectorAll(".algo-card").forEach(c=>c.classList.remove("selected"));
    document.querySelectorAll(".card-icon").forEach(i=>i.classList.remove("orange"));
    extraOptionsGroup.classList.add("hidden");
    document.querySelectorAll(".workflow-step").forEach(s=>s.classList.remove("active","completed"));
    document.querySelectorAll(".workflow-step")[0].classList.add("active");
    document.querySelectorAll(".workflow-connector").forEach(c=>c.classList.remove("filled"));
}

// ═══════════════════════════════════════════════════════════════
// BATTLE MODE
// ═══════════════════════════════════════════════════════════════

let battleMode = false;
let battleAlgoAlpha = null, battleAlgoBravo = null;
let battleJobId = null, battleEventSource = null;
let battleLastPositions = [];

const ALGO_NAMES = {
    flocking:"Reynolds Boids", pso:"PSO Search", aco:"ACO Path Planning",
    consensus:"Consensus", apf:"Potential Fields", abc:"Artificial Bee Colony",
    voronoi:"Voronoi Coverage", marl:"MARL (PPO)"
};

// ─── Mode Toggle ───
$("mode-sim").addEventListener("click",()=>switchMode("sim"));
$("mode-battle").addEventListener("click",()=>switchMode("battle"));

function switchMode(mode){
    battleMode = mode === "battle";
    $("mode-sim").classList.toggle("active", !battleMode);
    $("mode-battle").classList.toggle("active", battleMode);

    // Hide all panels
    Object.values(panels).forEach(p=>p.classList.remove("active"));
    document.querySelectorAll(".battle-panel").forEach(p=>p.classList.remove("active"));

    // Show/hide workflow bar
    document.querySelector(".workflow-bar").style.display = battleMode ? "none" : "flex";

    if(battleMode){
        $("panel-battle-configure").classList.add("active");
    } else {
        navigateTo("configure");
    }
}

// ─── Battle Sliders ───
const baDronesSlider = $("ba-drones-slider"), baDronesVal = $("ba-drones-val");
const bbDronesSlider = $("bb-drones-slider"), bbDronesVal = $("bb-drones-val");
const battleDurSlider = $("battle-duration-slider"), battleDurVal = $("battle-duration-val");

baDronesSlider.addEventListener("input",()=>baDronesVal.textContent=baDronesSlider.value);
bbDronesSlider.addEventListener("input",()=>bbDronesVal.textContent=bbDronesSlider.value);
battleDurSlider.addEventListener("input",()=>battleDurVal.textContent=battleDurSlider.value);

$("btn-ba-drone-minus").addEventListener("click",()=>{baDronesSlider.value=Math.max(+baDronesSlider.min,+baDronesSlider.value-1);baDronesVal.textContent=baDronesSlider.value;});
$("btn-ba-drone-plus").addEventListener("click",()=>{baDronesSlider.value=Math.min(+baDronesSlider.max,+baDronesSlider.value+1);baDronesVal.textContent=baDronesSlider.value;});
$("btn-bb-drone-minus").addEventListener("click",()=>{bbDronesSlider.value=Math.max(+bbDronesSlider.min,+bbDronesSlider.value-1);bbDronesVal.textContent=bbDronesSlider.value;});
$("btn-bb-drone-plus").addEventListener("click",()=>{bbDronesSlider.value=Math.min(+bbDronesSlider.max,+bbDronesSlider.value+1);bbDronesVal.textContent=bbDronesSlider.value;});
$("btn-battle-time-minus").addEventListener("click",()=>{battleDurSlider.value=Math.max(+battleDurSlider.min,+battleDurSlider.value-+battleDurSlider.step);battleDurVal.textContent=battleDurSlider.value;});
$("btn-battle-time-plus").addEventListener("click",()=>{battleDurSlider.value=Math.min(+battleDurSlider.max,+battleDurSlider.value+ +battleDurSlider.step);battleDurVal.textContent=battleDurSlider.value;});

function checkBattleLaunchReady(){
    $("btn-battle-launch").disabled = !(battleAlgoAlpha && battleAlgoBravo);
}

// ─── Battle Algorithm Selection ───
fetch("/battle/algorithms").then(r=>r.json()).then(algos=>{
    ["alpha","bravo"].forEach(team=>{
        const grid = $(`battle-algo-grid-${team}`);
        algos.forEach(algo=>{
            const card = document.createElement("div");
            card.className = "battle-algo-card";
            card.dataset.algoId = algo.id;
            card.innerHTML = `<i class="${algo.icon}"></i><div class="battle-algo-name">${algo.name}</div>`;
            card.addEventListener("click",()=>{
                grid.querySelectorAll(".battle-algo-card").forEach(c=>c.classList.remove("selected"));
                card.classList.add("selected");
                if(team==="alpha") battleAlgoAlpha = algo.id;
                else battleAlgoBravo = algo.id;
                checkBattleLaunchReady();
            });
            grid.appendChild(card);
        });
    });
});

// ─── Battle Presets ───
fetch("/battle/presets").then(r=>r.json()).then(presets=>{
    const grid = $("battle-preset-grid");
    presets.forEach(p=>{
        const card = document.createElement("div");
        card.className = "preset-card";
        card.innerHTML = `
            <div class="preset-icon" style="background:${p.color}15;color:${p.color}"><i class="${p.icon}"></i></div>
            <div class="preset-info">
                <h4>${p.name}</h4>
                <p>${p.desc}</p>
                <div class="preset-meta">
                    <span class="preset-tag">${p.drones_alpha}v${p.drones_bravo}</span>
                    <span class="preset-tag">${p.duration}s</span>
                </div>
            </div>`;
        card.addEventListener("click",()=>launchBattlePreset(p));
        grid.appendChild(card);
    });
});

function launchBattlePreset(p){
    switchMode("battle");
    baDronesSlider.value = p.drones_alpha; baDronesVal.textContent = p.drones_alpha;
    bbDronesSlider.value = p.drones_bravo; bbDronesVal.textContent = p.drones_bravo;
    battleDurSlider.value = p.duration; battleDurVal.textContent = p.duration;
    battleAlgoAlpha = p.algo_alpha;
    battleAlgoBravo = p.algo_bravo;

    // Select the algo cards visually
    document.querySelectorAll("#battle-algo-grid-alpha .battle-algo-card").forEach(c=>{
        c.classList.toggle("selected", c.dataset.algoId === p.algo_alpha);
    });
    document.querySelectorAll("#battle-algo-grid-bravo .battle-algo-card").forEach(c=>{
        c.classList.toggle("selected", c.dataset.algoId === p.algo_bravo);
    });

    checkBattleLaunchReady();
    setTimeout(()=>$("btn-battle-launch").click(), 200);
}

// ─── Battle Launch ───
$("btn-battle-launch").addEventListener("click", async()=>{
    if(!battleAlgoAlpha || !battleAlgoBravo) return;

    const fd = new FormData();
    fd.append("algo_alpha", battleAlgoAlpha);
    fd.append("algo_bravo", battleAlgoBravo);
    fd.append("drones_alpha", baDronesSlider.value);
    fd.append("drones_bravo", bbDronesSlider.value);
    fd.append("duration", battleDurSlider.value);

    $("btn-battle-launch").disabled = true;
    $("battle-terminal-container").classList.remove("hidden");
    $("battle-terminal-output").innerHTML = "";
    $("battle-terminal-badge").textContent = "BATTLING";

    try {
        const r = await fetch("/battle/run", {method:"POST", body:fd});
        const d = await r.json();
        battleJobId = d.job_id;

        // Initialize live view
        $("live-algo-alpha").textContent = (ALGO_NAMES[battleAlgoAlpha]||battleAlgoAlpha).toUpperCase();
        $("live-algo-bravo").textContent = (ALGO_NAMES[battleAlgoBravo]||battleAlgoBravo).toUpperCase();
        $("live-alpha-total").textContent = baDronesSlider.value;
        $("live-bravo-total").textContent = bbDronesSlider.value;
        $("live-alpha-alive").textContent = baDronesSlider.value;
        $("live-bravo-alive").textContent = bbDronesSlider.value;
        $("live-alpha-kills").textContent = "0";
        $("live-bravo-kills").textContent = "0";
        $("kill-feed").innerHTML = '<div class="kill-feed-empty">Waiting for action...</div>';

        // Switch to live panel
        document.querySelectorAll(".battle-panel").forEach(p=>p.classList.remove("active"));
        $("panel-battle-live").classList.add("active");

        streamBattle(d.job_id);
    } catch(e) {
        console.error(e);
        $("btn-battle-launch").disabled = false;
        alert("Failed to start battle.");
    }
});

// ─── Battle SSE Stream ───
function streamBattle(jobId){
    battleEventSource = new EventSource(`/battle/stream/${jobId}`);

    battleEventSource.onmessage = e => {
        const termOut = $("battle-terminal-output");
        const l = document.createElement("div");
        l.textContent = `> ${e.data}`;
        termOut.appendChild(l);
        termOut.scrollTop = termOut.scrollHeight;
    };

    battleEventSource.addEventListener("progress", e => {
        $("battle-progress-text").textContent = e.data.replace("%","") + "%";
    });

    battleEventSource.addEventListener("battle", e => {
        try {
            const d = JSON.parse(e.data);
            $("live-alpha-alive").textContent = d.alpha_alive;
            $("live-bravo-alive").textContent = d.bravo_alive;
            $("live-alpha-kills").textContent = d.alpha_kills;
            $("live-bravo-kills").textContent = d.bravo_kills;

            // Update timer
            if(d.time !== undefined){
                const m = Math.floor(d.time/60);
                const s = Math.floor(d.time%60);
                $("battle-timer").textContent = `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
            }

            // Store positions for canvas
            if(d.positions) {
                battleLastPositions = d.positions;
                drawBattleArena(d.positions);
            }
        } catch(err) { console.error("Battle parse error:", err); }
    });

    battleEventSource.addEventListener("kill", e => {
        try {
            const k = JSON.parse(e.data);
            const feed = $("kill-feed");
            // Remove empty message
            const empty = feed.querySelector(".kill-feed-empty");
            if(empty) empty.remove();

            const item = document.createElement("div");
            item.className = "kill-feed-item";
            item.innerHTML = `
                <span class="kill-time">${k.time.toFixed(1)}s</span>
                <span class="kill-team-tag ${k.killer_team}">${k.killer_team.toUpperCase()}</span>
                <span class="kill-text">Drone #${k.killer} eliminated Drone #${k.victim}</span>
                <span class="kill-team-tag ${k.victim_team}">${k.victim_team.toUpperCase()}</span>
            `;
            feed.insertBefore(item, feed.firstChild);
            feed.scrollTop = 0;
        } catch(err) { console.error("Kill parse error:", err); }
    });

    battleEventSource.addEventListener("done", () => {
        battleEventSource.close();
        $("battle-terminal-badge").textContent = "DONE";
        $("battle-terminal-badge").style.background = "rgba(34,197,94,0.15)";
        $("battle-terminal-badge").style.color = "#22c55e";

        // Load results after short delay
        setTimeout(()=>loadBattleResults(jobId), 1500);
    });

    battleEventSource.onerror = () => {
        battleEventSource.close();
        $("btn-battle-launch").disabled = false;
        // May also mean battle is done
        setTimeout(()=>loadBattleResults(jobId), 1000);
    };
}

// ─── Battle Arena Canvas ───
function drawBattleArena(positions){
    const canvas = $("battle-canvas"), ctx = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * devicePixelRatio;
    canvas.height = rect.height * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const W = rect.width, H = rect.height;

    // Background
    ctx.fillStyle = "#0a0a0a";
    ctx.fillRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = "#1a1a1a";
    ctx.lineWidth = 1;
    for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
    for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}

    // Center line
    ctx.strokeStyle = "#2a2a2a";
    ctx.lineWidth = 2;
    ctx.setLineDash([5,5]);
    ctx.beginPath(); ctx.moveTo(W/2,0); ctx.lineTo(W/2,H); ctx.stroke();
    ctx.setLineDash([]);

    // Coordinate mapping — arena is -5 to 5 on both axes
    const mx = v => ((v + 5) / 10) * (W - 40) + 20;
    const my = v => H - (((v + 5) / 10) * (H - 40) + 20);

    // Draw connection lines within teams
    const alphas = positions.filter(p=>p.team==="alpha");
    const bravos = positions.filter(p=>p.team==="bravo");

    function drawTeamLinks(teamDrones, color){
        for(let i=0;i<teamDrones.length;i++){
            for(let j=i+1;j<teamDrones.length;j++){
                const dx=teamDrones[i].x-teamDrones[j].x, dy=teamDrones[i].y-teamDrones[j].y;
                const d=Math.sqrt(dx*dx+dy*dy);
                if(d<2){
                    ctx.strokeStyle=color.replace("1)",`${Math.max(0,1-d/2)*0.2})`);
                    ctx.lineWidth=1;
                    ctx.beginPath();
                    ctx.moveTo(mx(teamDrones[i].x),my(teamDrones[i].y));
                    ctx.lineTo(mx(teamDrones[j].x),my(teamDrones[j].y));
                    ctx.stroke();
                }
            }
        }
    }

    drawTeamLinks(alphas, "rgba(239,68,68,1)");
    drawTeamLinks(bravos, "rgba(59,130,246,1)");

    // Draw drones
    positions.forEach(p=>{
        const px = mx(p.x), py = my(p.y);
        const isAlpha = p.team === "alpha";
        const color = isAlpha ? "#ef4444" : "#3b82f6";

        // Glow
        const g = ctx.createRadialGradient(px,py,0,px,py,14);
        g.addColorStop(0, color+"55");
        g.addColorStop(1, color+"00");
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(px,py,14,0,Math.PI*2); ctx.fill();

        // Core
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(px,py,4,0,Math.PI*2); ctx.fill();
    });

    // Draw team labels
    ctx.fillStyle = "rgba(239,68,68,0.4)";
    ctx.font = "bold 10px 'Orbitron', monospace";
    ctx.fillText("ALPHA", 10, 18);

    ctx.fillStyle = "rgba(59,130,246,0.4)";
    ctx.textAlign = "right";
    ctx.fillText("BRAVO", W-10, 18);
    ctx.textAlign = "left";
}

// ─── Load Battle Results ───
async function loadBattleResults(jobId){
    try{
        const d = await(await fetch(`/battle/results/${jobId}`)).json();
        if(d.error){ console.log("Results not ready yet."); return; }

        // Switch to results panel
        document.querySelectorAll(".battle-panel").forEach(p=>p.classList.remove("active"));
        $("panel-battle-results").classList.add("active");

        // Winner banner
        const banner = $("winner-banner");
        banner.className = "winner-banner";
        if(d.winner === "alpha"){
            banner.classList.add("alpha-winner");
            $("winner-name").textContent = `TEAM ALPHA · ${(ALGO_NAMES[d.algo_alpha]||d.algo_alpha).toUpperCase()}`;
            $("winner-name").style.color = "#ef4444";
        } else if(d.winner === "bravo"){
            banner.classList.add("bravo-winner");
            $("winner-name").textContent = `TEAM BRAVO · ${(ALGO_NAMES[d.algo_bravo]||d.algo_bravo).toUpperCase()}`;
            $("winner-name").style.color = "#3b82f6";
        } else {
            banner.classList.add("draw-result");
            $("winner-name").textContent = "DRAW";
            $("winner-name").style.color = "#9ca3af";
        }

        // Team stats
        $("result-algo-alpha").textContent = (ALGO_NAMES[d.algo_alpha]||d.algo_alpha).toUpperCase();
        $("result-algo-bravo").textContent = (ALGO_NAMES[d.algo_bravo]||d.algo_bravo).toUpperCase();

        $("r-alpha-survivors").textContent = `${d.alpha.survivors} / ${d.alpha.initial}`;
        $("r-alpha-kills").textContent = d.alpha.kills;
        $("r-alpha-kd").textContent = d.alpha.kd_ratio;
        $("r-alpha-survival").textContent = `${d.alpha.survival_rate}%`;
        $("r-alpha-efficiency").textContent = `${d.alpha.efficiency}%`;

        $("r-bravo-survivors").textContent = `${d.bravo.survivors} / ${d.bravo.initial}`;
        $("r-bravo-kills").textContent = d.bravo.kills;
        $("r-bravo-kd").textContent = d.bravo.kd_ratio;
        $("r-bravo-survival").textContent = `${d.bravo.survival_rate}%`;
        $("r-bravo-efficiency").textContent = `${d.bravo.efficiency}%`;

        // Summary stats
        $("r-duration").textContent = `${d.duration}s`;
        $("r-first-blood").textContent = d.first_blood.team ? `${d.first_blood.team.toUpperCase()} @ ${d.first_blood.time}s` : "N/A";
        $("r-intensity").textContent = `${d.battle_intensity} kills/s`;
        $("r-total-kills").textContent = d.alpha.kills + d.bravo.kills;

        // Plotly charts
        const pc = {responsive:true, displayModeBar:false};
        if(d.kill_timeline_chart){
            Plotly.newPlot("chart-kill-timeline", d.kill_timeline_chart.data, d.kill_timeline_chart.layout, pc);
        }
        if(d.survival_chart){
            Plotly.newPlot("chart-survival", d.survival_chart.data, d.survival_chart.layout, pc);
        }
        if(d.kill_heatmap_chart){
            Plotly.newPlot("chart-kill-heatmap", d.kill_heatmap_chart.data, d.kill_heatmap_chart.layout, pc);
        }
    } catch(e){ console.error("Failed to load battle results:", e); }
}

// ─── Rematch / New Battle ───
$("btn-battle-rematch").addEventListener("click",()=>{
    document.querySelectorAll(".battle-panel").forEach(p=>p.classList.remove("active"));
    $("panel-battle-configure").classList.add("active");
    $("btn-battle-launch").disabled = false;
    // Keep the same config, just re-enable launch
    checkBattleLaunchReady();
    setTimeout(()=>$("btn-battle-launch").click(), 200);
});

$("btn-battle-new").addEventListener("click",()=>{
    document.querySelectorAll(".battle-panel").forEach(p=>p.classList.remove("active"));
    $("panel-battle-configure").classList.add("active");
    $("btn-battle-launch").disabled = true;
    battleAlgoAlpha = null;
    battleAlgoBravo = null;
    document.querySelectorAll(".battle-algo-card").forEach(c=>c.classList.remove("selected"));
    $("battle-terminal-container").classList.add("hidden");
    $("battle-terminal-badge").textContent = "BATTLING";
    $("battle-terminal-badge").style.background = "";
    $("battle-terminal-badge").style.color = "";
    ["chart-kill-timeline","chart-survival","chart-kill-heatmap"].forEach(id=>{const el=$(id);if(el)Plotly.purge(el);});
});

});

