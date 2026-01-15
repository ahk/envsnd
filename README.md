Project Structure                                                                                                  
                                                                                                                     
  pete-sounds/                                                                                                       
  ├── install.sh        # FastVLM installation for M4 Pro                                                            
  ├── pete_sounds.py    # Webcam inference program                                                                   
  ├── DIRECTOR.md       # Prompt configuration                                                                       
  └── PLANNING.md       # Project planning document                                                                  
                                                                                                                     
  Model Choice                                                                                                       
                                                                                                                     
  Selected FastVLM-0.5B-fp16 from https://huggingface.co/collections/apple/fastvlm:                                  
  - 85x faster TTFT than comparable models                                                                           
  - FP16 precision (your 48GB RAM allows full precision without quantization penalty)                                
  - FastViTHD encoder outputs fewer tokens for lower latency                                                         
                                                                                                                     
  Usage                                                                                                              
                                                                                                                     
  cd pete-sounds                                                                                                     
  ./install.sh                    # Install dependencies & download model                                            
  source venv/bin/activate                                                                                           
  python3 pete_sounds.py          # Run with defaults                                                                
  python3 pete_sounds.py --help   # See all options                                                                  
                                                                                                                     
  Latency Tuning                                                                                                     
                                                                                                                     
  For lowest TBT latency, try:                                                                                       
  python3 pete_sounds.py --resolution 64 --max-tokens 20 --fps 1                                                     
                                                                                                                     
  The program outputs director cues to stdout in the format specified in DIRECTOR.md (e.g., color: blue, mood: calm).
                                                                                                                     
  Sources:                                                                                                           
  - https://github.com/apple/ml-fastvlm                                                                              
  - https://github.com/Blaizzy/mlx-vlm                                                                               
  - https://huggingface.co/collections/apple/fastvlm     