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
    algos.forEach(algo=>{
        const card=document.createElement("div");
        card.className="algo-card";
        if(algo.is_custom) card.classList.add("custom-card");
        card.innerHTML=`<div class="card-icon"><i class="${algo.icon}"></i></div><h3>${algo.name}</h3><p>${algo.desc}</p>`;
        card.addEventListener("click",()=>selectAlgo(card,algo));
        algoGrid.appendChild(card);
    });
});
function selectAlgo(el,algo){
    document.querySelectorAll(".algo-card").forEach(c=>c.classList.remove("selected"));
    document.querySelectorAll(".card-icon").forEach(i=>i.classList.remove("orange"));
    el.classList.add("selected"); el.querySelector(".card-icon").classList.add("orange");
    selectedAlgo=algo; btnLaunch.disabled=false;
    if(algo.has_shapes||algo.is_custom){extraOptionsGroup.classList.remove("hidden");formSelectGroup.classList.toggle("hidden",!algo.has_shapes);customUploadGroup.classList.toggle("hidden",!algo.is_custom);}
    else extraOptionsGroup.classList.add("hidden");
}

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

});
