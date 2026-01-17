#!/usr/bin/env python3
"""Quick test script to verify MIDI output functionality."""

import sys
import time

# Test if mido is available
try:
    import mido
    print("✓ mido is installed")
    print(f"Available MIDI output ports:")
    ports = mido.get_output_names()
    for port in ports:
        print(f"  - {port}")
    
    if "IAC Driver Bus 1" in ports:
        print("\n✓ 'IAC Driver Bus 1' is available!")
    else:
        print("\n⚠ 'IAC Driver Bus 1' not found in available ports")
        print("   Make sure IAC Driver is enabled in Audio MIDI Setup")
    
except ImportError:
    print("✗ mido is NOT installed")
    print("   Install with: pip install mido")
    sys.exit(1)

# Test importing the composer's MIDI class
try:
    sys.path.insert(0, '.')
    from composer import MidiOutput, MIDI_AVAILABLE
    
    if not MIDI_AVAILABLE:
        print("\n✗ MIDI_AVAILABLE is False in composer.py")
        sys.exit(1)
    
    print("\n✓ Successfully imported MidiOutput from composer")
    
    # Try to create a MIDI output instance
    print("\nAttempting to connect to 'IAC Driver Bus 1'...")
    midi = MidiOutput("IAC Driver Bus 1")
    
    if midi.port is None:
        print("⚠ MIDI port could not be opened")
        print("   This might be due to system permissions or port not existing")
    else:
        print("✓ MIDI port opened successfully!")
        
        # Test sending a note
        print("\nSending test MIDI note (C4, channel 0)...")
        midi.send_note_on(60, velocity=100, channel=0)
        print("  Note On sent")
        
        time.sleep(0.5)
        
        midi.send_note_off(60, velocity=100, channel=0)
        print("  Note Off sent")
        
        print("\n✓ MIDI test complete!")
        
        midi.close()
        print("✓ MIDI port closed")
    
except Exception as e:
    print(f"\n✗ Error during test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("MIDI test completed successfully!")
print("="*60)
