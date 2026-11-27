(function () {
  const d = JSON.parse(document.getElementById("prank-data").textContent);
  const el = document.getElementById("screen");
  const STY = {
    whatsapp:  { bg: "linear-gradient(180deg,#0b3d36,#075e54 45%,#04221e)", accent: "#25d366", sub: "WhatsApp video call" },
    telegram:  { bg: "linear-gradient(160deg,#2aabee,#1e6fb8 50%,#0d2f55)", accent: "#2aabee", sub: "Telegram Video Call" },
    signal:    { bg: "linear-gradient(160deg,#3a76f0,#1d3f8f 60%,#0a1d4a)", accent: "#3a76f0", sub: "Signal video call" },
    zangi:     { bg: "linear-gradient(160deg,#22c1c3,#0088a9 55%,#003d4f)", accent: "#22c1c3", sub: "Zangi video call" },
    instagram: { bg: "linear-gradient(140deg,#f58529,#dd2a7b 45%,#8134af 75%,#515bd4)", accent: "#dd2a7b", sub: "Instagram video call" },
    facebook:  { bg: "linear-gradient(160deg,#1877f2,#0a4dbb 55%,#041c4d)", accent: "#1877f2", sub: "Facebook video call" },
    messenger: { bg: "linear-gradient(160deg,#a033ff,#ff5280 55%,#ff7061)", accent: "#34c759", sub: "Messenger video chat" },
    facetime:  { bg: "linear-gradient(180deg,#3a3a3c,#1c1c1e)", accent: "#34c759", sub: "Video call…" },
  };
  const s = STY[d.style] || STY.whatsapp;
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const initials = d.callerName.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
  const avatar = (size, ring) => `
    <div class="relative" style="width:${size}px;height:${size}px">
      ${ring ? '<span class="absolute inset-0 animate-ping rounded-full bg-white/20"></span>' : ""}
      ${d.avatarUrl
        ? `<img src="${esc(d.avatarUrl)}" class="relative h-full w-full rounded-full object-cover shadow-2xl">`
        : `<div class="relative flex h-full w-full items-center justify-center rounded-full bg-white/20 font-semibold text-white" style="font-size:${size * 0.36}px">${esc(initials)}</div>`}
    </div>`;
  const track = (event) => fetch(`/api/pranks/${d.id}/track/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event }) }).catch(() => {});

  let ctx, ringTimer, callTimer;
  let stream = null;
  let speakerMuted = false;
  let cameraOff = false;
  let micMuted = false;
  let controlsVisible = false;
  let idleTimer = null;
  let bodyClickHandler = null;

  const FULLBLEED_VIDEO_STYLE = "position:absolute;top:0;left:0;width:100vw;height:100vh;width:100dvw;height:100dvh;object-fit:cover;object-position:center;background:#000;";

  function ringStart() {
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      const burst = () => {
        const t = ctx.currentTime;
        [0, 0.4].forEach((o) => {
          const g = ctx.createGain();
          g.gain.setValueAtTime(0, t + o); g.gain.linearRampToValueAtTime(0.25, t + o + 0.03);
          g.gain.setValueAtTime(0.25, t + o + 0.3); g.gain.linearRampToValueAtTime(0, t + o + 0.35);
          g.connect(ctx.destination);
          [440, 480].forEach((f) => { const os = ctx.createOscillator(); os.frequency.value = f; os.connect(g); os.start(t + o); os.stop(t + o + 0.36); });
        });
        if (navigator.vibrate) navigator.vibrate([400, 200, 400]);
      };
      burst(); ringTimer = setInterval(burst, 2500);
    } catch (e) {}
  }
  function ringStop() { clearInterval(ringTimer); if (navigator.vibrate) navigator.vibrate(0); if (ctx) ctx.close(); ctx = null; }

  async function startCameraAndMic(videoEl) {
    try {
      if (!stream) {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
          audio: true,
        });
      }
      if (videoEl) {
        videoEl.srcObject = stream;
        videoEl.muted = true;
        videoEl.play().catch(() => {});
      }
    } catch (err) {
      if (videoEl) {
        videoEl.replaceWith(Object.assign(document.createElement("div"),
          { className: "flex h-full w-full items-center justify-center bg-slate-800 text-[10px] text-slate-400 text-center px-1",
            innerText: "Camera off" }));
      }
    }
  }
  function stopAllTracks() { if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; } }
  window.addEventListener("pagehide", stopAllTracks);
  window.addEventListener("beforeunload", stopAllTracks);

  function tap() {
    el.innerHTML = `<div class="flex h-full flex-col items-center justify-center gap-6 bg-slate-950 p-6 text-center">
      <div class="text-6xl">🎥</div>
      <h2 class="text-xl font-semibold">${esc(d.callerName)} sent you a private call message</h2>
      <button id="go" class="rounded-full bg-emerald-500 px-8 py-4 text-lg font-bold">▶ Tap to open</button>
    </div>`;
    document.getElementById("go").onclick = () => { track("view"); waiting(); };
  }

  function waiting() {
    el.innerHTML = `<div class="flex h-full flex-col items-center justify-center gap-4 bg-slate-950"><div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-700 border-t-emerald-400"></div><p class="text-sm text-slate-400">Loading…</p></div>`;
    setTimeout(ringing, d.ringDelay * 1000);
  }

  function ringing() {
    el.innerHTML = `<div class="flex h-full flex-col" style="background:${s.bg}">
      <div class="mt-6 text-center text-sm text-white/80">🔒 End-to-end encrypted</div>
      <div class="flex flex-1 flex-col items-center justify-center gap-6">${avatar(128, true)}
        <div class="text-center"><p class="text-3xl font-semibold text-white">${esc(d.callerName)}</p><p class="mt-1 text-white/80">${s.sub}</p></div></div>
      <div class="relative flex flex-col items-center justify-end pb-24 pt-4" style="min-height:180px">
        <div class="text-center pointer-events-none mb-6">
          <p class="text-xs uppercase tracking-widest text-white/60">Swipe up to answer</p>
          <p class="mt-1 text-xs uppercase tracking-widest text-white/40">Swipe down to decline</p>
        </div>
        <div id="thumb" class="h-16 w-16 rounded-full flex items-center justify-center text-3xl shadow-xl animate-bounce-slow" style="background:${s.accent};touch-action:none;cursor:grab;user-select:none;">📞</div>
      </div>
    </div>`;
    ringStart();

    const thumb = document.getElementById("thumb");
    let startY = 0, dragging = false;
    thumb.addEventListener("pointerdown", (e) => { dragging = true; startY = e.clientY; thumb.setPointerCapture(e.pointerId); thumb.classList.remove("animate-bounce-slow"); });
    thumb.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const dy = e.clientY - startY;
      thumb.style.transform = `translateY(${dy}px)`;
      thumb.style.background = dy < -30 ? "#22c55e" : dy > 30 ? "#ef4444" : s.accent;
    });
    thumb.addEventListener("pointerup", (e) => {
      dragging = false;
      const dy = e.clientY - startY;
      if (dy < -60) { ringStop(); track("answer"); connected(); }
      else if (dy > 60) { ringStop(); reveal(); }
      else { thumb.style.transform = ""; thumb.style.background = s.accent; thumb.classList.add("animate-bounce-slow"); }
    });
  }

  const iconSpeakerOn  = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.8-1-3.3-2.5-4.1v8.2c1.5-.8 2.5-2.3 2.5-4.1zM14 3.2v2.1c2.9.9 5 3.5 5 6.7s-2.1 5.8-5 6.7v2.1c4-.9 7-4.5 7-8.8s-3-7.9-7-8.8z"/></svg>`;
  const iconSpeakerOff = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M16.5 12c0-1.8-1-3.3-2.5-4.1v2.4l2.4 2.4c0-.2.1-.4.1-.7zM19 12c0 .9-.2 1.7-.5 2.5l1.5 1.5c.6-1.2 1-2.5 1-4 0-3.3-2.1-6.1-5-6.9v2.1c1.8.7 3 2.5 3 4.8zM4.3 3L3 4.3 7.7 9H3v6h4l5 5v-6.7l4.3 4.3c-.7.5-1.5.9-2.3 1.2v2.1c1.3-.3 2.5-.9 3.5-1.7L19.7 21l1.3-1.3L4.3 3zM12 4L9.9 6.1 12 8.2V4z"/></svg>`;
  const iconMicOn  = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M12 15c1.7 0 3-1.3 3-3V6c0-1.7-1.3-3-3-3S9 4.3 9 6v6c0 1.7 1.3 3 3 3zm5-3c0 2.8-2.2 5-5 5s-5-2.2-5-5H5c0 3.5 2.6 6.4 6 6.9V22h2v-3.1c3.4-.5 6-3.4 6-6.9h-2z"/></svg>`;
  const iconMicOff = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M19 12c0 .6-.1 1.2-.2 1.7l1.6 1.6c.4-1 .6-2.1.6-3.3h-2zM4.3 3L3 4.3 6.4 7.7c-.2.4-.4 1-.4 1.3v6c0 1.7 1.3 3 3 3s3-1.3 3-3V12l4.7 4.7c-.6.2-1.2.3-1.7.3-2.8 0-5-2.2-5-5H8c0 3.5 2.6 6.4 6 6.9V22h2v-3.1c.9-.1 1.8-.4 2.6-.8L20.7 21l1.3-1.3L4.3 3z"/></svg>`;
  const iconCamOn  = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M17 10.5V7c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2v-3.5l4 4v-11l-4 4z"/></svg>`;
  const iconCamOff = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M21 6.5l-4 4V7c0-.6-.4-1-1-1H9.8l9.2 9.2V6.5zM3.3 2.3L2 3.6l2.4 2.4H3c-.6 0-1 .4-1 1v10c0 .6.4 1 1 1h12c.2 0 .3 0 .5-.1l3.9 3.9 1.3-1.3L3.3 2.3zM8 17H4V9h3.2l2 2H6v2h4v2h-2v2z"/></svg>`;
  const iconHangup = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" style="transform:rotate(135deg)"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.2.6 3.4.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.8 21 3 13.2 3 3.4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.2.2 2.3.6 3.4.1.3 0 .7-.2 1l-2.3 2z"/></svg>`;

  const btnClasses = "flex flex-col items-center gap-1";
  const spanBase = "flex h-14 w-14 items-center justify-center rounded-full transition-colors";
  const spanOn = "rgba(255,255,255,0.2)";
  const spanOff = "rgba(239,68,68,0.55)";

  function connected() {
    let sec = 0;
    const timeout = d.callTimeout || 0;
    let main;
    if (d.mediaType === "video" && d.videoUrl) {
      main = `<video id="main-video" src="${esc(d.videoUrl)}"
                    autoplay loop playsinline muted preload="auto"
                    style="${FULLBLEED_VIDEO_STYLE}"></video>`;
    } else if (d.mediaType === "photo" && d.photoUrl) {
      main = `<div class="absolute inset-0" style="background-image:url('${esc(d.photoUrl)}');background-size:cover;background-position:center;background-repeat:no-repeat;width:100vw;height:100vh;width:100dvw;height:100dvh;"></div>`;
    } else {
      main = `<div class="absolute inset-0 flex flex-col items-center justify-center" style="background:${s.bg}">${avatar(140)}<p class="mt-4 animate-pulse text-sm text-white/80">Connecting video…</p></div>`;
    }

    el.innerHTML = `<div class="relative h-full w-full overflow-hidden bg-black">${main}
      <div id="top-bar" class="absolute inset-x-0 top-0 bg-gradient-to-b from-black/60 to-transparent pb-8 pt-2 transition-opacity duration-300" style="opacity:0;pointer-events:none;">
        <div class="mt-3 text-center"><p class="text-lg font-semibold text-white">${esc(d.callerName)}</p><p id="t" class="text-sm text-white/80">🔒 00:00</p></div>
      </div>

      <div id="self-view" class="absolute right-3 top-24 h-36 w-24 overflow-hidden rounded-xl border border-white/30 bg-slate-800 shadow-lg">
        <video id="self" autoplay muted playsinline class="h-full w-full object-cover" style="transform:scaleX(-1)"></video>
      </div>

      <div id="controls" class="absolute inset-x-0 bottom-0 flex justify-center gap-4 pb-8 pt-10 bg-gradient-to-t from-black/70 to-transparent transition-opacity duration-300" style="opacity:0;pointer-events:none;">
        <button id="btn-speaker" class="${btnClasses} text-white/90">
          <span id="spk-span" class="${spanBase}" style="background:${spanOn}">${iconSpeakerOn}</span>
          <span class="text-[10px] uppercase tracking-wide">Speaker</span>
        </button>
        <button id="btn-mic" class="${btnClasses} text-white/90">
          <span id="mic-span" class="${spanBase}" style="background:${spanOn}">${iconMicOn}</span>
          <span class="text-[10px] uppercase tracking-wide">Mic</span>
        </button>
        <button id="btn-camera" class="${btnClasses} text-white/90">
          <span id="cam-span" class="${spanBase}" style="background:${spanOn}">${iconCamOn}</span>
          <span class="text-[10px] uppercase tracking-wide">Camera</span>
        </button>
        <button id="end" class="${btnClasses}">
          <span class="${spanBase} bg-red-500 text-white">${iconHangup}</span>
          <span class="text-[10px] uppercase tracking-wide text-white">End</span>
        </button>
      </div>
    </div>`;

    const mainVid = document.getElementById("main-video");
    if (mainVid) mainVid.play().catch(() => {});

    startCameraAndMic(document.getElementById("self"));

    // --- Auto-hide controls (self-view always visible) ---
    const topBar = document.getElementById("top-bar");
    const controls = document.getElementById("controls");

    function showControls() {
      controlsVisible = true;
      topBar.style.opacity = "1";
      topBar.style.pointerEvents = "auto";
      controls.style.opacity = "1";
      controls.style.pointerEvents = "auto";
      resetIdleTimer();
    }
    function hideControls() {
      controlsVisible = false;
      topBar.style.opacity = "0";
      topBar.style.pointerEvents = "none";
      controls.style.opacity = "0";
      controls.style.pointerEvents = "none";
    }
    function resetIdleTimer() {
      if (idleTimer) clearTimeout(idleTimer);
      idleTimer = setTimeout(() => { hideControls(); }, 4000);
    }

    if (bodyClickHandler) document.body.removeEventListener("click", bodyClickHandler);
    bodyClickHandler = (e) => {
      if (e.target.closest("#controls") || e.target.closest("#self-view")) {
        resetIdleTimer();
        return;
      }
      if (controlsVisible) { hideControls(); }
      else { showControls(); }
    };
    document.body.addEventListener("click", bodyClickHandler);

    showControls(); // visible for first 4s

    document.getElementById("btn-speaker").onclick = () => {
      speakerMuted = !speakerMuted;
      const mv = document.getElementById("main-video");
      if (mv) mv.muted = speakerMuted;
      const sp = document.getElementById("spk-span");
      sp.style.background = speakerMuted ? spanOff : spanOn;
      sp.innerHTML = speakerMuted ? iconSpeakerOff : iconSpeakerOn;
      resetIdleTimer();
    };

    document.getElementById("btn-mic").onclick = () => {
      micMuted = !micMuted;
      if (stream) stream.getAudioTracks().forEach((t) => { t.enabled = !micMuted; });
      const sp = document.getElementById("mic-span");
      sp.style.background = micMuted ? spanOff : spanOn;
      sp.innerHTML = micMuted ? iconMicOff : iconMicOn;
      resetIdleTimer();
    };

    document.getElementById("btn-camera").onclick = () => {
      cameraOff = !cameraOff;
      if (stream) stream.getVideoTracks().forEach((t) => { t.enabled = !cameraOff; });
      const sp = document.getElementById("cam-span");
      sp.style.background = cameraOff ? spanOff : spanOn;
      sp.innerHTML = cameraOff ? iconCamOff : iconCamOn;
      resetIdleTimer();
    };

    callTimer = setInterval(() => {
      sec++;
      const t = document.getElementById("t");
      if (t) t.textContent = `🔒 ${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
      if (timeout > 0 && sec >= timeout) {
        clearInterval(callTimer);
        if (idleTimer) clearTimeout(idleTimer);
        if (bodyClickHandler) document.body.removeEventListener("click", bodyClickHandler);
        stopAllTracks();
        reveal(sec);
      }
    }, 1000);

    document.getElementById("end").onclick = () => {
      clearInterval(callTimer);
      if (idleTimer) clearTimeout(idleTimer);
      if (bodyClickHandler) document.body.removeEventListener("click", bodyClickHandler);
      const dur = sec;
      stopAllTracks();
      reveal(dur);
    };
  }

  function reveal(durSeconds) {
    clearInterval(callTimer);
    if (idleTimer) clearTimeout(idleTimer);
    if (bodyClickHandler) document.body.removeEventListener("click", bodyClickHandler);
    stopAllTracks();
    const m = Math.floor((durSeconds || 0) / 60);
    const ss = (durSeconds || 0) % 60;
    const durText = `${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
    el.innerHTML = `<div class="flex h-full flex-col items-center justify-center gap-5 bg-gradient-to-br from-slate-800 via-slate-900 to-black p-6 text-center">
      <svg class="w-16 h-16 text-slate-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"/>
        <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 3.75l5.25 5.25m0-5.25L16.5 9"/>
      </svg>
      <h2 class="text-2xl font-bold text-white">Call ended</h2>
      <p class="text-sm text-slate-400">Duration ${durText}</p>
      <p class="mt-2 text-xs text-slate-500">Returning in 5 seconds…</p>
    </div>`;
    setTimeout(() => { window.location.href = "/"; }, 5000);
  }

  tap();
})();
