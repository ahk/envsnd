Project Structure

  pete-sounds/
  ├── pete.py           # Main script: runs full pipeline
  ├── pete_sounds.py    # Director: webcam vision inference
  ├── composer.py       # Composer: real-time soundtrack generator
  ├── install.sh        # Installation script for M4 Pro
  ├── prompts/          # Director prompt configurations
  │   ├── smolvlm2-2.2b.md
  │   ├── smolvlm2-2.2b-strict-output.md
  │   ├── smolvlm2-500m.md
  │   └── smolvlm2-256m.md
  └── PLANNING.md       # Project planning document                                                                  
                                                                                                                     
  Model Choice                                                                                                       
                                                                                                                     
  Selected FastVLM-0.5B-fp16 from https://huggingface.co/collections/apple/fastvlm:                                  
  - 85x faster TTFT than comparable models                                                                           
  - FP16 precision (your 48GB RAM allows full precision without quantization penalty)                                
  - FastViTHD encoder outputs fewer tokens for lower latency                                                         
                                                                                                                     
## Quick Start

```bash
cd pete-sounds
./install.sh                    # Install dependencies & download model
source venv/bin/activate
python3 pete.py                 # Run full pipeline with audio
```

Press `Ctrl-C` to stop gracefully.

## Main Script (pete.py)

The main script orchestrates the full pipeline, interleaving director and composer
output into a unified performance score.

```bash
# Basic usage - audio output only
python3 pete.py

# Record audio to MP3
python3 pete.py --record session.mp3

# Save score to file
python3 pete.py --score performance.txt

# Full session with recording and score
python3 pete.py --record session.mp3 --score session_score.txt

# Use faster model with slower tempo
python3 pete.py --model 500m --bpm 160
```

### Options

```
--record, -r PATH    Record audio to MP3 file
--score, -s PATH     Save interleaved score to file
--model, -m SIZE     Vision model: 256m, 500m, 2.2b (default: 2.2b)
--prompt, -p PATH    Custom prompt file
--bpm N              Composer tempo (default: 174)
--resolution N       Director frame resolution (default: 128)
--max-tokens N       Director max tokens (default: 50)
--no-audio           Disable audio playback
```

### Score Output

The score interleaves director cues and composer state with timestamps:

```
[   5.23s] [DIR] color: blue
[   5.23s] [DIR] mood: calm
[   5.23s] [DIR] person: sitting
[   5.23s] [DIR] object: computer
[   5.54s] [MIX] Bar 4 | root=58 chord=maj7 scale=dorian density=0.30 intensity=0.21
```

- `[DIR]` - Director output (what the vision model sees)
- `[MIX]` - Composer state (what music is being generated)
- `[SYS]` - System messages (startup, shutdown, errors)

## Director Only

To run just the director (vision model) without the composer:

  python3 pete_sounds.py          # Run with defaults
  python3 pete_sounds.py --help   # See all options

### Latency Tuning                                                                                                     
                                                                                                                     
  For lowest TBT latency, try:                                                                                       
  python3 pete_sounds.py --resolution 64 --max-tokens 20 --fps 1                                                     
                                                                                                                     
  The program outputs director cues to stdout in the format specified in DIRECTOR.md (e.g., color: blue, mood: calm).
                                                                                                                     
## Composer

The composer takes director output and generates a real-time jazz-over-DnB soundtrack
with a 4-channel synth ensemble: lead, rhythm, bass, and percussion.

### Basic Usage

```bash
# Director only (outputs cues to stdout)
python3 pete_sounds.py --prompt-file prompts/smolvlm2-2.2b-strict-output.md

# Full pipeline: director | composer (plays audio)
python3 pete_sounds.py --prompt-file prompts/smolvlm2-2.2b-strict-output.md | python3 composer.py

# With score logging
python3 pete_sounds.py ... | python3 composer.py | tee score.txt

# With MP3 recording (320kbps VBR)
python3 pete_sounds.py ... | python3 composer.py --record output.mp3 | tee score.txt
```

Press `Ctrl-C` to stop. The MP3 will be saved on graceful shutdown.

### Composer Options

```
--record, -r PATH   Record audio to MP3 file
--bpm N             Base tempo (default: 174 BPM)
--no-audio          Disable playback, score output only
```

### Director-to-Music Mapping

The composer interprets structured director output and maps it to musical parameters:

| Director Field | Musical Effect |
|----------------|----------------|
| `color` | Root note/key (blue→Bb, green→D, red→A, gray→F, etc.) |
| `mood` | Chord voicing (happy→maj9, sad→min9, serious→min7, calm→maj7) |
| `person` | Rhythm density (sitting→sparse, walking→busy, waving→very active) |
| `object` | Melodic character (computer→staccato, book→flowing, phone→glitchy) |
| `energy` | Tempo & intensity (low→slower/quiet, high→faster/loud) |

### Ensemble Voices

- **Lead**: Triangle + sine oscillators with vibrato, plays melodic phrases from the current scale
- **Rhythm**: Rhodes-style electric piano, plays jazz chord voicings (7ths, 9ths, 11ths, 13ths)
- **Bass**: Sub-bass sine + saw harmonics, syncopated DnB patterns
- **Percussion**: Synthesized DnB breakbeat (kick, snare, hi-hats in Amen-style pattern)

### Score Output Format

The composer logs musical state to stdout (captured by tee):

```
[  12.11s] Bar    8 | root=58 chord=maj9   scale=major   | density=0.50 intensity=0.56 tempo_mult=1.00
```

- `root`: MIDI note number of current key (58=Bb, 53=F, 62=D, etc.)
- `chord`: Current chord type being played
- `scale`: Scale used for lead melodies
- `density`: How busy the rhythm is (0.0-1.0)
- `intensity`: Overall volume/energy (0.0-1.0)
- `tempo_mult`: Tempo multiplier from energy (0.85-1.1)

## Director Prompts

Use `--prompt-file` to select different output formats:

- `prompts/smolvlm2-2.2b-strict-output.md` - Structured key:value output for composer
- `prompts/smolvlm2-2.2b.md` - Prose descriptions
- `prompts/smolvlm2-500m.md` - Simpler prose (faster model)
- `prompts/smolvlm2-256m.md` - Minimal output (fastest model)

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.12+
- Webcam (tested with Logitech Brio)
- ffmpeg (for MP3 encoding): `brew install ffmpeg`

## Sources

- https://github.com/apple/ml-fastvlm
- https://github.com/Blaizzy/mlx-vlm
- https://huggingface.co/collections/apple/fastvlm     