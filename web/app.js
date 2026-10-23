(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const state = { token: null, busy: false, closing: null, messages: [] };
  const CONSENT_VERSION = "1";
  const CONSENT_KEY = `tiny-baymax-consent-v${CONSENT_VERSION}`;

  function setStatus(text, connected = false) {
    const el = byId("connection-status");
    el.textContent = text;
    el.classList.toggle("connected", connected);
  }

  async function refreshVersion() {
    try {
      const health = await api("/api/health");
      if (health.version) byId("app-version").textContent = `Tiny Baymax · v${health.version}`;
    } catch (_) {
      // Version display is optional when the server is offline.
    }
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
    if (localStorage.getItem(CONSENT_KEY) !== "accepted") {
      byId("consent-error").textContent = "Please review and accept the privacy and safety information before connecting.";
      if (!consentDialog.open) consentDialog.showModal();
      return;
    }
    const token = byId("passcode").value.trim();
    if (!token) return;
    byId("connect-error").textContent = "";
    setStatus("Connecting…");
    try {
      const health = await fetch("/api/health", { cache: "no-store" }).then(async r => ({ ok: r.ok, data: await r.json() }));
      if (!health.ok || !health.data.ok) throw new Error("The server or its storage is unavailable.");
      state.token = token; // memory only; never localStorage/sessionStorage/cookies
      const session = await api("/api/session");
      if (localStorage.getItem(CONSENT_KEY) === "accepted") {
        await api("/api/settings", { method: "POST", body: JSON.stringify({ consented_version: CONSENT_VERSION }) });
      }
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

  function openSettings(title) {
    const panel = byId("settings-panel");
    panel.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = title;
    panel.append(heading);
    panel.classList.remove("hidden");
    return panel;
  }

  async function showMemories() {
    try {
      const data = await api("/api/memories");
      const panel = openSettings("Saved memories");
      if (!data.memories?.length) { const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "No saved memories."; panel.append(empty); return; }
      for (const item of data.memories) {
        const row = document.createElement("div"); row.className = "saved-item";
        const text = document.createElement("p"); text.textContent = item.fact;
        const remove = document.createElement("button"); remove.type = "button"; remove.className = "small-action"; remove.textContent = "Delete";
        remove.addEventListener("click", async () => { try { await api(`/api/memories/${item.id}`, { method: "DELETE" }); row.remove(); } catch (e) { message("assistant", e.message, true); } });
        row.append(text, remove); panel.append(row);
      }
      const clear = document.createElement("button"); clear.type = "button"; clear.className = "small-action"; clear.textContent = "Delete all memories";
      clear.addEventListener("click", async () => { try { await api("/api/memories", { method: "DELETE" }); panel.replaceChildren(heading); const e = document.createElement("p"); e.textContent = "No saved memories."; panel.append(e); } catch (err) { message("assistant", err.message, true); } });
      panel.append(clear);
    } catch (error) { message("assistant", error.message, true); }
  }

  async function showRatings() {
    try {
      const data = await api("/api/ratings");
      const panel = openSettings("Your self-reported ratings");
      if (!data.ratings?.length) { const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "No ratings saved."; panel.append(empty); return; }
      for (const item of data.ratings) {
        const row = document.createElement("div"); row.className = "saved-item";
        const text = document.createElement("p"); text.textContent = `${item.ts} · ${item.type}/${item.subtype}`;
        const actions = document.createElement("div"); actions.className = "rating-edit";
        const input = document.createElement("input"); input.type = "number"; input.min = "0"; input.max = "10"; input.step = "1"; input.value = String(item.rating); input.setAttribute("aria-label", "Rating from 0 to 10");
        const save = document.createElement("button"); save.type = "button"; save.className = "small-action"; save.textContent = "Save";
        save.addEventListener("click", async () => { const value = Number(input.value); if (!Number.isInteger(value) || value < 0 || value > 10) return; try { await api(`/api/ratings/${item.id}`, { method: "PATCH", body: JSON.stringify({ rating: value }) }); message("assistant", "Rating updated."); } catch (e) { message("assistant", e.message, true); } });
        const remove = document.createElement("button"); remove.type = "button"; remove.className = "small-action"; remove.textContent = "×"; remove.setAttribute("aria-label", "Delete rating");
        remove.addEventListener("click", async () => { try { await api(`/api/ratings/${item.id}`, { method: "DELETE" }); row.remove(); } catch (e) { message("assistant", e.message, true); } });
        actions.append(input, save, remove); row.append(text, actions); panel.append(row);
      }
    } catch (error) { message("assistant", error.message, true); }
  }

  async function exportData() {
    try {
      const data = await api("/api/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "tiny-baymax-export.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { message("assistant", error.message, true); }
  }

  async function resetEmotion() {
    if (!window.confirm("Reset Baymax's simulated emotion state?")) return;
    try { await api("/api/emotion/reset", { method: "POST", body: JSON.stringify({}) }); message("assistant", "My simulated state is back to baseline."); }
    catch (error) { message("assistant", error.message, true); }
  }

  async function deleteAllData() {
    if (!window.confirm("Delete all Baymax data stored for this account? This cannot be undone.")) return;
    const typed = window.prompt('Type DELETE to confirm complete data deletion:');
    if (typed !== "DELETE") return;
    try {
      const result = await api("/api/data", { method: "DELETE", body: JSON.stringify({ confirm: "DELETE" }) });
      byId("messages").replaceChildren();
      byId("settings-panel").classList.add("hidden");
      message("assistant", result.backups_purged === false
        ? (result.warning || "Your active data was deleted, but a backup could not be removed.")
        : "Your saved data has been deleted.");
    } catch (error) { message("assistant", error.message, true); }
  }

  byId("connect-form").addEventListener("submit", connect);
  byId("chat-form").addEventListener("submit", (event) => { event.preventDefault(); sendMessage(); });
  byId("message-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); }
  });
  byId("end-session").addEventListener("click", endSession);
  byId("show-memories").addEventListener("click", showMemories);
  byId("show-ratings").addEventListener("click", showRatings);
  byId("export-data").addEventListener("click", exportData);
  byId("reset-emotion").addEventListener("click", resetEmotion);
  byId("delete-all").addEventListener("click", deleteAllData);
  byId("clear-history").addEventListener("click", async () => {
    if (!window.confirm("Clear saved conversation history? Long-term memories stay intact.")) return;
    try { await api("/api/clear", { method: "POST", body: JSON.stringify({}) }); byId("messages").replaceChildren(); clearTools(); message("assistant", "Conversation cleared. Long-term memories remain."); }
    catch (error) { message("assistant", error.message, true); }
  });

  const consentDialog = byId("consent-dialog");
  if (localStorage.getItem(CONSENT_KEY) !== "accepted") consentDialog.showModal();
  byId("review-consent").addEventListener("click", () => {
    byId("consent-error").textContent = "";
    if (!consentDialog.open) consentDialog.showModal();
  });
  byId("consent-form").addEventListener("submit", (event) => {
    const submitter = event.submitter;
    if (submitter && submitter.value === "accept") {
      localStorage.setItem(CONSENT_KEY, "accepted");
      byId("consent-error").textContent = "";
      byId("connect-error").textContent = "";
    } else {
      localStorage.removeItem(CONSENT_KEY);
      byId("consent-error").textContent = "You have not accepted.";
      byId("connect-error").textContent = "Consent not accepted. Review privacy & safety and accept before connecting.";
    }
  });

  refreshVersion();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
})();
