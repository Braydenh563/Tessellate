// translate-worker.js: the offline translator's engine, in a Worker of its own
// (WORLD_CLASS_PLAN 28.5 row 10, Brief 83). A classic worker, so the engine's
// Emscripten glue can be pulled in with `importScripts` and find `Module` on
// the worker's global scope, which is how that glue is written.
//
// The engine (Bergamot, MPL-2.0) and the model are not in the repository:
// they are the Settings, Packages download "Translate offline", served from
// the data dir by `api/routes_translate.py`. This file is ours; it drives the
// engine through its published bindings (BlockingService, TranslationModel,
// AlignedMemory) and copies none of the engine's own JavaScript.
//
// Messages in: `{id, pair, text}` with `pair` as `/translate/status` lists it.
// Out: `{id, ok: true, text, ms, loadMs}` or `{id, ok: false, error}`.

const TRANSLATE_FILES = "/translate/files/";

//: The matrix routines marian asks its host for, by the names the WASM build
//: exports its own copies under. Firefox supplies faster native ones; a page
//: has only these, which is what the measured times were taken with.
const TRANSLATE_GEMM = {
  int8_prepare_a: "int8PrepareAFallback",
  int8_prepare_b: "int8PrepareBFallback",
  int8_prepare_b_from_transposed: "int8PrepareBFromTransposedFallback",
  int8_prepare_b_from_quantized_transposed: "int8PrepareBFromQuantizedTransposedFallback",
  int8_prepare_bias: "int8PrepareBiasFallback",
  int8_multiply_and_add_bias: "int8MultiplyAndAddBiasFallback",
  int8_select_columns_of_b: "int8SelectColumnsOfBFallback",
};

//: Greedy decoding on one thread: the settings the engine's own client uses
//: for a page, and the ones the paragraph under a second was measured with.
const TRANSLATE_CONFIG = [
  "beam-size: 1",
  "normalize: 1.0",
  "word-penalty: 0",
  "cpu-threads: 0",
  "gemm-precision: int8shiftAlphaAll",
  "skip-cost: true",
  "alignment: soft",
  "quiet: true",
  "quiet-translation: true",
  "max-length-break: 128",
  "mini-batch-words: 1024",
  "workspace: 128",
  "max-length-factor: 2.0",
].join("\n");

const translateEngine = { module: null, loading: null, service: null, models: new Map() };

function translateLoadEngine() {
  if (translateEngine.loading) return translateEngine.loading;
  translateEngine.loading = new Promise((resolve, reject) => {
    const wasm = fetch(`${TRANSLATE_FILES}bergamot-translator-worker.wasm`);
    const gemm = {};
    for (const [name, own] of Object.entries(TRANSLATE_GEMM)) {
      gemm[name] = (...args) => self.Module.asm[own](...args);
    }
    self.Module = {
      instantiateWasm(imports, accept) {
        WebAssembly.instantiateStreaming(wasm, { ...imports, wasm_gemm: gemm })
          .then(({ instance }) => accept(instance))
          .catch(reject);
        return {};
      },
      onRuntimeInitialized() {
        translateEngine.module = self.Module;
        translateEngine.service = new self.Module.BlockingService({ cacheSize: 0 });
        resolve();
      },
      onAbort: (what) => reject(new Error(String(what || "the engine stopped"))),
      print: () => {},
      printErr: () => {},
    };
    try {
      importScripts(`${TRANSLATE_FILES}bergamot-translator-worker.js`);
    } catch (error) {
      reject(error);
    }
  });
  //: A failed load is not remembered: the next ask tries again (the package
  //: may have been installed in between).
  translateEngine.loading.catch(() => {
    translateEngine.loading = null;
  });
  return translateEngine.loading;
}

async function translateBytes(name) {
  const response = await fetch(`${TRANSLATE_FILES}${encodeURIComponent(name)}`);
  if (!response.ok) throw new Error(`${name} is not installed`);
  return new Uint8Array(await response.arrayBuffer());
}

function translateAligned(bytes, alignment) {
  const memory = new translateEngine.module.AlignedMemory(bytes.byteLength, alignment);
  memory.getByteArrayView().set(bytes);
  return memory;
}

//: One pair loaded at a time (L-world-class-41): each model is about 37 MB in
//: the engine's 32-bit heap, and the fifth pair kept beside four others
//: aborted the engine (measured in Chromium, 2026-11-22), which then failed
//: every later call. Switching pairs costs one load, about 2 s.
function translateDropOthers(key) {
  for (const [other, loading] of translateEngine.models) {
    if (other === key) continue;
    translateEngine.models.delete(other);
    loading.then((model) => model.delete()).catch(() => {});
  }
}

async function translateModel(pair) {
  const key = `${pair.from}-${pair.to}`;
  translateDropOthers(key);
  if (!translateEngine.models.has(key)) {
    //: One model at a time: the engine's memory aborted on the fifth model held
    //: at once (measured in Node 22 with the eight pairs), so a pair change frees
    //: the one before it. Switching back reloads in about 100 ms.
    for (const [other, held] of [...translateEngine.models]) {
      translateEngine.models.delete(other);
      held.then((old) => old.delete()).catch(() => {});
    }
    const loading = Promise.all([translateBytes(pair.model), translateBytes(pair.lex), translateBytes(pair.vocab)]).then(
      ([model, lex, vocab]) => {
        const vocabs = new translateEngine.module.AlignedMemoryList();
        vocabs.push_back(translateAligned(vocab, 64));
        return new translateEngine.module.TranslationModel(
          TRANSLATE_CONFIG,
          translateAligned(model, 256),
          translateAligned(lex, 64),
          vocabs,
          null,
        );
      },
    );
    translateEngine.models.set(key, loading);
    loading.catch(() => translateEngine.models.delete(key));
  }
  return translateEngine.models.get(key);
}

function translateRun(model, text) {
  const { module, service } = translateEngine;
  const input = new module.VectorString();
  const options = new module.VectorResponseOptions();
  input.push_back(text);
  options.push_back({ alignment: false, html: false, qualityScores: false });
  const responses = service.translate(model, input, options);
  const out = responses.get(0).getTranslatedText();
  input.delete();
  options.delete();
  responses.delete();
  return out;
}

self.addEventListener("message", async (event) => {
  const { id, pair, text } = event.data || {};
  try {
    const started = performance.now();
    await translateLoadEngine();
    const model = await translateModel(pair);
    const loaded = performance.now();
    const out = translateRun(model, String(text || ""));
    self.postMessage({ id, ok: true, text: out, ms: Math.round(performance.now() - loaded), loadMs: Math.round(loaded - started) });
  } catch (error) {
    self.postMessage({ id, ok: false, error: String((error && error.message) || error) });
  }
});
