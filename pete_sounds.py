#!/usr/bin/env python3
"""
Pete-Sounds: Real-time video-to-text director for soundtrack generation.

Runs FastVLM inference on webcam feed, outputting director cues for a composer.
Optimized for sub-20ms TBT latency on Apple Silicon.

Usage:
    python3 pete_sounds.py [--help] [--resolution SIZE] [--max-tokens N]

Press Ctrl-C to exit.
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

# Use local cache directory to avoid polluting ~/.cache/huggingface
os.environ.setdefault("HF_HOME", str(Path(__file__).parent / ".hf_cache"))

import cv2
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pete-Sounds: Real-time video director for soundtrack generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 pete_sounds.py                    # Run with defaults
    python3 pete_sounds.py --resolution 64    # Ultra-low latency mode
    python3 pete_sounds.py --max-tokens 20    # Shorter responses

Press Ctrl-C to exit at any time.
        """
    )
    parser.add_argument(
        "--resolution", "-r",
        type=int,
        default=128,
        help="Frame resolution (default: 128). Lower = faster. Try 64 for lowest latency."
    )
    parser.add_argument(
        "--max-tokens", "-t",
        type=int,
        default=50,
        help="Maximum tokens per inference (default: 50). Lower = faster responses."
    )
    parser.add_argument(
        "--prompt-file", "-p",
        type=str,
        default="DIRECTOR.md",
        help="Path to prompt file (default: DIRECTOR.md)"
    )
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="Camera device index (default: 0)"
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=2.0,
        help="Target frames per second for inference (default: 2.0)"
    )
    return parser.parse_args()


def load_prompt(prompt_file: str) -> str:
    """Load the director prompt from file."""
    path = Path(prompt_file)
    if not path.exists():
        print(f"Error: Prompt file '{prompt_file}' not found.", file=sys.stderr)
        print("Create DIRECTOR.md or specify a different file with --prompt-file", file=sys.stderr)
        sys.exit(1)
    return path.read_text().strip()


def setup_signal_handler():
    """Setup graceful shutdown on Ctrl-C."""
    def handler(signum, frame):
        print("\n\nShutting down Pete-Sounds...", file=sys.stderr)
        sys.exit(0)
    signal.signal(signal.SIGINT, handler)


def capture_frame(cap, resolution: int) -> Image.Image:
    """Capture and downsample a frame from webcam."""
    ret, frame = cap.read()
    if not ret:
        return None

    # Convert BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Convert to PIL and downsample
    img = Image.fromarray(frame_rgb)
    img = img.resize((resolution, resolution), Image.Resampling.LANCZOS)

    return img


def main():
    args = parse_args()

    setup_signal_handler()

    print("=" * 60, file=sys.stderr)
    print("Pete-Sounds: Real-time Video Director", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Resolution: {args.resolution}x{args.resolution}", file=sys.stderr)
    print(f"Max tokens: {args.max_tokens}", file=sys.stderr)
    print(f"Target FPS: {args.fps}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Press Ctrl-C to exit", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)

    # Load prompt
    print("Loading director prompt...", file=sys.stderr)
    system_prompt = load_prompt(args.prompt_file)

    # Load model
    print("Loading FastVLM model (this may take a moment)...", file=sys.stderr)
    try:
        from mlx_vlm import load, stream_generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config
    except ImportError:
        print("Error: mlx-vlm not installed. Run ./install.sh first.", file=sys.stderr)
        sys.exit(1)

    model_path = "apple/FastVLM-0.5B-fp16"
    model, processor = load(model_path)
    config = load_config(model_path)

    print("Model loaded successfully!", file=sys.stderr)

    # Initialize webcam
    print(f"Initializing camera {args.camera}...", file=sys.stderr)
    cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        print(f"Error: Could not open camera {args.camera}", file=sys.stderr)
        print("Check that your Logitech Brio is connected.", file=sys.stderr)
        sys.exit(1)

    # Set camera to lower resolution for faster capture
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    print("Camera initialized!", file=sys.stderr)
    print("", file=sys.stderr)
    print("Starting inference loop... (output below)", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    frame_interval = 1.0 / args.fps
    last_frame_time = 0

    try:
        while True:
            current_time = time.time()

            # Rate limit frame capture
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.01)
                continue

            last_frame_time = current_time

            # Capture frame
            frame = capture_frame(cap, args.resolution)
            if frame is None:
                print("Warning: Failed to capture frame", file=sys.stderr)
                continue

            # Format prompt with system context
            user_prompt = f"{system_prompt}\n\nDescribe this frame with short director messages:"
            formatted_prompt = apply_chat_template(
                processor,
                config,
                user_prompt,
                num_images=1
            )

            # Run streaming inference
            for result in stream_generate(
                model,
                processor,
                formatted_prompt,
                image=[frame],
                max_tokens=args.max_tokens,
                temperature=0.7,
            ):
                # Output tokens to stdout as they're generated
                if hasattr(result, 'text'):
                    print(result.text, end="", flush=True)
                elif isinstance(result, str):
                    print(result, end="", flush=True)

            # Newline after each frame's output
            print(flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        print("\nPete-Sounds terminated.", file=sys.stderr)


if __name__ == "__main__":
    main()
