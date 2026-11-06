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
    const concernExcess = Math.max(0, concern - 0.10) / 0.90;
    const happyExcess = Math.max(0, happiness - 0.50) / 0.50;
    return {
      eyeScale: clamp(1 + 0.15 * concernExcess - 0.10 * happyExcess, 0.88, 1.15),
      blinkIntervalMs: clamp(5000 + 3500 * concernExcess - 1000 * happyExcess, 3500, 8500),
      blinkDurationMs: 160 + 60 * happyExcess,
      blinkEnabled: !reducedMotion
    };
  }

  function mountFace(svg, initialEmotion) {
    if (!svg || !root || typeof root.setTimeout !== "function") return { update: function () {}, stop: function () {} };
    const motionQuery = typeof root.matchMedia === "function"
      ? root.matchMedia("(prefers-reduced-motion: reduce)") : null;
    let emotion = initialEmotion;
    let timer = null;
    let blinkTimer = null;
    let stopped = false;
    let current = faceParams(emotion, Boolean(motionQuery && motionQuery.matches));

    function clearTimers() {
      if (timer !== null) root.clearTimeout(timer);
      if (blinkTimer !== null) root.clearTimeout(blinkTimer);
      timer = null;
      blinkTimer = null;
      svg.classList.remove("is-blinking");
    }

    function schedule() {
      if (stopped || !current.blinkEnabled || root.document?.hidden) return;
      const jitter = 0.8 + Math.random() * 0.4;
      timer = root.setTimeout(blink, Math.round(current.blinkIntervalMs * jitter));
    }

    function blink() {
      timer = null;
      if (stopped || !current.blinkEnabled || root.document?.hidden) return schedule();
      svg.classList.add("is-blinking");
      blinkTimer = root.setTimeout(function () {
        svg.classList.remove("is-blinking");
        blinkTimer = null;
        schedule();
      }, current.blinkDurationMs);
    }

    function apply() {
      current = faceParams(emotion, Boolean(motionQuery && motionQuery.matches));
      svg.style.setProperty("--eye-scale", String(current.eyeScale));
      svg.style.setProperty("--blink-duration", `${current.blinkDurationMs}ms`);
      clearTimers();
      schedule();
    }

    function onVisibilityChange() {
      clearTimers();
      schedule();
    }

    function onMotionChange() { apply(); }
    if (root.document) root.document.addEventListener("visibilitychange", onVisibilityChange);
    if (motionQuery) {
      if (typeof motionQuery.addEventListener === "function") motionQuery.addEventListener("change", onMotionChange);
      else if (typeof motionQuery.addListener === "function") motionQuery.addListener(onMotionChange);
    }
    apply();

    return {
      update: function (nextEmotion) { emotion = nextEmotion; apply(); },
      stop: function () {
        stopped = true;
        clearTimers();
        if (root.document) root.document.removeEventListener("visibilitychange", onVisibilityChange);
        if (motionQuery && typeof motionQuery.removeEventListener === "function") motionQuery.removeEventListener("change", onMotionChange);
      }
    };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { faceParams: faceParams };
  if (root) root.BaymaxFace = { faceParams: faceParams, mountFace: mountFace };
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : null));
