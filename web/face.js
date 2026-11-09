(function (root) {
  "use strict";

  function finiteField(emotion, field, fallback) {
    const value = emotion && typeof emotion === "object" ? emotion[field] : undefined;
    return typeof value === "number" && Number.isFinite(value) ? value : fallback;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function faceParams(emotion, reducedMotion) {
    const concern = finiteField(emotion, "concern", 0.10);
    const happiness = finiteField(emotion, "happiness", 0.50);
    const concernExcess = clamp((concern - 0.10) / 0.50, 0, 1);
    const happyExcess = clamp((happiness - 0.50) / 0.30, 0, 1);
    return {
      eyeScaleX: clamp(1 + 0.15 * concernExcess + 0.10 * happyExcess, 0.90, 1.15),
      eyeScaleY: clamp(1 + 0.40 * concernExcess - 0.35 * happyExcess, 0.60, 1.40),
      eyeTiltDeg: 8 * concernExcess,
      blinkIntervalMs: clamp(5000 + 4000 * concernExcess - 1500 * happyExcess, 3000, 9000),
      blinkDurationMs: 160 + 60 * happyExcess,
      blinkEnabled: !reducedMotion
    };
  }

  function reactionFor(result) {
    if (!result || typeof result !== "object" || result.kind !== "chat") return null;
    if (!result.emotion || typeof result.emotion !== "object") return null;
    const concern = result.emotion.concern;
    if (typeof concern !== "number" || !Number.isFinite(concern) || concern >= 0.30) return null;
    if (result.mode === "celebrate") return "hop";
    if (result.mode === "playful") return "wink";
    return null;
  }

  function mountFace(svg, initialEmotion) {
    if (!svg || !root || typeof root.setTimeout !== "function") {
      return { update: function () {}, setBusy: function () {}, setComposerText: function () {}, triggerReaction: function () {}, setSpeaking: function () {}, stop: function () {} };
    }
    const motionQuery = typeof root.matchMedia === "function"
      ? root.matchMedia("(prefers-reduced-motion: reduce)") : null;
    let emotion = initialEmotion;
    let timer = null;
    let blinkTimer = null;
    let hopTimer = null;
    let winkTimer = null;
    let stopped = false;
    let busy = false;
    let composerHasText = false;
    let speaking = false;
    let current = faceParams(emotion, Boolean(motionQuery && motionQuery.matches));
    const blinkGroups = Array.from(svg.querySelectorAll(".face-eye-blink"));
    const hopGroup = svg.querySelector(".face-hop");

    function reduced() { return Boolean(motionQuery && motionQuery.matches); }
    function concernBlocksGaze() {
      const concern = finiteField(emotion, "concern", 0.10);
      return concern >= 0.50;
    }
    function setBlinking(active, group) {
      const targets = group ? [group] : blinkGroups;
      targets.forEach(function (item) { item.classList.toggle("is-blinking", active); });
    }
    function clearTimers() {
      if (timer !== null) root.clearTimeout(timer);
      if (blinkTimer !== null) root.clearTimeout(blinkTimer);
      timer = null;
      blinkTimer = null;
      setBlinking(false);
    }
    function schedule() {
      if (stopped || !current.blinkEnabled || root.document?.hidden) return;
      const jitter = 0.8 + Math.random() * 0.4;
      timer = root.setTimeout(blink, Math.round(current.blinkIntervalMs * jitter));
    }
    function blink() {
      timer = null;
      if (stopped || !current.blinkEnabled || root.document?.hidden) return schedule();
      setBlinking(true);
      blinkTimer = root.setTimeout(function () {
        setBlinking(false);
        blinkTimer = null;
        schedule();
      }, current.blinkDurationMs);
    }
    function applyGaze() {
      let x = 0;
      let y = 0;
      if (!reduced() && !concernBlocksGaze()) {
        if (busy) { x = 1.2; y = -1.8; }
        else if (composerHasText) { y = 1.2; }
      }
      svg.style.setProperty("--gaze-x", x + "px");
      svg.style.setProperty("--gaze-y", y + "px");
    }
    function apply() {
      current = faceParams(emotion, reduced());
      svg.style.setProperty("--eye-scale-x", String(current.eyeScaleX));
      svg.style.setProperty("--eye-scale-y", String(current.eyeScaleY));
      svg.style.setProperty("--eye-tilt-left", (-current.eyeTiltDeg) + "deg");
      svg.style.setProperty("--eye-tilt-right", current.eyeTiltDeg + "deg");
      svg.style.setProperty("--blink-duration", current.blinkDurationMs + "ms");
      applyGaze();
      svg.classList.toggle("is-speaking", speaking && !reduced());
      if (reduced()) {
        if (hopTimer !== null) root.clearTimeout(hopTimer);
        if (winkTimer !== null) root.clearTimeout(winkTimer);
        hopTimer = winkTimer = null;
        if (hopGroup) hopGroup.classList.remove("is-hopping");
        setBlinking(false);
      }
      clearTimers();
      schedule();
    }
    function onVisibilityChange() { clearTimers(); schedule(); }
    function onMotionChange() { apply(); }
    if (root.document) root.document.addEventListener("visibilitychange", onVisibilityChange);
    if (motionQuery) {
      if (typeof motionQuery.addEventListener === "function") motionQuery.addEventListener("change", onMotionChange);
      else if (typeof motionQuery.addListener === "function") motionQuery.addListener(onMotionChange);
    }
    apply();

    return {
      update: function (nextEmotion) { emotion = nextEmotion; apply(); },
      setBusy: function (value) { busy = Boolean(value); applyGaze(); },
      setComposerText: function (value) { composerHasText = Boolean(String(value || "").trim()); applyGaze(); },
      setSpeaking: function (value) {
        speaking = Boolean(value);
        svg.classList.toggle("is-speaking", speaking && !reduced());
      },
      triggerReaction: function (reaction) {
        if (reduced()) return;
        if (reaction === "hop" && hopGroup) {
          if (hopTimer !== null) root.clearTimeout(hopTimer);
          hopGroup.classList.remove("is-hopping");
          void hopGroup.getBoundingClientRect();
          hopGroup.classList.add("is-hopping");
          hopTimer = root.setTimeout(function () {
            hopGroup.classList.remove("is-hopping");
            hopTimer = null;
          }, 520);
        } else if (reaction === "wink" && blinkGroups.length) {
          const eye = blinkGroups[0];
          if (winkTimer !== null) root.clearTimeout(winkTimer);
          setBlinking(false, eye);
          eye.classList.add("is-blinking");
          winkTimer = root.setTimeout(function () {
            eye.classList.remove("is-blinking");
            winkTimer = null;
          }, current.blinkDurationMs);
        }
      },
      stop: function () {
        stopped = true;
        clearTimers();
        if (hopTimer !== null) root.clearTimeout(hopTimer);
        if (winkTimer !== null) root.clearTimeout(winkTimer);
        if (hopGroup) hopGroup.classList.remove("is-hopping");
        svg.classList.remove("is-speaking");
        if (root.document) root.document.removeEventListener("visibilitychange", onVisibilityChange);
        if (motionQuery && typeof motionQuery.removeEventListener === "function") motionQuery.removeEventListener("change", onMotionChange);
      }
    };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { faceParams: faceParams, reactionFor: reactionFor };
  if (root) root.BaymaxFace = { faceParams: faceParams, reactionFor: reactionFor, mountFace: mountFace };
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : null));
