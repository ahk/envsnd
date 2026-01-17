#!/usr/bin/env python3
"""Standalone MIDI test - tests MIDI output without importing composer."""

import sys
import time

# Test if mido is available
try:
    import mido
    print("✓ mido is installed")
    print(f"\nAvailable MIDI output ports:")
    ports = mido.get_output_names()
    for port in ports:
        marker = " ← TARGET" if port == "IAC Driver Bus 1" else ""
        print(f"  - {port}{marker}")
    
    if "IAC Driver Bus 1" in ports:
        print("\n✓ 'IAC Driver Bus 1' is available!")
    else:
        print("\n⚠ 'IAC Driver Bus 1' not found in available ports")
        print("   Make sure IAC Driver is enabled in Audio MIDI Setup")
        sys.exit(1)
    
except ImportError:
    print("✗ mido is NOT installed")
    print("   Install with: pip install mido")
    sys.exit(1)

# Test creating and using a MIDI output (similar to composer's MidiOutput class)
print("\n" + "="*60)
print("Testing MIDI Output to 'IAC Driver Bus 1'...")
print("="*60)

try:
    print("\n1. Opening MIDI port...")
    port = mido.open_output("IAC Driver Bus 1")
    print("   ✓ Port opened successfully!")
    
    print("\n2. Sending test notes...")
    
    # Test note: C4 (MIDI note 60)
    test_note = 60
    velocity = 100
    channel = 0
    
    print(f"   Sending Note On:  note={test_note} (C4), velocity={velocity}, channel={channel}")
    msg_on = mido.Message('note_on', note=test_note, velocity=velocity, channel=channel)
    port.send(msg_on)
    print("   ✓ Note On sent")
    
    time.sleep(0.5)
    
    print(f"   Sending Note Off: note={test_note} (C4), velocity={velocity}, channel={channel}")
    msg_off = mido.Message('note_off', note=test_note, velocity=velocity, channel=channel)
    port.send(msg_off)
    print("   ✓ Note Off sent")
    
    # Test a chord (like RhythmSynth does)
    print("\n3. Testing chord (multiple notes like RhythmSynth)...")
    chord_notes = [48, 52, 55, 59]  # C major chord (C3, E3, G3, B3)
    print(f"   Sending chord: {chord_notes}")
    for note in chord_notes:
        msg = mido.Message('note_on', note=note, velocity=80, channel=1)
        port.send(msg)
        print(f"     ✓ Note {note} On (channel 1)")
    
    time.sleep(0.3)
    
    for note in chord_notes:
        msg = mido.Message('note_off', note=note, velocity=80, channel=1)
        port.send(msg)
    
    print("   ✓ Chord Note Offs sent")
    
    print("\n4. Closing MIDI port...")
    port.close()
    print("   ✓ Port closed")
    
    print("\n" + "="*60)
    print("✓ MIDI test completed successfully!")
    print("="*60)
    print("\nIf you have a MIDI device or DAW listening to 'IAC Driver Bus 1',")
    print("you should have heard the test notes!")
    
except Exception as e:
    print(f"\n✗ Error during test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
