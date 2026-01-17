#!/usr/bin/env python3
"""
Composer: Real-time soundtrack generator driven by director cues.

Reads structured output from the director (stdin) and synthesizes a 4-channel
jazz-over-DnB ensemble: lead, rhythm, bass, and percussion.

Usage:
    python3 pete_sounds.py --prompt-file prompts/smolvlm2-2.2b-strict-output.md | \
        tee score.txt | python3 composer.py

    # Or with MP3 recording:
    python3 pete_sounds.py ... | tee score.txt | python3 composer.py --record output.mp3

Press Ctrl-C to exit.
"""

import argparse
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np

# Attempt to import audio libraries
try:
    import sounddevice as sd
except ImportError:
    print("Error: sounddevice not installed. Run: pip install sounddevice", file=sys.stderr)
    sys.exit(1)

# Attempt to import MIDI library
try:
    import mido
    MIDI_AVAILABLE = True
except ImportError:
    MIDI_AVAILABLE = False
    print("Warning: mido not installed. MIDI output disabled. Install with: pip install mido", file=sys.stderr)


# ============================================================================
# Musical Constants
# ============================================================================

SAMPLE_RATE = 44100
BPM = 174  # Classic DnB tempo
BEAT_DURATION = 60.0 / BPM
BAR_DURATION = BEAT_DURATION * 4

# Jazz chord intervals (semitones from root)
CHORDS = {
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dom7": [0, 4, 7, 10],
    "dim7": [0, 3, 6, 9],
    "min9": [0, 3, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14],
    "dom9": [0, 4, 7, 10, 14],
    "min11": [0, 3, 7, 10, 14, 17],
    "dom13": [0, 4, 7, 10, 14, 21],
}

# Scales (semitones from root)
SCALES = {
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "blues": [0, 3, 5, 6, 7, 10],
    "pentatonic_minor": [0, 3, 5, 7, 10],
}

# Color to root note mapping (MIDI note numbers, octave 3)
COLOR_TO_ROOT = {
    "red": 57,      # A
    "orange": 59,   # B
    "yellow": 60,   # C
    "green": 62,    # D
    "blue": 58,     # Bb (jazz!)
    "purple": 56,   # Ab
    "brown": 55,    # G
    "gray": 53,     # F
    "black": 51,    # Eb
    "white": 60,    # C
}

# Mood to chord type and scale
MOOD_TO_HARMONY = {
    "happy": ("maj9", "major", 0.8),
    "sad": ("min9", "minor", 0.4),
    "calm": ("maj7", "dorian", 0.3),
    "excited": ("dom9", "mixolydian", 0.9),
    "serious": ("min7", "dorian", 0.5),
    "neutral": ("dom7", "mixolydian", 0.6),
}

# Person activity to rhythm density
PERSON_TO_RHYTHM = {
    "sitting": 0.3,
    "standing": 0.5,
    "walking": 0.7,
    "talking": 0.6,
    "waving": 0.8,
    "none": 0.4,
}

# Object to melodic character
OBJECT_TO_CHARACTER = {
    "computer": "staccato",
    "phone": "glitchy",
    "cup": "warm",
    "chair": "steady",
    "book": "flowing",
    "plant": "organic",
    "window": "airy",
    "none": "neutral",
}

# Energy to tempo multiplier and intensity
ENERGY_TO_DYNAMICS = {
    "low": (0.85, 0.4),
    "medium": (1.0, 0.7),
    "high": (1.1, 1.0),
}


# ============================================================================
# Director State
# ============================================================================

@dataclass
class DirectorState:
    """Current state from director cues."""
    color: str = "gray"
    mood: str = "neutral"
    person: str = "none"
    obj: str = "none"  # 'object' is reserved
    energy: str = "medium"

    # Derived musical parameters
    root_note: int = 53  # F
    chord_type: str = "dom7"
    scale: str = "mixolydian"
    density: float = 0.5
    intensity: float = 0.7
    tempo_mult: float = 1.0
    character: str = "neutral"

    def update(self, **kwargs):
        """Update state and recalculate derived parameters."""
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

        # Recalculate derived parameters
        self.root_note = COLOR_TO_ROOT.get(self.color, 53)

        harmony = MOOD_TO_HARMONY.get(self.mood, ("dom7", "mixolydian", 0.6))
        self.chord_type = harmony[0]
        self.scale = harmony[1]
        self.intensity = harmony[2]

        self.density = PERSON_TO_RHYTHM.get(self.person, 0.5)
        self.character = OBJECT_TO_CHARACTER.get(self.obj, "neutral")

        dynamics = ENERGY_TO_DYNAMICS.get(self.energy, (1.0, 0.7))
        self.tempo_mult = dynamics[0]
        self.intensity = min(1.0, self.intensity * dynamics[1])


# ============================================================================
# Synthesis Engine
# ============================================================================

class Oscillator:
    """Basic oscillator with multiple waveforms."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sr = sample_rate
        self.phase = 0.0

    def sine(self, freq: float, duration: float, amp: float = 0.5) -> np.ndarray:
        t = np.linspace(0, duration, int(self.sr * duration), False)
        return amp * np.sin(2 * np.pi * freq * t + self.phase)

    def saw(self, freq: float, duration: float, amp: float = 0.5) -> np.ndarray:
        t = np.linspace(0, duration, int(self.sr * duration), False)
        return amp * (2 * (t * freq % 1) - 1)

    def square(self, freq: float, duration: float, amp: float = 0.5) -> np.ndarray:
        t = np.linspace(0, duration, int(self.sr * duration), False)
        return amp * np.sign(np.sin(2 * np.pi * freq * t))

    def triangle(self, freq: float, duration: float, amp: float = 0.5) -> np.ndarray:
        t = np.linspace(0, duration, int(self.sr * duration), False)
        return amp * (2 * np.abs(2 * (t * freq % 1) - 1) - 1)

    def noise(self, duration: float, amp: float = 0.5) -> np.ndarray:
        samples = int(self.sr * duration)
        return amp * np.random.uniform(-1, 1, samples)


def midi_to_freq(midi_note: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def adsr_envelope(duration: float, attack: float = 0.01, decay: float = 0.1,
                  sustain: float = 0.7, release: float = 0.1,
                  sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Generate ADSR envelope."""
    samples = int(sample_rate * duration)
    envelope = np.zeros(samples)

    attack_samples = int(sample_rate * attack)
    decay_samples = int(sample_rate * decay)
    release_samples = int(sample_rate * release)
    sustain_samples = samples - attack_samples - decay_samples - release_samples

    if sustain_samples < 0:
        # Short note - just do attack and release
        half = samples // 2
        envelope[:half] = np.linspace(0, 1, half)
        envelope[half:] = np.linspace(1, 0, samples - half)
        return envelope

    idx = 0
    # Attack
    envelope[idx:idx + attack_samples] = np.linspace(0, 1, attack_samples)
    idx += attack_samples
    # Decay
    envelope[idx:idx + decay_samples] = np.linspace(1, sustain, decay_samples)
    idx += decay_samples
    # Sustain
    envelope[idx:idx + sustain_samples] = sustain
    idx += sustain_samples
    # Release
    envelope[idx:] = np.linspace(sustain, 0, samples - idx)

    return envelope


def lowpass_filter(signal: np.ndarray, cutoff: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Simple one-pole lowpass filter."""
    rc = 1.0 / (2 * np.pi * cutoff)
    dt = 1.0 / sample_rate
    alpha = dt / (rc + dt)

    output = np.zeros_like(signal)
    output[0] = signal[0]
    for i in range(1, len(signal)):
        output[i] = output[i-1] + alpha * (signal[i] - output[i-1])
    return output


def highpass_filter(signal: np.ndarray, cutoff: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Simple one-pole highpass filter."""
    rc = 1.0 / (2 * np.pi * cutoff)
    dt = 1.0 / sample_rate
    alpha = rc / (rc + dt)

    output = np.zeros_like(signal)
    output[0] = signal[0]
    for i in range(1, len(signal)):
        output[i] = alpha * (output[i-1] + signal[i] - signal[i-1])
    return output


# ============================================================================
# MIDI Output
# ============================================================================

@dataclass
class MidiEvent:
    """MIDI event with sample position."""
    sample_pos: int  # Position in samples from start of bar
    note: int
    velocity: int
    channel: int
    is_note_on: bool  # True for note_on, False for note_off


class MidiOutput:
    """MIDI output handler for IAC Driver Bus 1."""

    def __init__(self, port_name: str = "IAC Driver Bus 1"):
        self.port = None
        self.port_name = port_name
        if not MIDI_AVAILABLE:
            return

        try:
            # Try to open the specified port
            self.port = mido.open_output(port_name)
            print(f"MIDI output connected to: {port_name}", file=sys.stderr)
        except (OSError, IOError) as e:
            print(f"Warning: Could not open MIDI port '{port_name}': {e}", file=sys.stderr)
            print("Available MIDI ports:", file=sys.stderr)
            try:
                for name in mido.get_output_names():
                    print(f"  - {name}", file=sys.stderr)
            except:
                pass
            self.port = None

    def send_note_on(self, note: int, velocity: int = 64, channel: int = 0):
        """Send MIDI Note On message."""
        if self.port:
            try:
                msg = mido.Message('note_on', note=note, velocity=velocity, channel=channel)
                self.port.send(msg)
            except Exception as e:
                print(f"MIDI send error: {e}", file=sys.stderr)

    def send_note_off(self, note: int, velocity: int = 64, channel: int = 0):
        """Send MIDI Note Off message."""
        if self.port:
            try:
                msg = mido.Message('note_off', note=note, velocity=velocity, channel=channel)
                self.port.send(msg)
            except Exception as e:
                print(f"MIDI send error: {e}", file=sys.stderr)

    def close(self):
        """Close MIDI port."""
        if self.port:
            try:
                self.port.close()
            except:
                pass
            self.port = None


# ============================================================================
# Instrument Voices
# ============================================================================

class LeadSynth:
    """Jazz lead synth - smooth, expressive."""

    def __init__(self):
        self.osc = Oscillator()
        self.last_note = 60

    def play_note(self, midi_note: int, duration: float, state: DirectorState, sample_offset: int = 0) -> Tuple[np.ndarray, List[MidiEvent]]:
        freq = midi_to_freq(midi_note)

        # Mix of triangle and sine for warm jazz tone
        tri = self.osc.triangle(freq, duration, 0.4)
        sine = self.osc.sine(freq, duration, 0.3)

        # Add subtle vibrato
        t = np.linspace(0, duration, len(tri), False)
        vibrato = 1 + 0.003 * np.sin(2 * np.pi * 5 * t)

        signal = (tri + sine) * vibrato

        # Envelope based on character
        if state.character == "staccato":
            env = adsr_envelope(duration, 0.005, 0.05, 0.3, 0.05)
        elif state.character == "flowing":
            env = adsr_envelope(duration, 0.1, 0.2, 0.8, 0.2)
        else:
            env = adsr_envelope(duration, 0.02, 0.1, 0.6, 0.1)

        signal = signal[:len(env)] * env

        # Lowpass for warmth
        signal = lowpass_filter(signal, 3000 + 2000 * state.intensity)

        # Create MIDI events
        velocity = int(64 + 63 * state.intensity)
        note_on_sample = sample_offset
        note_off_sample = sample_offset + int(duration * SAMPLE_RATE)
        midi_events = [
            MidiEvent(note_on_sample, midi_note, velocity, 0, True),
            MidiEvent(note_off_sample, midi_note, velocity, 0, False)
        ]

        self.last_note = midi_note
        return signal * state.intensity * 0.5, midi_events


class RhythmSynth:
    """Jazz chord rhythm section - Rhodes-like."""

    def __init__(self):
        self.osc = Oscillator()

    def play_chord(self, root: int, chord_type: str, duration: float,
                   state: DirectorState, sample_offset: int = 0) -> Tuple[np.ndarray, List[MidiEvent]]:
        intervals = CHORDS.get(chord_type, CHORDS["dom7"])

        # Voice the chord in a jazzy way (spread voicing)
        notes = [root - 12]  # Root in bass
        for i, interval in enumerate(intervals[1:], 1):
            octave_shift = 12 if i > 2 else 0  # Spread upper notes
            notes.append(root + interval + octave_shift)

        # Mix signals
        signal = np.zeros(int(SAMPLE_RATE * duration))

        for note in notes:
            freq = midi_to_freq(note)
            # Rhodes-like: sine with harmonic
            sine = self.osc.sine(freq, duration, 0.15)
            harm = self.osc.sine(freq * 2, duration, 0.05)

            note_signal = sine + harm
            if len(note_signal) <= len(signal):
                signal[:len(note_signal)] += note_signal

        # Tremolo for Rhodes effect
        t = np.linspace(0, duration, len(signal), False)
        tremolo = 1 + 0.1 * np.sin(2 * np.pi * 4 * t)
        signal = signal * tremolo

        # Soft envelope
        env = adsr_envelope(duration, 0.01, 0.2, 0.5, 0.3)
        signal = signal[:len(env)] * env

        # Create MIDI events for chord
        velocity = int(64 + 63 * state.intensity)
        note_on_sample = sample_offset
        note_off_sample = sample_offset + int(duration * SAMPLE_RATE)
        midi_events = []
        for note in notes:
            midi_events.append(MidiEvent(note_on_sample, note, velocity, 1, True))
            midi_events.append(MidiEvent(note_off_sample, note, velocity, 1, False))

        return signal * state.intensity * 0.4, midi_events


class BassSynth:
    """DnB sub-bass with jazzy notes."""

    def __init__(self):
        self.osc = Oscillator()

    def play_note(self, midi_note: int, duration: float, state: DirectorState, sample_offset: int = 0) -> Tuple[np.ndarray, List[MidiEvent]]:
        # Sub-bass: one octave down
        freq = midi_to_freq(midi_note - 12)

        # Mix sine (sub) with saw (grit)
        sub = self.osc.sine(freq, duration, 0.6)
        grit = self.osc.saw(freq * 2, duration, 0.15)

        signal = sub + grit

        # Tight envelope for DnB punch
        env = adsr_envelope(duration, 0.005, 0.1, 0.4, 0.1)
        signal = signal[:len(env)] * env

        # Heavy lowpass
        signal = lowpass_filter(signal, 200 + 100 * state.intensity)

        # Create MIDI events (use the original note, not the transposed one)
        velocity = int(64 + 63 * state.intensity)
        note_on_sample = sample_offset
        note_off_sample = sample_offset + int(duration * SAMPLE_RATE)
        midi_events = [
            MidiEvent(note_on_sample, midi_note, velocity, 2, True),
            MidiEvent(note_off_sample, midi_note, velocity, 2, False)
        ]

        return signal * state.intensity * 0.7, midi_events


class DrumSynth:
    """DnB drum machine - breakbeat style."""

    def __init__(self):
        self.osc = Oscillator()

    def kick(self, duration: float = 0.15, sample_offset: int = 0) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Punchy DnB kick."""
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, False)

        # Pitch envelope: starts high, drops quickly
        pitch_env = 150 * np.exp(-30 * t) + 50

        # Generate with pitch envelope
        phase = np.cumsum(2 * np.pi * pitch_env / SAMPLE_RATE)
        signal = 0.8 * np.sin(phase)

        # Amplitude envelope
        amp_env = np.exp(-8 * t)
        signal = signal * amp_env

        # Create MIDI events (kick = MIDI note 36, C1)
        velocity = 100
        note_on_sample = sample_offset
        note_off_sample = sample_offset + int(duration * SAMPLE_RATE)
        midi_events = [
            MidiEvent(note_on_sample, 36, velocity, 3, True),
            MidiEvent(note_off_sample, 36, velocity, 3, False)
        ]

        return signal, midi_events

    def snare(self, duration: float = 0.15, sample_offset: int = 0) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Punchy DnB snare with noise."""
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, False)

        # Tone component
        tone = 0.3 * np.sin(2 * np.pi * 200 * t) * np.exp(-20 * t)

        # Noise component
        noise = self.osc.noise(duration, 0.4)
        noise_env = np.exp(-15 * t)
        noise = noise * noise_env

        # Highpass the noise
        noise = highpass_filter(noise, 2000)

        # Create MIDI events (snare = MIDI note 38, D1)
        velocity = 100
        note_on_sample = sample_offset
        note_off_sample = sample_offset + int(duration * SAMPLE_RATE)
        midi_events = [
            MidiEvent(note_on_sample, 38, velocity, 3, True),
            MidiEvent(note_off_sample, 38, velocity, 3, False)
        ]

        return tone + noise, midi_events

    def hihat(self, duration: float = 0.05, open: bool = False, sample_offset: int = 0) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Hi-hat - closed or open."""
        dur = duration * (3 if open else 1)
        samples = int(SAMPLE_RATE * dur)
        t = np.linspace(0, dur, samples, False)

        # Filtered noise
        noise = self.osc.noise(dur, 0.3)
        noise = highpass_filter(noise, 7000)

        # Envelope
        decay = 5 if open else 30
        env = np.exp(-decay * t)

        # Create MIDI events (hi-hat closed = 42/F#1, open = 46/A#1)
        velocity = 80
        note = 46 if open else 42
        note_on_sample = sample_offset
        note_off_sample = sample_offset + int(dur * SAMPLE_RATE)
        midi_events = [
            MidiEvent(note_on_sample, note, velocity, 3, True),
            MidiEvent(note_off_sample, note, velocity, 3, False)
        ]

        return noise * env, midi_events


# ============================================================================
# Pattern Generators
# ============================================================================

class PatternGenerator:
    """Generates musical patterns based on director state."""

    def __init__(self, state: DirectorState):
        self.state = state
        self.bar_count = 0
        self.lead = LeadSynth()
        self.rhythm = RhythmSynth()
        self.bass = BassSynth()
        self.drums = DrumSynth()

    def get_scale_notes(self, octave_range: int = 2) -> list:
        """Get available notes from current scale."""
        scale = SCALES.get(self.state.scale, SCALES["mixolydian"])
        notes = []
        for octave in range(-1, octave_range):
            for interval in scale:
                notes.append(self.state.root_note + interval + octave * 12)
        return notes

    def generate_lead_phrase(self, duration: float) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Generate a melodic phrase."""
        samples = int(SAMPLE_RATE * duration)
        signal = np.zeros(samples)
        midi_events = []

        scale_notes = self.get_scale_notes()

        # Determine number of notes based on density
        num_notes = max(1, int(4 * self.state.density * self.state.tempo_mult))
        note_duration = duration / num_notes

        current_note = self.lead.last_note

        for i in range(num_notes):
            # Random walk through scale with occasional leaps
            if np.random.random() < 0.7:
                # Step motion
                step = np.random.choice([-1, 0, 1, 2])
                current_idx = min(range(len(scale_notes)),
                                  key=lambda x: abs(scale_notes[x] - current_note))
                new_idx = max(0, min(len(scale_notes) - 1, current_idx + step))
                note = scale_notes[new_idx]
            else:
                # Leap
                note = np.random.choice(scale_notes)

            # Rest probability based on density
            if np.random.random() > self.state.density:
                continue

            start = int(i * note_duration * SAMPLE_RATE)
            note_signal, events = self.lead.play_note(note, note_duration * 0.9, self.state, start)
            midi_events.extend(events)
            end = min(start + len(note_signal), samples)
            signal[start:end] += note_signal[:end - start]

            current_note = note

        return signal, midi_events

    def generate_rhythm_pattern(self, duration: float) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Generate chord rhythm pattern."""
        samples = int(SAMPLE_RATE * duration)
        signal = np.zeros(samples)
        midi_events = []

        # Jazz comping pattern - syncopated hits
        beat_samples = int(SAMPLE_RATE * BEAT_DURATION / self.state.tempo_mult)

        # Typical jazz chord rhythm: hit on 2 and 4, sometimes 1-and
        pattern = [0, 0.5, 1.5, 2, 3, 3.5]  # Beat positions

        for beat_pos in pattern:
            if np.random.random() > self.state.density:
                continue

            start = int(beat_pos * beat_samples)
            if start >= samples:
                continue

            chord_dur = BEAT_DURATION * (0.3 + 0.3 * np.random.random())
            chord, events = self.rhythm.play_chord(
                self.state.root_note,
                self.state.chord_type,
                chord_dur,
                self.state,
                start
            )
            midi_events.extend(events)

            end = min(start + len(chord), samples)
            signal[start:end] += chord[:end - start]

        return signal, midi_events

    def generate_bass_pattern(self, duration: float) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Generate DnB bass pattern."""
        samples = int(SAMPLE_RATE * duration)
        signal = np.zeros(samples)
        midi_events = []

        beat_samples = int(SAMPLE_RATE * BEAT_DURATION / self.state.tempo_mult)

        # DnB bass pattern: root, fifth, octave variations
        root = self.state.root_note
        fifth = root + 7

        # Classic DnB: syncopated bass hits
        pattern = [
            (0, root, 0.2),
            (1.5, fifth, 0.15),
            (2.5, root, 0.2),
            (3, fifth, 0.1),
        ]

        for beat_pos, note, dur in pattern:
            if np.random.random() > self.state.density + 0.3:
                continue

            start = int(beat_pos * beat_samples)
            if start >= samples:
                continue

            bass_note, events = self.bass.play_note(note, dur, self.state, start)
            midi_events.extend(events)
            end = min(start + len(bass_note), samples)
            signal[start:end] += bass_note[:end - start]

        return signal, midi_events

    def generate_drum_pattern(self, duration: float) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Generate DnB breakbeat pattern."""
        samples = int(SAMPLE_RATE * duration)
        signal = np.zeros(samples)
        midi_events = []

        beat_samples = int(SAMPLE_RATE * BEAT_DURATION / self.state.tempo_mult)
        sixteenth = beat_samples // 4

        # Classic DnB pattern (Amen-style)
        # Kick: 1, 2.75, 3.5
        # Snare: 1.5, 3, (ghost notes)
        # Hi-hats: 8ths and 16ths

        kick_pattern = [0, 2.75, 3.5]
        snare_pattern = [1, 3]

        # Add kicks
        for beat_pos in kick_pattern:
            start = int(beat_pos * beat_samples)
            if start >= samples:
                continue
            kick, events = self.drums.kick(sample_offset=start)
            midi_events.extend(events)
            end = min(start + len(kick), samples)
            signal[start:end] += kick[:end - start] * self.state.intensity

        # Add snares
        for beat_pos in snare_pattern:
            start = int(beat_pos * beat_samples)
            if start >= samples:
                continue
            snare, events = self.drums.snare(sample_offset=start)
            midi_events.extend(events)
            end = min(start + len(snare), samples)
            signal[start:end] += snare[:end - start] * self.state.intensity

        # Add hi-hats based on density
        for i in range(int(duration / (BEAT_DURATION / 2))):
            if np.random.random() > self.state.density + 0.2:
                continue

            start = int(i * beat_samples / 2)
            if start >= samples:
                continue

            is_open = np.random.random() < 0.1
            hh, events = self.drums.hihat(open=is_open, sample_offset=start)
            midi_events.extend(events)
            end = min(start + len(hh), samples)
            signal[start:end] += hh[:end - start] * self.state.intensity * 0.7

        return signal, midi_events

    def generate_bar(self) -> Tuple[np.ndarray, List[MidiEvent]]:
        """Generate one bar of music with all channels."""
        duration = BAR_DURATION / self.state.tempo_mult

        # Generate each channel
        lead_signal, lead_events = self.generate_lead_phrase(duration)
        rhythm_signal, rhythm_events = self.generate_rhythm_pattern(duration)
        bass_signal, bass_events = self.generate_bass_pattern(duration)
        drums_signal, drums_events = self.generate_drum_pattern(duration)

        # Collect all MIDI events
        all_midi_events = lead_events + rhythm_events + bass_events + drums_events

        # Ensure all same length
        max_len = max(len(lead_signal), len(rhythm_signal), len(bass_signal), len(drums_signal))

        def pad(arr):
            if len(arr) < max_len:
                return np.pad(arr, (0, max_len - len(arr)))
            return arr[:max_len]

        # Mix channels
        mix = pad(lead_signal) + pad(rhythm_signal) + pad(bass_signal) + pad(drums_signal)

        # Soft clip / tanh saturation
        mix = np.tanh(mix * 0.8) * 0.9

        self.bar_count += 1
        return mix, all_midi_events


# ============================================================================
# Score Logger
# ============================================================================

class ScoreLogger:
    """Logs musical events to stdout (for tee to capture)."""

    def __init__(self):
        self.start_time = time.time()

    def log_state(self, state: DirectorState, bar_num: int):
        """Log current musical state."""
        elapsed = time.time() - self.start_time
        print(f"[{elapsed:7.2f}s] Bar {bar_num:4d} | "
              f"root={state.root_note:2d} chord={state.chord_type:6s} "
              f"scale={state.scale:12s} | "
              f"density={state.density:.2f} intensity={state.intensity:.2f} "
              f"tempo_mult={state.tempo_mult:.2f}",
              flush=True)


# ============================================================================
# Audio Engine
# ============================================================================

class AudioEngine:
    """Real-time audio playback and recording."""

    def __init__(self, record_path: Optional[str] = None):
        self.buffer = queue.Queue(maxsize=10)
        self.running = False
        self.record_path = record_path
        self.recorded_audio = []
        self.stream = None

    def audio_callback(self, outdata, frames, time_info, status):
        """Sounddevice callback for audio output."""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)

        try:
            data = self.buffer.get_nowait()
            # Ensure correct length
            if len(data) < frames:
                data = np.pad(data, (0, frames - len(data)))
            outdata[:, 0] = data[:frames]

            # Record if enabled
            if self.record_path:
                self.recorded_audio.append(data[:frames].copy())

        except queue.Empty:
            outdata.fill(0)

    def start(self):
        """Start audio output stream."""
        self.running = True
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            callback=self.audio_callback,
            blocksize=2048
        )
        self.stream.start()
        print("Audio engine started", file=sys.stderr)

    def stop(self):
        """Stop audio and save recording."""
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()

        if self.record_path and self.recorded_audio:
            self.save_recording()

    def queue_audio(self, samples: np.ndarray, midi_events: List[MidiEvent] = None, midi_output: Optional[MidiOutput] = None):
        """Queue audio samples for playback and send MIDI events at the correct timing."""
        # Sort MIDI events by sample position
        sorted_events = []
        if midi_events and midi_output and midi_output.port:
            sorted_events = sorted(midi_events, key=lambda e: e.sample_pos)
        
        # Split into chunks for smooth playback
        chunk_size = 2048
        current_sample = 0
        event_index = 0  # Track which events we've already sent
        
        for i in range(0, len(samples), chunk_size):
            chunk_start = current_sample
            chunk_end = current_sample + chunk_size
            
            # Send MIDI events that occur in this chunk
            if sorted_events and midi_output and midi_output.port:
                while event_index < len(sorted_events):
                    event = sorted_events[event_index]
                    if event.sample_pos >= chunk_end:
                        break  # Event is in a future chunk
                    if chunk_start <= event.sample_pos < chunk_end:
                        if event.is_note_on:
                            midi_output.send_note_on(event.note, event.velocity, event.channel)
                        else:
                            midi_output.send_note_off(event.note, event.velocity, event.channel)
                    event_index += 1
            
            chunk = samples[i:i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            try:
                self.buffer.put(chunk.astype(np.float32), timeout=0.5)
            except queue.Full:
                pass  # Drop if buffer full
            
            current_sample += chunk_size
            
            current_sample += chunk_size

    def save_recording(self):
        """Save recorded audio to MP3."""
        print(f"\nSaving recording to {self.record_path}...", file=sys.stderr)

        # Concatenate all recorded audio
        audio = np.concatenate(self.recorded_audio)

        # Normalize
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.95

        # Convert to 16-bit PCM
        audio_int = (audio * 32767).astype(np.int16)

        # Write WAV first, then convert to MP3
        wav_path = self.record_path.replace('.mp3', '.wav')

        try:
            import wave
            with wave.open(wav_path, 'w') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(audio_int.tobytes())

            # Convert to MP3 using ffmpeg
            result = subprocess.run([
                'ffmpeg', '-y', '-i', wav_path,
                '-codec:a', 'libmp3lame',
                '-q:a', '0',  # VBR quality 0 = best (~320kbps)
                self.record_path
            ], capture_output=True, text=True)

            if result.returncode == 0:
                os.remove(wav_path)  # Clean up WAV
                print(f"Recording saved: {self.record_path}", file=sys.stderr)
            else:
                print(f"FFmpeg error: {result.stderr}", file=sys.stderr)
                print(f"WAV file kept at: {wav_path}", file=sys.stderr)

        except Exception as e:
            print(f"Error saving recording: {e}", file=sys.stderr)


# ============================================================================
# Input Parser
# ============================================================================

class DirectorParser:
    """Parses director output from stdin."""

    def __init__(self):
        self.current_frame = {}
        self.expected_keys = ['color', 'mood', 'person', 'object', 'energy']

    def parse_line(self, line: str) -> Optional[dict]:
        """Parse a line of director output. Returns complete frame when ready."""
        line = line.strip()
        if not line or line.startswith(('=', '-', 'Pete', 'Model', 'Loading',
                                        'Press', 'Resolution', 'Max', 'Target',
                                        'Prompt', 'Camera', 'Starting', 'Fetching')):
            return None

        # Try to parse key: value format
        match = re.match(r'(\w+):\s*(\w+)', line)
        if match:
            key, value = match.groups()
            key = key.lower()
            value = value.lower()

            if key in self.expected_keys:
                self.current_frame[key] = value

                # Check if frame is complete
                if len(self.current_frame) >= 4:  # Allow for missing energy
                    frame = self.current_frame.copy()
                    self.current_frame = {}
                    return frame

        return None


# ============================================================================
# Main
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Composer: Real-time soundtrack generator from director cues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage with director
    python3 pete_sounds.py | python3 composer.py

    # With score logging
    python3 pete_sounds.py | python3 composer.py | tee score.txt

    # With MP3 recording
    python3 pete_sounds.py | python3 composer.py --record output.mp3 | tee score.txt

Press Ctrl-C to exit.
        """
    )
    parser.add_argument(
        '--record', '-r',
        type=str,
        default=None,
        help='Path to output MP3 file for recording'
    )
    parser.add_argument(
        '--bpm',
        type=int,
        default=BPM,
        help=f'Base tempo in BPM (default: {BPM})'
    )
    parser.add_argument(
        '--no-audio',
        action='store_true',
        help='Disable audio playback (score output only)'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    global BPM, BEAT_DURATION, BAR_DURATION
    BPM = args.bpm
    BEAT_DURATION = 60.0 / BPM
    BAR_DURATION = BEAT_DURATION * 4

    print("=" * 60, file=sys.stderr)
    print("Composer: Jazz-over-DnB Soundtrack Generator", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"BPM: {BPM}", file=sys.stderr)
    print(f"Recording: {args.record or 'disabled'}", file=sys.stderr)
    print("Waiting for director input on stdin...", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)

    # Initialize MIDI output
    midi_output = None
    if MIDI_AVAILABLE:
        midi = MidiOutput("IAC Driver Bus 1")
        # Only use MIDI output if port was successfully opened
        if midi.port is not None:
            midi_output = midi
            print(f"MIDI output enabled: port={midi.port_name}", file=sys.stderr)
        else:
            print("MIDI output disabled: port could not be opened", file=sys.stderr)
    else:
        print("MIDI output disabled: mido not available", file=sys.stderr)

    # Initialize components
    state = DirectorState()
    pattern_gen = PatternGenerator(state)
    parser = DirectorParser()
    score_log = ScoreLogger()

    # Initialize audio engine
    audio = None
    if not args.no_audio:
        audio = AudioEngine(record_path=args.record)
        audio.start()

    # Signal handler for clean shutdown
    def shutdown(signum, frame):
        print("\n\nShutting down composer...", file=sys.stderr)
        if audio:
            audio.stop()
        if midi_output:
            midi_output.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    bar_count = 0
    last_bar_time = time.time()

    try:
        # Set stdin to non-blocking mode
        import select

        while True:
            # Check for input
            if select.select([sys.stdin], [], [], 0.01)[0]:
                line = sys.stdin.readline()
                if not line:
                    break

                frame = parser.parse_line(line)
                if frame:
                    # Update state with new director cues
                    state.update(
                        color=frame.get('color', state.color),
                        mood=frame.get('mood', state.mood),
                        person=frame.get('person', state.person),
                        obj=frame.get('object', state.obj),
                        energy=frame.get('energy', state.energy)
                    )

            # Generate music at bar intervals
            current_time = time.time()
            bar_duration = BAR_DURATION / state.tempo_mult

            if current_time - last_bar_time >= bar_duration:
                last_bar_time = current_time
                bar_count += 1

                # Generate and play bar
                bar_audio, bar_midi_events = pattern_gen.generate_bar()

                if audio:
                    audio.queue_audio(bar_audio, bar_midi_events, midi_output)

                # Log to score output
                score_log.log_state(state, bar_count)

    except KeyboardInterrupt:
        pass
    finally:
        if audio:
            audio.stop()
        if midi_output:
            midi_output.close()
        print("\nComposer terminated.", file=sys.stderr)


if __name__ == "__main__":
    main()
