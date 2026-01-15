# Pete-Sounds Planning

## Project Overview
Real-time video-to-text director system for generative soundtrack creation.

## Architecture

```
[Webcam] -> [Frame Capture] -> [FastVLM Inference] -> [stdout tokens]
                                      ^
                                      |
                               [DIRECTOR.md prompt]
```

## Components

### 1. Installation Script (`install.sh`)
- Creates Python virtual environment
- Installs mlx-vlm for Apple Silicon optimized inference
- Installs OpenCV for webcam capture
- Pre-downloads FastVLM-0.5B-fp16 model to cache

### 2. Inference Program (`pete_sounds.py`)
- Captures webcam frames at configurable FPS
- Downsamples to low resolution (default 128x128) for latency
- Runs FastVLM streaming inference
- Outputs tokens to stdout in real-time
- Graceful Ctrl-C shutdown

### 3. Prompt File (`DIRECTOR.md`)
- System prompt for the vision model
- Defines output format for composer integration
- Structured message types (color, mood, energy, etc.)

## Hardware Target
- Apple M4 Pro MacBook
- 48GB unified memory
- Logitech Brio webcam

## Latency Optimization Strategy

### Model Selection
- **FastVLM-0.5B-fp16**: Smallest model, full precision
- 85x faster TTFT than comparable models (Apple benchmarks)
- FastViTHD encoder outputs fewer tokens

### Input Optimization
- Frame downsampling: 128x128 default, 64x64 for lowest latency
- Camera capture at 320x240 (pre-downsample)
- Target 2 FPS inference rate (adjustable)

### Output Optimization
- Max 50 tokens per frame (adjustable)
- Streaming generation for immediate output
- Simple newline-delimited format

## TBT Latency Target
Goal: sub-20ms time-between-tokens

Achieved through:
1. Smallest model variant (0.5B parameters)
2. FP16 precision (fast on M4 Pro with 48GB headroom)
3. Minimal input resolution
4. MLX native Apple Silicon optimization

## Future Enhancements
- OSC output for direct DAW integration
- Multiple camera support
- Prompt hot-reloading
- Latency metrics logging

## References
- [FastVLM Paper (CVPR 2025)](https://arxiv.org/abs/2412.13303)
- [Apple FastVLM Collection](https://huggingface.co/collections/apple/fastvlm)
- [MLX-VLM](https://github.com/Blaizzy/mlx-vlm)
