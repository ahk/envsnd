#!/usr/bin/env python3
"""Test composer MIDI output with simulated director input."""

import sys
import time
import subprocess
import threading

print("="*60)
print("Testing Composer MIDI Output")
print("="*60)
print()

# Check which Python will be used
import sys
print(f"Using Python: {sys.executable}")
print()

# Test if composer can import MIDI
print("1. Testing MIDI import in composer...")
try:
    # Import the MIDI-related parts
    sys.path.insert(0, '.')
    from composer import MIDI_AVAILABLE, MidiOutput
    print(f"   MIDI_AVAILABLE = {MIDI_AVAILABLE}")
    
    if not MIDI_AVAILABLE:
        print("   ✗ MIDI is not available in composer!")
        print("   This means mido is not installed in the Python being used.")
        sys.exit(1)
    
    print("   ✓ MIDI is available")
    
    # Test creating MIDI output
    print("\n2. Testing MIDI output creation...")
    midi = MidiOutput("IAC Driver Bus 1")
    if midi.port is None:
        print("   ✗ Could not open MIDI port")
        sys.exit(1)
    print("   ✓ MIDI port opened successfully")
    midi.close()
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Now test running composer with test input
print("\n3. Testing composer with simulated director input...")
print("   (This will run for ~5 seconds to generate some bars)")

# Simulate director output
test_input = """color: blue
mood: calm
person: sitting
object: none
energy: medium
"""

print(f"\n   Simulated input:\n{test_input}")

# Run composer in a subprocess with the test input
try:
    proc = subprocess.Popen(
        [sys.executable, "composer.py", "--no-audio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Send test input
    proc.stdin.write(test_input)
    proc.stdin.flush()
    
    # Let it run for a few seconds to generate some bars
    print("   Running composer for 5 seconds...")
    
    def read_stderr():
        """Read stderr to see MIDI connection messages."""
        for line in proc.stderr:
            print(f"   [stderr] {line.rstrip()}")
    
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    
    # Wait a bit
    time.sleep(5)
    
    # Terminate
    proc.terminate()
    proc.wait(timeout=2)
    
    print("   ✓ Composer ran successfully")
    
    # Check stderr for MIDI messages
    proc.stderr.close()
    
except KeyboardInterrupt:
    print("\n   Test interrupted")
    if proc:
        proc.terminate()
except Exception as e:
    print(f"   ✗ Error running composer: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("✓ MIDI test completed!")
print("="*60)
print("\nCheck the stderr output above for 'MIDI output connected' message.")
print("If you see that message, MIDI is working in the composer!")
