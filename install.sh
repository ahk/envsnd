#!/bin/bash
# FastVLM Installation Script for M4 Pro MacBook (48GB RAM)
# Optimized for lowest possible TBT (Time Between Tokens) latency

set -e

echo "=== Pete-Sounds: FastVLM Installation ==="
echo "Optimizing for M4 Pro with 48GB RAM"
echo ""

# Check if running on macOS with Apple Silicon
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: This script is designed for macOS"
    exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
    echo "Error: This script requires Apple Silicon (arm64)"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing MLX-VLM and dependencies..."
# mlx-vlm is the recommended package for running VLMs on Apple Silicon
pip install mlx-vlm

# OpenCV for webcam capture
pip install opencv-python

# Pillow for image processing
pip install pillow

echo ""
echo "Downloading FastVLM model (0.5B FP16 - optimal for low latency)..."
echo "Model: apple/FastVLM-0.5B-fp16"
echo ""
# Pre-download the model to cache for faster startup
python3 -c "
from mlx_vlm import load
print('Downloading and caching FastVLM-0.5B-fp16...')
model, processor = load('apple/FastVLM-0.5B-fp16')
print('Model cached successfully!')
"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Model Selection Rationale:"
echo "  - FastVLM-0.5B-fp16: Smallest model with full precision"
echo "  - 85x faster TTFT than comparable models"
echo "  - FP16 chosen over INT4/INT8 for quality with 48GB RAM headroom"
echo "  - Optimized FastViTHD encoder outputs fewer tokens"
echo ""
echo "To run the inference program:"
echo "  source venv/bin/activate"
echo "  python3 pete_sounds.py"
echo ""
