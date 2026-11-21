// caption-tap-worker.js: the live captions' microphone tap, in an AudioWorklet
// (L580). It replaces the deprecated ScriptProcessorNode: the browser runs
// this on its audio thread and hands the page one Float32Array of 4096
// samples at a time, which captions.js decimates and sends exactly as before.
//
// Loaded with `audioWorklet.addModule` from the app's own origin, which the
// policy's `script-src 'self'` covers; no blob: or data: URL is involved, so
// the policy is unchanged. It has a scope of its own (no page globals).

const CAPTION_TAP_BLOCK = 4096;

class CaptionTap extends AudioWorkletProcessor {
  constructor() {
    super();
    this.block = new Float32Array(CAPTION_TAP_BLOCK);
    this.at = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;
    for (let i = 0; i < channel.length; i++) {
      this.block[this.at++] = channel[i];
      if (this.at === CAPTION_TAP_BLOCK) {
        const full = this.block;
        this.block = new Float32Array(CAPTION_TAP_BLOCK);
        this.at = 0;
        this.port.postMessage(full, [full.buffer]);
      }
    }
    return true;
  }
}

registerProcessor("caption-tap", CaptionTap);
