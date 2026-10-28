(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const state = { token: null, busy: false, closing: null };

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
    byId("send-button").disabled = busy;
    byId("message-input").disabled = busy;
    byId("end-session").disabled = busy;
  }

  async function sendMessage(value) {
    const text = String(value ?? byId("message-input").value).trim();
    if (!text || state.busy || !state.token) return;
    byId("message-input").value = "";
    clearTools();
    message("user", text);
    setBusy(true);
    byId("offline-card").classList.add("hidden");
    try {
      const result = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: text }) });
      message("assistant", result.reply, result.kind === "safety");
      state.closing = result.closing;
      updateInteraction(result);
      if (result.ended) {
        message("assistant", "This session is closed. You can reconnect when you are ready.");
        state.token = null;
        byId("chat-screen").classList.add("hidden");
        byId("connect-screen").classList.remove("hidden");
        setStatus("Not connected");
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
      const emergencyHint = typeof session.emergency_hint === "string" && session.emergency_hint.trim()
        ? session.emergency_hint.trim() : "your local emergency number";
      byId("emergency-line").textContent = `In an emergency, contact ${emergencyHint}.`;
      byId("offline-card").querySelector("p").textContent =
        `If you may be experiencing a medical emergency, contact ${emergencyHint} now. Messages are not queued for later delivery.`;
      byId("offline-card").classList.add("hidden");
      renderHistory(session.history);
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
    if (state.busy || !state.token) return;
    setBusy(true);
    try {
      const result = await api("/api/session/end", { method: "POST", body: JSON.stringify({}) });
      message("assistant", result.reply);
      updateInteraction(result);
    } catch (error) {
      message("assistant", error.message, true);
    } finally { setBusy(false); }
  }

  byId("connect-form").addEventListener("submit", connect);
  byId("chat-form").addEventListener("submit", (event) => { event.preventDefault(); sendMessage(); });
  byId("message-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); }
  });
  byId("end-session").addEventListener("click", endSession);

  api("/api/health").then((health) => {
    if (health.version) byId("app-version").textContent = `Tiny Baymax · v${health.version}`;
  }).catch(() => {});
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
})();
