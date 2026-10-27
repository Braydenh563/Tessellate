# fastembed-1027: search by meaning on fastembed (the owner, 2026-10-27)

"Replace sentence-transformers + torch with fastembed (onnxruntime) for search by meaning, keeping the same model family (BAAI/bge-small-en-v1.5; fastembed's ONNX build of it)."

Scratch (session scratchpad): `fe-venv` (fastembed 0.9.1 and the app's deps), `st-venv` (torch CPU and sentence-transformers), `fe-scripts/` (embed2.py, st_vectors.py, custom.py, native.py, rss.py).

## Done
- Engine: `ai/embeddings.py` loads `fastembed.TextEmbedding` from the snapshot folder (`specific_model_path`, offline), threads at load; `core/embedmodels.py` `OnnxBuild` per catalogue row (fastembed's own sources), `fetch` downloads only the ONNX build; `embedfind` needs an ONNX export; `hub_refusal` split (`_format_refusal`).
- Persisted values: backend "sentence-transformers" reads as "fastembed" (`embedmodels.backend_name`); migration `f1b3c5d7e9a2` renames stored vectors, so no re-embed.
- Measured: wheels 57 MB (Linux, py3.13), model 66 MB, RSS +244 MB loaded (+315 after long notes), cosine torch vs fastembed 0.9999987 min over 8 texts, one embed 13.7 ms vs 257 ms.

## Left
- Not run: the app end to end with fastembed (consent, download, embed, search) in a browser.
- Old torch-format folders are removable from Settings, Search and index, Old search files (`embedmodels.legacy_files`, `remove_legacy`; packaged app: `extras.legacy_engine`); a source install still removes torch with pip by hand.
- A model chosen from this computer with PyTorch weights only now reads as the default; its renamed vectors are stranded until a switch (`model_manager.embedding_st_model`).
- nomic-embed-text-v1.5 is native in fastembed and could be one press (embedmodels.py nomic row, why_not).
- Qwen3 and bge-m3 builds untested for real.
- done: 75f9be0 (engine, migration, consent copy, docs); next: e2e over HTTP, then hand back.
- e2e on :8961 with real fastembed (HTTP, no browser): no download before the yes; after it, ready in 5.2 s (5 files, 65 MB); vectors stored as `fastembed:BAAI/bge-small-en-v1.5`, 384 dims; server RSS 623 MB (peak 685 MB); "taxes owed" finds the tax note (0.725).
- Found, then fixed: a note saved before the yes waited for the next warm-up backfill or periodic pass; the yes now warms the model and backfills (`embeddings.warm_then_backfill`). "cat" and "a pet asleep" miss the kitten note (cosine 0.51, 0.57), below the configured cutoff; vectors match the old engine to 1e-6, so this is not new.
- done: ad9352f (backfill fills another model's vectors), 92f4dfd (the yes backfills). Measured: multilingual-e5-small, 20 texts, "query: " prefix, same weights through sentence-transformers and fastembed, min cosine 0.9999999 (max component difference 1.3e-07); migration f1b3c5d7e9a2 now renames only bge-small and e5-small (`embedmodels.VECTORS_KEPT`), every other model is embedded again by the backfill.
- next: item 1 (upgraders: the notice says the engine moved), then 2 (remove old files), 4 (dead torch leftovers).
- done: 1da1f7c (upgraders told the engine moved), ca4d37d (torch launcher opt-in removed), item 2 (Old search files, below).
- Checked in a browser on :8793 (:8791 was another agent's server) with a fake HF cache: Old search files rows at 1440 (694 px wide, Remove 86x32) and 390 (264 px, Remove 86x44), no horizontal overflow, Remove deleted the BGE folder and left the ONNX one; the moved-engine notice at 390 (371 px wide, right edge 380 of 390).
- Not verified: a real PyTorch-era cache and a real packaged build (the extras removal runs on a fake dist-info folder); the welcome-card wording in a browser; Windows launcher edits (text only).
- Found and fixed on the way: a pip removal (`extras._run_uninstall`) left the installer marked running, so the next install was refused until a restart.
- Left: nomic-embed-text-v1.5 as one press; Qwen3 and bge-m3 builds untested for real.
