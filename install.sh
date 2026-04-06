#!/bin/bash
echo "============================================================"
echo "  Transient Marker Maker - macOS Installer"
echo "============================================================"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install numpy scipy soundfile demucs
echo ""

# Detect Apple Silicon vs Intel
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    echo "Detected Apple Silicon — installing PyTorch with MPS support..."
    pip3 install torch torchaudio
else
    echo "Detected Intel Mac — installing PyTorch (CPU)..."
    pip3 install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
fi
echo ""

# Copy script to Resolve's Scripts folder
RESOLVE_SCRIPTS="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
echo "Installing script to Resolve..."
echo "  Target: $RESOLVE_SCRIPTS"

mkdir -p "$RESOLVE_SCRIPTS"
cp "Transient Marker Maker.py" "$RESOLVE_SCRIPTS/Transient Marker Maker.py"
echo "  Script copied."

echo ""
echo "============================================================"
echo "  Installation complete!"
echo ""
echo "  1. Open DaVinci Resolve"
echo "  2. Go to: Preferences > General"
echo "  3. Set 'External scripting using' to 'Local'"
echo "  4. Restart Resolve"
echo "  5. Find it at: Workspace > Scripts > Transient Marker Maker"
echo "============================================================"
echo ""
