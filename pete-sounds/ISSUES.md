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

## 3. FastVLM Loader Bug in mlx-vlm 0.3.9

**Date:** 2025-01-15
**Issue:** Community-converted FastVLM models also fail to load

**Details:**
After trying the InsightKeeper MLX-converted models as suggested in Issue #2, the same error occurs. This indicates a bug in mlx-vlm's FastVLM loader itself, not just a model format mismatch.

**Error:**
```python
KeyError: 'vision_tower.vision_model.patch_embed.blocks.1.reparam_conv.weight'
```

The mlx-vlm code in `models/fastvlm/vision.py:650` expects `reparam_conv.weight` keys that don't exist in any published FastVLM weights. FastVLM support was added in mlx-vlm 0.3.6, but appears broken in 0.3.9.

**Resolution:**
Pivot to SmolVLM2-256M-Video-Instruct-4bit which:
- Is proven to work with mlx-vlm for real-time webcam (see: https://github.com/davepoon/mlx-vlm-smolvlm-realtime-webcam)
- Has 256M parameters (even smaller than FastVLM-0.5B)
- Is specifically designed for video/streaming use cases

**Trade-off:**
- SmolVLM2 may have different output characteristics than FastVLM
- FastVLM claims 5.2x faster than SmolVLM, so we lose some potential speed
- Using a HuggingFace community model rather than Apple's official release

**Future work:**
File a bug report on https://github.com/Blaizzy/mlx-vlm/issues about the FastVLM loader.

---

## 4. SmolVLM2 Processor Dependencies

**Date:** 2025-01-15
**Issue:** SmolVLM2 video processor requires torch, torchvision, and num2words

**Details:**
The SmolVLM2 processor in transformers imports `torch` and `torchvision.transforms.v2` for video processing, even when used with MLX backend. Additionally, the SmolVLMProcessor requires `num2words` package.

**Error sequence:**
1. `ModuleNotFoundError: No module named 'torch'`
2. `ModuleNotFoundError: No module named 'torchvision'`
3. `ImportError: Package 'num2words' is required to run SmolVLM processor`

**Resolution:**
Added torch, torchvision, and num2words to the install dependencies. These are only used for processor setup, not inference (MLX handles the actual model execution).

**Trade-off:**
- Larger install footprint (~75MB for torch)
- torch is only used for video processor transforms, not inference

---

## 5. HuggingFace Cache Pollution

**Date:** 2025-01-15
**Issue:** Model downloads pollute `~/.cache/huggingface/`

**Details:**
By default, HuggingFace Hub downloads models to `~/.cache/huggingface/hub/`, which persists after deleting the project directory.

**Resolution:**
Set `HF_HOME` environment variable to `./.hf_cache/` in both `install.sh` and `pete_sounds.py`, keeping all downloaded models local to the project.

**Trade-off:**
None significant. Models are re-downloaded if the project is cloned fresh, but this is the expected behavior for a self-contained install.
