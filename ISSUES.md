# Known Issues and Compromises

This document tracks technical issues encountered during development and the compromises made to resolve them.

---

## 1. Python Version Requirement

**Date:** 2025-01-15
**Issue:** System Python 3.9 is too old for mlx-vlm

**Details:**
The initial install script used the system Python (`python3 -m venv`), which on macOS defaults to Python 3.9. The mlx-vlm package requires Python 3.10+ and pip fell back to an ancient version (0.1.15) that didn't support FastVLM's architecture.

**Error:**
```
Model type llava_qwen2 not supported.
ModuleNotFoundError: No module named 'mlx_vlm.models.llava_qwen2'
```

**Resolution:**
Use `uv` (installed via Homebrew) to manage Python versions. uv automatically downloads Python 3.12 to the project's venv directory, keeping it self-contained.

**Trade-off:**
Requires Homebrew and adds `uv` as a system dependency (installed to `/opt/homebrew/`). The `./install.sh clean` command documents how to remove uv if desired.

---

## 2. FastVLM Model Compatibility with mlx-vlm

**Date:** 2025-01-15
**Issue:** Apple's official FP16 models fail to load in mlx-vlm

**Details:**
The official Apple models (`apple/FastVLM-0.5B-fp16`) have weight tensor names that don't match what mlx-vlm expects. This appears to be a format mismatch between Apple's export and mlx-vlm's loader.

**Error:**
```python
KeyError: 'vision_tower.vision_model.patch_embed.blocks.1.reparam_conv.weight'
```

The mlx-vlm code in `models/fastvlm/vision.py` tries to access weight keys that don't exist in the Apple-published model files.

**Resolution:**
Use community-converted models from [InsightKeeper/FastVLM-0.5B-MLX-8bit](https://huggingface.co/InsightKeeper/FastVLM-0.5B-MLX-8bit) which are explicitly exported for mlx-vlm compatibility.

**Trade-off:**
- Using 8-bit quantized weights instead of FP16
- Quality may be slightly reduced compared to full precision
- Dependent on community-maintained model conversion (not official Apple release)

**Ideal fix:**
Apple could publish MLX-native weights, or mlx-vlm could add a compatibility layer. See: https://github.com/apple/ml-fastvlm/issues/57

---

## 3. HuggingFace Cache Pollution

**Date:** 2025-01-15
**Issue:** Model downloads pollute `~/.cache/huggingface/`

**Details:**
By default, HuggingFace Hub downloads models to `~/.cache/huggingface/hub/`, which persists after deleting the project directory.

**Resolution:**
Set `HF_HOME` environment variable to `./.hf_cache/` in both `install.sh` and `pete_sounds.py`, keeping all downloaded models local to the project.

**Trade-off:**
None significant. Models are re-downloaded if the project is cloned fresh, but this is the expected behavior for a self-contained install.
