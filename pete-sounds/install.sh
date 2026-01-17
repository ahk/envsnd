#!/bin/bash
# Pete-Sounds Installation Script for M4 Pro MacBook (48GB RAM)
# Self-contained: all files stay within this directory (except brew packages)
#
# Usage:
#   ./install.sh              Install deps and download default model (2.2b)
#   ./install.sh [MODEL]      Install deps and download specific model
#   ./install.sh all          Install deps and download all models
#   ./install.sh clean        Remove all downloaded/built files
#
# Models: 256m, 500m, 2.2b

set -e

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

# Model definitions
declare -A MODELS
MODELS[256m]="mlx-community/SmolVLM2-256M-Video-Instruct-mlx"
MODELS[500m]="mlx-community/SmolVLM2-500M-Video-Instruct-mlx"
MODELS[2.2b]="mlx-community/SmolVLM2-2.2B-Instruct-mlx"

DEFAULT_MODEL="2.2b"

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
uv pip install --python venv/bin/python mlx-vlm opencv-python pillow torch torchvision num2words sounddevice

# Determine which models to download
if [[ "${1}" == "all" ]]; then
    DOWNLOAD_MODELS=("256m" "500m" "2.2b")
elif [[ -n "${1}" ]]; then
    if [[ -z "${MODELS[${1}]}" ]]; then
        echo "Error: Unknown model '${1}'"
        echo "Available models: 256m, 500m, 2.2b, all"
        exit 1
    fi
    DOWNLOAD_MODELS=("${1}")
else
    DOWNLOAD_MODELS=("$DEFAULT_MODEL")
fi

echo ""
echo "Downloading model(s): ${DOWNLOAD_MODELS[*]}"
echo ""

for model_key in "${DOWNLOAD_MODELS[@]}"; do
    model_path="${MODELS[$model_key]}"
    echo "Downloading $model_key ($model_path)..."
    venv/bin/python -c "
from mlx_vlm import load
model, processor = load('$model_path')
print('  Cached successfully!')
"
done

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Available models:"
echo "  256m - Fastest, prose output only"
echo "  500m - Fast, prose output only"
echo "  2.2b - Slower, follows structured format"
echo ""
echo "To run:"
echo "  source venv/bin/activate"
echo "  python3 pete_sounds.py              # Uses 2.2b (default)"
echo "  python3 pete_sounds.py --model 256m # Fastest"
echo ""
echo "Self-contained installation:"
echo "  - Python + packages:  ./venv/"
echo "  - Model cache:        ./.hf_cache/"
echo ""
echo "To completely remove:"
echo "  rm -rf $PROJECT_DIR"
echo "  brew uninstall uv  # optional"
echo ""
