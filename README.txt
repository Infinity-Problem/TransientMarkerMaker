============================================================
  TRANSIENT MARKER MAKER
  for DaVinci Resolve
============================================================

Automatically separates drums from any audio file, detects
kick and snare hits, and places colored markers directly on
clips in your DaVinci Resolve timeline.

  Red markers  = Kick
  Blue markers = Snare
  (colors are configurable)

Supports Windows and macOS.


REQUIREMENTS
------------------------------------------------------------
- DaVinci Resolve 18+ (Free or Studio)
- Python 3.10 or newer
- NVIDIA GPU recommended on Windows (runs on CPU too)
- Apple Silicon Macs run Demucs natively on the GPU


============================================================
  WINDOWS INSTALL
============================================================

1. INSTALL PYTHON DEPENDENCIES

   Open Command Prompt and run:

   pip install numpy scipy soundfile demucs

   If you have an NVIDIA GPU (recommended):
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

   If no GPU:
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu


2. ENABLE RESOLVE SCRIPTING

   DaVinci Resolve > Preferences > General >
   "External scripting using" > Local
   Restart Resolve.


3. INSTALL THE SCRIPT

   Copy "Transient Marker Maker.py" to:

   %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\

   Full path example:
   C:\Users\YourName\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\Transient Marker Maker.py

   If the "Utility" folder doesn't exist, create it.

   Or just double-click install.bat to do this automatically.


============================================================
  macOS INSTALL
============================================================

1. INSTALL PYTHON (if not already)

   Open Terminal and run:

   brew install python

   Or download from https://www.python.org/downloads/


2. INSTALL PYTHON DEPENDENCIES

   Open Terminal and run:

   pip3 install numpy scipy soundfile demucs

   For Apple Silicon Macs (M1/M2/M3/M4):
   pip3 install torch torchaudio

   For Intel Macs:
   pip3 install torch torchaudio --index-url https://download.pytorch.org/whl/cpu


3. ENABLE RESOLVE SCRIPTING

   DaVinci Resolve > Preferences > General >
   "External scripting using" > Local
   Restart Resolve.


4. INSTALL THE SCRIPT

   Copy "Transient Marker Maker.py" to:

   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/

   Terminal command:

   mkdir -p ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Scripts/Utility/
   cp "Transient Marker Maker.py" ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Scripts/Utility/

   Or run the install script:

   chmod +x install.sh
   ./install.sh


============================================================
  USAGE
============================================================

OPTION A: From inside Resolve (recommended)

   Workspace > Scripts > Transient Marker Maker

   A UI panel will open with:
   - File picker (Browse for your audio file)
   - Kick sensitivity slider + color picker
   - Snare sensitivity slider + color picker
   - Min gap control
   - Analyze & Place Markers button
   - Clear Markers button


OPTION B: From terminal/command prompt

   Windows:
   cd C:\path\to\TransientMarkerMaker
   python "Transient Marker Maker.py"

   macOS:
   cd /path/to/TransientMarkerMaker
   python3 "Transient Marker Maker.py"

   A standalone window opens with the same controls.
   Resolve must be running in the background.


HOW IT WORKS
------------------------------------------------------------
1. Demucs (by Meta) separates the drum stem from the mix
2. The drum stem is split into frequency bands:
   - Kick:  20-120 Hz
   - Snare: 200-5000 Hz
3. Energy-based onset detection finds transient peaks
4. Overlapping kick/snare hits are deduplicated
5. Markers are placed on the matching clip in Resolve


SENSITIVITY
------------------------------------------------------------
- Lower value (toward 0) = more markers (catches quieter hits)
- Higher value (toward 1) = fewer markers (only prominent hits)
- Default: 0.55 for both kick and snare
- Start at 0.55 and adjust from there


TIPS
------------------------------------------------------------
- The audio file you analyze must also exist as a clip on
  your currently active timeline. The script matches by
  filename.

- First run of Demucs downloads the model (~80 MB). After
  that it's cached and runs faster.

- With an NVIDIA GPU (e.g. 4090), Demucs takes ~10-30
  seconds. On CPU or Apple Silicon, ~30-90 seconds.

- Min Gap prevents markers from bunching up. Default is
  100ms. Raise it for sparser markers.

- Clear Markers removes all Kick and Snare markers from
  every audio clip on the current timeline.


TROUBLESHOOTING
------------------------------------------------------------
"Could not import DaVinciResolveScript"
  > Make sure Resolve is running with scripting set to Local.

"Entry point torch_library_impl not found" (Windows)
  > Reinstall torch:
    pip uninstall torch torchaudio -y
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

"No clip matching 'filename'"
  > The audio file must be on the active timeline. Check
    that the clip name matches the filename.

Script doesn't appear in Workspace > Scripts
  Windows:
  > Check: %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\
  macOS:
  > Check: ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/
  > Restart Resolve after adding the file.

"ModuleNotFoundError: No module named 'demucs'" (macOS)
  > Make sure you used pip3, not pip:
    pip3 install demucs


============================================================
