#!/bin/bash
# FastVLM Installation Script for M4 Pro MacBook (48GB RAM)
# Optimized for lowest possible TBT (Time Between Tokens) latency
# Self-contained: all files stay within this directory (except brew packages)
#
# Usage:
#   ./install.sh         Install dependencies and download model
#   ./install.sh clean   Remove all downloaded/built files

set -e

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

# Handle clean command
if [[ "${1}" == "clean" ]]; then
    echo "Cleaning ephemeral files..."
    rm -rf "$PROJECT_DIR/venv"
    rm -rf "$PROJECT_DIR/.hf_cache"
    rm -rf "$PROJECT_DIR/__pycache__"
    echo "Removed:"
    echo "  - venv/"
    echo "  - .hf_cache/"
    echo "  - __pycache__/"
    echo ""
    echo "To also remove uv (installed via Homebrew):"
    echo "  brew uninstall uv"
    exit 0
fi

echo "=== Pete-Sounds: SmolVLM2 Installation ==="
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

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew is required but not installed."
    echo ""
    echo "Install Homebrew from https://brew.sh:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Install uv via Homebrew if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager via Homebrew..."
    brew install uv
fi

# Keep HuggingFace cache local to this project
export HF_HOME="$PROJECT_DIR/.hf_cache"
mkdir -p "$HF_HOME"

# Create venv with Python 3.12 (uv will download if needed)
echo "Creating Python 3.12 virtual environment..."
uv venv --python 3.12 venv

echo "Installing dependencies..."
# torch + torchvision + num2words required for SmolVLM2 video processor
uv pip install --python venv/bin/python mlx-vlm opencv-python pillow torch torchvision num2words

echo ""
echo "Downloading SmolVLM2 model (500M BF16)..."
echo "Model: mlx-community/SmolVLM2-500M-Video-Instruct-mlx"
echo ""

# Pre-download the model to cache
# Using SmolVLM2 - proven to work with mlx-vlm for real-time webcam
# FastVLM has loader bugs in mlx-vlm 0.3.9 (see ISSUES.md)
venv/bin/python -c "
from mlx_vlm import load
print('Downloading and caching SmolVLM2-500M-Video-Instruct-mlx...')
model, processor = load('mlx-community/SmolVLM2-500M-Video-Instruct-mlx')
print('Model cached successfully!')
"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Model Selection Rationale:"
echo "  - SmolVLM2-500M: Smallest available VLM (500M parameters)"
echo "  - BF16 precision (plenty of headroom with 48GB RAM)"
echo "  - Video-Instruct variant optimized for streaming frames"
echo "  - FastVLM has loader bugs in mlx-vlm 0.3.9 (see ISSUES.md)"
echo ""
echo "To run the inference program:"
echo "  source venv/bin/activate"
echo "  python3 pete_sounds.py"
echo ""
echo "Self-contained installation:"
echo "  - Python + packages:  ./venv/"
echo "  - Model cache:        ./.hf_cache/"
echo ""
echo "To completely remove:"
echo "  rm -rf $PROJECT_DIR"
echo "  brew uninstall uv  # optional, if you don't need uv elsewhere"
echo ""
