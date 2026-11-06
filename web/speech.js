(function (root) {
  "use strict";

  function pickVoice(voices, lang) {
    if (!Array.isArray(voices) || voices.length === 0) return null;
    const requested = typeof lang === "string" ? lang.trim().toLowerCase() : "";
    const exact = requested ? voices.filter((voice) => String(voice.lang || "").toLowerCase() === requested) : [];
    const english = voices.filter((voice) => String(voice.lang || "").toLowerCase().startsWith("en"));
    const candidates = exact.length ? exact : english;
    return candidates.find((voice) => voice.localService === true) || candidates[0] || null;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { pickVoice: pickVoice };
  if (root) root.BaymaxSpeech = { pickVoice: pickVoice };
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : null));
