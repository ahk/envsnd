#!/usr/bin/env python3
"""
Pete: Main orchestrator for the pete-sounds pipeline.

Runs the director (vision model) and composer (synth) together, interleaving
their output to create a complete performance score.

Usage:
    python3 pete.py                      # Run with defaults
    python3 pete.py --record output.mp3  # Record audio to MP3
    python3 pete.py --score score.txt    # Save score to file

Press Ctrl-C for graceful shutdown.
"""

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pete: Real-time video-to-soundtrack pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 pete.py                              # Run with audio output
    python3 pete.py --record session.mp3         # Record to MP3
    python3 pete.py --score score.txt            # Save score to file
    python3 pete.py --model 500m --bpm 160       # Faster model, slower tempo

Press Ctrl-C to stop. Audio will be saved on graceful shutdown.
        """
    )
    parser.add_argument(
        '--record', '-r',
        type=str,
        default=None,
        help='Record audio to MP3 file'
    )
    parser.add_argument(
        '--score', '-s',
        type=str,
        default=None,
        help='Save score to file (default: stdout only)'
    )
    parser.add_argument(
        '--model', '-m',
        type=str,
        choices=['256m', '500m', '2.2b'],
        default='2.2b',
        help='Vision model size (default: 2.2b)'
    )
    parser.add_argument(
        '--prompt', '-p',
        type=str,
        default=None,
        help='Custom prompt file (default: auto-select structured prompt for model)'
    )
    parser.add_argument(
        '--bpm',
        type=int,
        default=174,
        help='Composer tempo in BPM (default: 174)'
    )
    parser.add_argument(
        '--resolution',
        type=int,
        default=128,
        help='Director frame resolution (default: 128)'
    )
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=50,
        help='Director max tokens per inference (default: 50)'
    )
    parser.add_argument(
        '--no-audio',
        action='store_true',
        help='Disable audio playback'
    )
    return parser.parse_args()


class Pipeline:
    """Manages the director and composer subprocesses."""

    def __init__(self, args):
        self.args = args
        self.director_proc = None
        self.composer_proc = None
        self.running = False
        self.score_file = None
        self.start_time = None

        # Select prompt file
        if args.prompt:
            self.prompt_file = args.prompt
        else:
            # Use structured output prompt for composer compatibility
            self.prompt_file = f"prompts/smolvlm2-{args.model}-strict-output.md"
            if not Path(self.prompt_file).exists():
                self.prompt_file = f"prompts/smolvlm2-{args.model}.md"

    def log(self, source: str, message: str):
        """Log a message with timestamp and source tag."""
        if not self.start_time:
            self.start_time = time.time()

        elapsed = time.time() - self.start_time
        timestamp = f"[{elapsed:7.2f}s]"

        # Format based on source
        if source == "director":
            line = f"{timestamp} [DIR] {message}"
        elif source == "composer":
            line = f"{timestamp} [MIX] {message}"
        else:
            line = f"{timestamp} [{source.upper():3s}] {message}"

        # Output to stdout
        print(line, flush=True)

        # Write to score file if specified
        if self.score_file:
            self.score_file.write(line + "\n")
            self.score_file.flush()

    def start(self):
        """Start the pipeline."""
        self.running = True
        self.start_time = time.time()

        # Open score file if specified
        if self.args.score:
            self.score_file = open(self.args.score, 'w')
            self.log("sys", f"Score file: {self.args.score}")

        # Print header
        print("=" * 70, flush=True)
        print("  PETE-SOUNDS: Real-time Video-to-Soundtrack Pipeline", flush=True)
        print("=" * 70, flush=True)
        print(f"  Model:      {self.args.model}", flush=True)
        print(f"  Prompt:     {self.prompt_file}", flush=True)
        print(f"  BPM:        {self.args.bpm}", flush=True)
        print(f"  Recording:  {self.args.record or 'disabled'}", flush=True)
        print(f"  Score file: {self.args.score or 'stdout only'}", flush=True)
        print("=" * 70, flush=True)
        print("  Press Ctrl-C to stop", flush=True)
        print("=" * 70, flush=True)
        print(flush=True)

        if self.score_file:
            self.score_file.write("=" * 70 + "\n")
            self.score_file.write(f"  PETE-SOUNDS Performance Score\n")
            self.score_file.write(f"  Recorded: {datetime.now().isoformat()}\n")
            self.score_file.write(f"  Model: {self.args.model} | BPM: {self.args.bpm}\n")
            self.score_file.write("=" * 70 + "\n\n")

        # Build director command
        director_cmd = [
            sys.executable, "pete_sounds.py",
            "--model", self.args.model,
            "--prompt-file", self.prompt_file,
            "--resolution", str(self.args.resolution),
            "--max-tokens", str(self.args.max_tokens),
        ]

        # Build composer command
        composer_cmd = [
            sys.executable, "composer.py",
            "--bpm", str(self.args.bpm),
        ]
        if self.args.record:
            composer_cmd.extend(["--record", self.args.record])
        if self.args.no_audio:
            composer_cmd.append("--no-audio")

        # Start director process
        self.log("sys", "Starting director (vision model)...")
        self.director_proc = subprocess.Popen(
            director_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Start composer process, reading from director's stdout
        self.log("sys", "Starting composer (synth engine)...")
        self.composer_proc = subprocess.Popen(
            composer_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Start reader threads
        self.threads = []

        # Director stdout -> composer stdin + log
        t1 = threading.Thread(target=self._pipe_director_to_composer, daemon=True)
        t1.start()
        self.threads.append(t1)

        # Director stderr -> log
        t2 = threading.Thread(target=self._read_director_stderr, daemon=True)
        t2.start()
        self.threads.append(t2)

        # Composer stdout -> log
        t3 = threading.Thread(target=self._read_composer_stdout, daemon=True)
        t3.start()
        self.threads.append(t3)

        # Composer stderr -> log (skip header noise)
        t4 = threading.Thread(target=self._read_composer_stderr, daemon=True)
        t4.start()
        self.threads.append(t4)

        self.log("sys", "Pipeline started")

    def _pipe_director_to_composer(self):
        """Read director stdout, log it, and pipe to composer."""
        try:
            for line in self.director_proc.stdout:
                if not self.running:
                    break
                line = line.rstrip()
                if line and not line.startswith(('=', '-', 'Pete', 'Model', 'Loading',
                                                  'Press', 'Resolution', 'Max', 'Target',
                                                  'Prompt', 'Camera', 'Starting', 'Fetching')):
                    self.log("director", line)

                # Always forward to composer
                if self.composer_proc and self.composer_proc.stdin:
                    try:
                        self.composer_proc.stdin.write(line + "\n")
                        self.composer_proc.stdin.flush()
                    except (BrokenPipeError, OSError):
                        break
        except Exception as e:
            if self.running:
                self.log("sys", f"Director read error: {e}")

    def _read_director_stderr(self):
        """Read and log director stderr (status messages)."""
        try:
            for line in self.director_proc.stderr:
                if not self.running:
                    break
                line = line.rstrip()
                # Only log important messages
                if line and ('loaded' in line.lower() or 'error' in line.lower()
                            or 'warning' in line.lower() or 'initialized' in line.lower()):
                    self.log("sys", line)
        except Exception:
            pass

    def _read_composer_stdout(self):
        """Read and log composer stdout (bar info)."""
        try:
            for line in self.composer_proc.stdout:
                if not self.running:
                    break
                line = line.rstrip()
                if line and 'Bar' in line:
                    # Extract just the musical info, already has timestamp
                    # Format: [  12.11s] Bar    8 | root=58 ...
                    # We want to log it with our own timestamp as composer output
                    if '|' in line:
                        parts = line.split('|', 1)
                        if len(parts) > 1:
                            bar_info = parts[0].split('Bar')[-1].strip()
                            music_info = parts[1].strip()
                            self.log("composer", f"Bar {bar_info} | {music_info}")
        except Exception:
            pass

    def _read_composer_stderr(self):
        """Read composer stderr (skip most, log important)."""
        try:
            for line in self.composer_proc.stderr:
                if not self.running:
                    break
                line = line.rstrip()
                if line and ('error' in line.lower() or 'saving' in line.lower()
                            or 'saved' in line.lower()):
                    self.log("sys", line)
        except Exception:
            pass

    def stop(self):
        """Stop the pipeline gracefully."""
        if not self.running:
            return

        self.running = False
        print(flush=True)
        self.log("sys", "Shutting down pipeline...")

        # Close composer stdin to signal EOF
        if self.composer_proc and self.composer_proc.stdin:
            try:
                self.composer_proc.stdin.close()
            except Exception:
                pass

        # Send SIGINT to processes for graceful shutdown
        for name, proc in [("director", self.director_proc), ("composer", self.composer_proc)]:
            if proc and proc.poll() is None:
                try:
                    proc.send_signal(signal.SIGINT)
                except Exception:
                    pass

        # Wait for processes to finish (with timeout)
        for name, proc in [("director", self.director_proc), ("composer", self.composer_proc)]:
            if proc:
                try:
                    proc.wait(timeout=5)
                    self.log("sys", f"{name.capitalize()} stopped")
                except subprocess.TimeoutExpired:
                    proc.kill()
                    self.log("sys", f"{name.capitalize()} killed (timeout)")

        # Close score file
        if self.score_file:
            self.log("sys", f"Score saved to {self.args.score}")
            self.score_file.close()

        self.log("sys", "Pipeline terminated")

    def wait(self):
        """Wait for pipeline to finish."""
        try:
            while self.running:
                # Check if processes are still alive
                if self.director_proc and self.director_proc.poll() is not None:
                    self.log("sys", "Director process ended")
                    break
                if self.composer_proc and self.composer_proc.poll() is not None:
                    self.log("sys", "Composer process ended")
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass


def main():
    args = parse_args()

    pipeline = Pipeline(args)

    # Setup signal handler
    def signal_handler(signum, frame):
        pipeline.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        pipeline.start()
        pipeline.wait()
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
