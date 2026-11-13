(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const state = { token: null, busy: false, closing: null, sessionEnding: false, gestureTimer: null, closeTimer: null };
  const SPEAK_PREFERENCE_KEY = "tiny-baymax-speak";
  const speechAvailable = typeof window.speechSynthesis !== "undefined" && typeof window.SpeechSynthesisUtterance === "function";
  let speakEnabled = true;
  let selectedVoice = null;
  let recognition = null;
  let faceController = null;

  function readSpeakPreference() {
    try {
      const saved = window.localStorage.getItem(SPEAK_PREFERENCE_KEY);
      return saved === null ? true : saved === "true";
    } catch (_) { return true; }
  }

  function saveSpeakPreference() {
    try { window.localStorage.setItem(SPEAK_PREFERENCE_KEY, String(speakEnabled)); } catch (_) {}
  }

  function setFaceState(name, enabled) {
    const face = byId("baymax-face");
    if (face) face.classList.toggle(`is-${name}`, Boolean(enabled));
  }

  function applyGesture(gesture, duration = 1900) {
    const face = byId("baymax-face");
    if (!face || !["wave", "smile_blush", "celebrate"].includes(gesture)) return;
    if (state.gestureTimer) window.clearTimeout(state.gestureTimer);
    ["waving", "smiling", "celebrating"].forEach((name) => setFaceState(name, false));
    const className = gesture === "wave" ? "waving" : gesture === "smile_blush" ? "smiling" : "celebrating";
    setFaceState(className, true);
    state.gestureTimer = window.setTimeout(() => {
      setFaceState(className, false);
      state.gestureTimer = null;
    }, duration);
  }

  function cancelSpeech() {
    if (speechAvailable) window.speechSynthesis.cancel();
    setFaceState("speaking", false);
  }

  function refreshVoice() {
    if (!speechAvailable || !window.BaymaxSpeech) return;
    selectedVoice = window.BaymaxSpeech.pickVoice(window.speechSynthesis.getVoices(), navigator.language);
  }

  function stopRecognition() {
    if (recognition) {
      try { recognition.stop(); } catch (_) {}
    }
  }

  function showSpeechError(text) {
    byId("speech-error").textContent = text;
  }

  function speakReply(text) {
    if (!speechAvailable || !speakEnabled || !text) return;
    refreshVoice();
    const utterance = new window.SpeechSynthesisUtterance(String(text));
    utterance.rate = 0.85;
    utterance.pitch = 0.9;
    if (selectedVoice) utterance.voice = selectedVoice;
    if (navigator.language) utterance.lang = navigator.language;
    cancelSpeech();
    utterance.onstart = () => setFaceState("speaking", true);
    utterance.onend = () => setFaceState("speaking", false);
    utterance.onerror = () => setFaceState("speaking", false);
    window.speechSynthesis.speak(utterance);
  }

  function updateFace(emotion) {
    if (!window.BaymaxFace) return;
    if (!faceController) faceController = window.BaymaxFace.mountFace(byId("baymax-face"), emotion);
    else faceController.update(emotion);
  }

  function setStatus(text, connected = false) {
    const el = byId("connection-status");
    el.textContent = text;
    el.classList.toggle("connected", connected);
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (state.token) headers["X-Baymax-Token"] = state.token;
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch(path, { ...options, headers, cache: "no-store" });
    const text = await response.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { error: "The server returned an invalid response." }; }
    if (!response.ok) {
      const error = new Error(data.error || `Request failed (${response.status}).`);
      error.status = response.status;
      error.code = data.code;
      throw error;
    }
    return data;
  }

  function message(role, text, system = false) {
    const row = document.createElement("div");
    row.className = `message-row ${role === "user" ? "user" : "assistant"}${system ? " system" : ""}`;
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? "YOU" : "B";
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = String(text ?? "");
    row.append(avatar, bubble);
    byId("messages").append(row);
    byId("messages").scrollTop = byId("messages").scrollHeight;
  }

  function renderHistory(items) {
    byId("messages").replaceChildren();
    for (const item of (items || [])) {
      if (item && (item.role === "user" || item.role === "assistant")) message(item.role, item.content);
    }
  }

  function clearTools() {
    const tools = byId("interaction-tools");
    tools.replaceChildren();
    tools.classList.add("hidden");
  }

  function showQuickReplies(items) {
    const tools = byId("interaction-tools");
    tools.replaceChildren();
    for (const label of items) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip";
      button.textContent = label;
      button.addEventListener("click", () => sendMessage(label));
      tools.append(button);
    }
    tools.classList.toggle("hidden", !items.length);
  }

  function showRating(rating) {
    const tools = byId("interaction-tools");
    tools.replaceChildren();
    const label = document.createElement("p");
    label.className = "hint";
    label.textContent = `Choose a ${rating.about === "pain" ? "pain" : "feeling"} rating from 0 to 10, or skip.`;
    tools.append(label);
    for (let value = rating.min; value <= rating.max; value += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip";
      button.textContent = String(value);
      button.setAttribute("aria-label", `Rate ${value} out of 10`);
      button.addEventListener("click", () => sendMessage(String(value)));
      tools.append(button);
    }
    const skip = document.createElement("button");
    skip.type = "button";
    skip.className = "chip skip";
    skip.textContent = "Skip";
    skip.addEventListener("click", () => sendMessage("skip"));
    tools.append(skip);
    tools.classList.remove("hidden");
  }

  function updateInteraction(reply) {
    clearTools();
    if (reply.ui?.rating) return showRating(reply.ui.rating);
    if (reply.ui?.quick_replies?.length) return showQuickReplies(reply.ui.quick_replies);
  }

  function setBusy(busy) {
    state.busy = busy;
    setFaceState("thinking", busy);
    byId("send-button").disabled = busy;
    byId("message-input").disabled = busy;
    byId("end-session").disabled = busy;
  }

  async function sendMessage(value) {
    const text = String(value ?? byId("message-input").value).trim();
    if (!text || state.busy || state.sessionEnding || !state.token) return;
    cancelSpeech();
    stopRecognition();
    byId("message-input").value = "";
    clearTools();
    message("user", text);
    setBusy(true);
    byId("offline-card").classList.add("hidden");
    try {
      const result = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: text }) });
      message("assistant", result.reply, result.kind === "safety");
      if (["chat", "safety", "ritual"].includes(result.kind)) {
        if (result.ended) cancelSpeech();
        else speakReply(result.reply);
      } else if (result.ended) cancelSpeech();
      if (Object.prototype.hasOwnProperty.call(result, "emotion")) updateFace(result.emotion);
      state.closing = result.closing;
      updateInteraction(result);
      if (result.ended) {
        state.sessionEnding = true;
        applyGesture(result.ui?.gesture || "wave", 1500);
        state.closeTimer = window.setTimeout(closeSessionVisually, 1500);
      } else if (result.ui?.gesture) {
        applyGesture(result.ui.gesture);
      }
    } catch (error) {
      byId("offline-card").classList.remove("hidden");
      if (error.status === 401 || error.status === 429) {
        state.token = null;
        byId("chat-screen").classList.add("hidden");
        byId("connect-screen").classList.remove("hidden");
        byId("connect-error").textContent = error.message;
        setStatus("Not connected");
      } else {
        message("assistant", "I cannot reach the server right now. I have not queued your message for later.", true);
      }
    } finally {
      setBusy(false);
      byId("message-input").focus();
    }
  }

  function closeSessionVisually() {
    if (state.gestureTimer) window.clearTimeout(state.gestureTimer);
    state.gestureTimer = null;
    state.closeTimer = null;
    state.token = null;
    state.sessionEnding = false;
    ["waving", "smiling", "celebrating", "thinking", "listening", "speaking", "attentive"].forEach((name) => setFaceState(name, false));
    message("assistant", "This session is closed. You can reconnect when you are ready.");
    byId("chat-screen").classList.add("hidden");
    byId("connect-screen").classList.remove("hidden");
    setStatus("Not connected");
  }

  async function connect(event) {
    event.preventDefault();
    if (state.busy) return;
    const token = byId("passcode").value.trim();
    if (!token) return;
    byId("connect-error").textContent = "";
    setStatus("Connecting…");
    try {
      const health = await fetch("/api/health", { cache: "no-store" }).then(async r => ({ ok: r.ok, data: await r.json() }));
      if (!health.ok || !health.data.ok) throw new Error("The server or its storage is unavailable.");
      state.token = token;
      const session = await api("/api/session");
      state.closing = null;
      state.sessionEnding = false;
      const emergencyHint = typeof session.emergency_hint === "string" && session.emergency_hint.trim()
        ? session.emergency_hint.trim() : "your local emergency number";
      byId("offline-card").querySelector("p").textContent =
        `If you may be experiencing a medical emergency, contact ${emergencyHint} now. Messages are not queued for later delivery.`;
      byId("offline-card").classList.add("hidden");
      renderHistory(session.history);
      updateFace(session.emotion);
      if (session.ui?.gesture) applyGesture(session.ui.gesture);
      byId("connect-screen").classList.add("hidden");
      byId("chat-screen").classList.remove("hidden");
      byId("end-session").disabled = false;
      setStatus("Connected", true);
      if (!session.history?.length) message("assistant", "Hello. I am Baymax, your personal healthcare companion. How are you feeling today?");
      byId("message-input").focus();
    } catch (error) {
      state.token = null;
      setStatus("Not connected");
      byId("connect-error").textContent = error.message || "Could not connect. Check the passcode and server.";
    }
  }

  async function endSession() {
    if (state.busy || state.sessionEnding || !state.token) return;
    setBusy(true);
    try {
      const result = await api("/api/session/end", { method: "POST", body: JSON.stringify({}) });
      message("assistant", result.reply);
      speakReply(result.reply);
      if (Object.prototype.hasOwnProperty.call(result, "emotion")) updateFace(result.emotion);
      updateInteraction(result);
      if (result.ui?.gesture) applyGesture(result.ui.gesture);
    } catch (error) {
      message("assistant", error.message, true);
    } finally { setBusy(false); }
  }

  if (speechAvailable) {
    speakEnabled = readSpeakPreference();
    const voiceButton = byId("voice-toggle");
    function renderVoiceButton() {
      voiceButton.textContent = speakEnabled ? "Voice on" : "Voice off";
      voiceButton.setAttribute("aria-pressed", String(speakEnabled));
    }
    renderVoiceButton();
    voiceButton.addEventListener("click", () => {
      speakEnabled = !speakEnabled;
      saveSpeakPreference();
      renderVoiceButton();
      if (!speakEnabled) cancelSpeech();
    });
    refreshVoice();
    if (typeof window.speechSynthesis.addEventListener === "function") {
      window.speechSynthesis.addEventListener("voiceschanged", refreshVoice);
    } else {
      window.speechSynthesis.onvoiceschanged = refreshVoice;
    }
  } else {
    byId("voice-toggle").classList.add("hidden");
  }

  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (typeof Recognition === "function") {
    recognition = new Recognition();
    recognition.lang = navigator.language || "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;
    const micButton = byId("mic-button");
    micButton.addEventListener("click", () => {
      showSpeechError("");
      cancelSpeech();
      try {
        recognition.start();
        micButton.setAttribute("aria-pressed", "true");
      } catch (_) {
        showSpeechError("Microphone is unavailable right now.");
      }
    });
    recognition.onstart = () => setFaceState("listening", true);
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results || []).map((item) => item[0]?.transcript || "").join(" ").trim();
      if (transcript) byId("message-input").value = transcript;
      byId("message-input").focus();
    };
    recognition.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") showSpeechError("Microphone permission was denied.");
      else showSpeechError("Microphone is unavailable right now.");
      micButton.setAttribute("aria-pressed", "false");
      setFaceState("listening", false);
    };
    recognition.onend = () => {
      micButton.setAttribute("aria-pressed", "false");
      setFaceState("listening", false);
    };
  } else {
    byId("mic-button").classList.add("hidden");
  }

  byId("connect-form").addEventListener("submit", connect);
  byId("chat-form").addEventListener("submit", (event) => { event.preventDefault(); sendMessage(); });
  byId("message-input").addEventListener("focus", () => setFaceState("attentive", true));
  byId("message-input").addEventListener("blur", () => setFaceState("attentive", false));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state.sessionEnding) closeSessionVisually();
  });
  byId("message-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); }
  });
  byId("end-session").addEventListener("click", endSession);

  api("/api/health").then((health) => {
    if (health.version) byId("app-version").textContent = `Tiny Baymax · v${health.version}`;
  }).catch(() => {});
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
})();
