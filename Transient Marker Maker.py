#!/usr/bin/env python3
"""
Transient Marker Maker — DaVinci Resolve Script
================================================
Launch from: Workspace > Scripts > Transient Marker Maker

This is the Resolve-native launcher. It uses Resolve's built-in
Fusion UI when run from inside Resolve, or falls back to tkinter
when run externally from Command Prompt.
"""

import sys
import os
import tempfile
import subprocess
import threading

# ──────────────────────────────────────────────────────────────
#  RESOLVE API CONNECTION
# ──────────────────────────────────────────────────────────────
def get_resolve():
    search_paths = [
        os.getenv("RESOLVE_SCRIPT_API", ""),
        os.getenv("RESOLVE_SCRIPT_LIB", ""),
    ]

    if sys.platform == "win32":
        search_paths += [
            os.path.join(os.getenv("PROGRAMDATA", ""),
                         "Blackmagic Design", "DaVinci Resolve", "Support", "Developer",
                         "Scripting", "Modules"),
            os.path.join(os.getenv("APPDATA", ""),
                         "Blackmagic Design", "DaVinci Resolve", "Support", "Developer",
                         "Scripting", "Modules"),
        ]
    elif sys.platform == "darwin":
        search_paths += [
            "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
            os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"),
        ]
    else:
        search_paths += [
            "/opt/resolve/Developer/Scripting/Modules",
            os.path.expanduser("~/.local/share/DaVinciResolve/Support/Developer/Scripting/Modules"),
        ]

    for p in search_paths:
        if p and p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        return None
    return dvr.scriptapp("Resolve")


# ──────────────────────────────────────────────────────────────
#  DETECT ENVIRONMENT
# ──────────────────────────────────────────────────────────────
def running_inside_resolve():
    """Check if bmd module is available (injected by Resolve)."""
    try:
        _ = bmd  # noqa: F821
        return True
    except NameError:
        return False


# ──────────────────────────────────────────────────────────────
#  MARKER COLORS
# ──────────────────────────────────────────────────────────────
COLORS = [
    "Red", "Blue", "Cyan", "Green", "Yellow", "Pink",
    "Purple", "Fuchsia", "Rose", "Lavender", "Sky",
    "Mint", "Lemon", "Sand", "Cocoa", "Cream"
]

COLOR_HEX = {
    "Red": "#FF3B30", "Blue": "#007AFF", "Cyan": "#5AC8FA",
    "Green": "#34C759", "Yellow": "#FFCC00", "Pink": "#FF2D55",
    "Purple": "#AF52DE", "Fuchsia": "#FF00FF", "Rose": "#FF6B81",
    "Lavender": "#C7B8EA", "Sky": "#87CEEB", "Mint": "#00C7B1",
    "Lemon": "#FFFACD", "Sand": "#C2B280", "Cocoa": "#6B3A2A",
    "Cream": "#FFFDD0",
}


# ──────────────────────────────────────────────────────────────
#  FIND SYSTEM PYTHON (not Resolve's bundled one)
# ──────────────────────────────────────────────────────────────
def get_system_python():
    """Find the system Python that has demucs installed."""
    import shutil

    # If running externally, sys.executable is fine
    if not running_inside_resolve():
        return sys.executable

    # Inside Resolve — need to find system Python
    if sys.platform == "win32":
        candidates = [
            shutil.which("python"),
            shutil.which("python3"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
            r"C:\Python312\python.exe",
            r"C:\Python311\python.exe",
        ]
    else:
        candidates = [
            shutil.which("python3"),
            shutil.which("python"),
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/bin/python3",
        ]

    for p in candidates:
        if p and os.path.isfile(p):
            # Verify demucs is installed
            try:
                r = subprocess.run([p, "-m", "demucs", "--help"],
                                   capture_output=True, timeout=10)
                if r.returncode == 0:
                    return p
            except Exception:
                continue

    # Fallback
    return sys.executable


# ──────────────────────────────────────────────────────────────
#  STEM SEPARATION (Demucs)
# ──────────────────────────────────────────────────────────────
def separate_drums(audio_path):
    python_exe = get_system_python()
    out_dir = tempfile.mkdtemp(prefix="demucs_out_")
    cmd = [
        python_exe, "-m", "demucs",
        "--two-stems", "drums",
        "-o", out_dir,
        "-n", "htdemucs",
        audio_path,
    ]
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=600, env=env)
    except Exception as e:
        return None, str(e)

    if result.returncode != 0:
        return None, result.stderr

    basename = os.path.splitext(os.path.basename(audio_path))[0]
    drums_path = os.path.join(out_dir, "htdemucs", basename, "drums.wav")

    if not os.path.isfile(drums_path):
        for root, dirs, files in os.walk(out_dir):
            for f in files:
                if f == "drums.wav":
                    drums_path = os.path.join(root, f)
                    break

    if not os.path.isfile(drums_path):
        return None, "Could not find drums.wav in output"

    return drums_path, None


# ──────────────────────────────────────────────────────────────
#  KICK/SNARE DETECTION
# ──────────────────────────────────────────────────────────────
def detect_kick_snare(drums_path, kick_sens, snare_sens, min_gap_sec, dedup_window=0.03):
    import numpy as np
    from scipy.ndimage import median_filter
    import soundfile as sf

    data, sr = sf.read(drums_path, dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    fft_size = 2048
    hop = fft_size // 4
    num_frames = 1 + (len(data) - fft_size) // hop
    window = np.hanning(fft_size)
    freq_bins = np.fft.rfftfreq(fft_size, d=1.0/sr)

    kick_mask  = (freq_bins >= 20) & (freq_bins <= 120)
    snare_mask = (freq_bins >= 200) & (freq_bins <= 5000)

    kick_energy  = np.zeros(num_frames)
    snare_energy = np.zeros(num_frames)

    for i in range(num_frames):
        start = i * hop
        segment = data[start:start + fft_size] * window
        spectrum = np.abs(np.fft.rfft(segment)) ** 2
        kick_energy[i]  = np.sum(spectrum[kick_mask])
        snare_energy[i] = np.sum(spectrum[snare_mask])

    ke_max = np.max(kick_energy)
    se_max = np.max(snare_energy)
    if ke_max > 0: kick_energy /= ke_max
    if se_max > 0: snare_energy /= se_max

    def pick_onsets(energy, sensitivity, min_gap):
        flux = np.zeros_like(energy)
        flux[1:] = np.maximum(0, energy[1:] - energy[:-1])
        med_size = max(3, int(0.3 * sr / hop))
        if med_size % 2 == 0: med_size += 1
        threshold = median_filter(flux, size=med_size)
        threshold = threshold + sensitivity * 0.15
        min_gap_frames = int(min_gap * sr / hop)
        onsets = []
        last = -min_gap_frames - 1
        for i in range(1, len(flux) - 1):
            if flux[i] > threshold[i] and flux[i] >= flux[i-1] and flux[i] >= flux[i+1]:
                if (i - last) >= min_gap_frames:
                    onsets.append(i)
                    last = i
        return [i * hop / sr for i in onsets]

    kick_onsets  = pick_onsets(kick_energy, kick_sens, min_gap_sec)
    snare_onsets = pick_onsets(snare_energy, snare_sens, min_gap_sec)

    # Dedup
    if kick_onsets and snare_onsets:
        def get_e(t, earr):
            idx = min(int(t * sr / hop), len(earr) - 1)
            return earr[idx]

        all_o = sorted([(t, "k") for t in kick_onsets] + [(t, "s") for t in snare_onsets])
        ck, cs = [], []
        i = 0
        while i < len(all_o):
            t1, ty1 = all_o[i]
            if i + 1 < len(all_o):
                t2, ty2 = all_o[i + 1]
                if abs(t2 - t1) <= dedup_window and ty1 != ty2:
                    kt = t1 if ty1 == "k" else t2
                    st = t1 if ty1 == "s" else t2
                    if get_e(kt, kick_energy) >= get_e(st, snare_energy):
                        ck.append(kt)
                    else:
                        cs.append(st)
                    i += 2
                    continue
            if ty1 == "k": ck.append(t1)
            else: cs.append(t1)
            i += 1
        kick_onsets, snare_onsets = ck, cs

    return kick_onsets, snare_onsets


# ──────────────────────────────────────────────────────────────
#  CLIP FINDER + MARKER PLACEMENT
# ──────────────────────────────────────────────────────────────
def find_audio_clip(timeline, target_filename):
    target_name = os.path.splitext(os.path.basename(target_filename))[0].lower()
    track_count = timeline.GetTrackCount("audio")
    for t_idx in range(1, track_count + 1):
        items = timeline.GetItemListInTrack("audio", t_idx)
        if items:
            for clip in items:
                clip_base = os.path.splitext(clip.GetName())[0].lower()
                if target_name in clip_base or clip_base in target_name:
                    return clip
    return None


def place_markers_on_clip(clip, onset_times, fps, color, name):
    existing = clip.GetMarkers()
    if existing:
        for frame_offset, info in existing.items():
            if info.get("name") == name:
                clip.DeleteMarkerAtFrame(frame_offset)
    added = 0
    for t in onset_times:
        if clip.AddMarker(round(t * fps), color, name, "", 1, ""):
            added += 1
    return added


def clear_all_drum_markers(timeline):
    track_count = timeline.GetTrackCount("audio")
    removed = 0
    for t_idx in range(1, track_count + 1):
        items = timeline.GetItemListInTrack("audio", t_idx)
        if items:
            for clip in items:
                existing = clip.GetMarkers()
                if existing:
                    for frame_offset, info in existing.items():
                        if info.get("name") in ("Kick", "Snare"):
                            clip.DeleteMarkerAtFrame(frame_offset)
                            removed += 1
    return removed


# ══════════════════════════════════════════════════════════════
#  FUSION UI (runs inside Resolve)
# ══════════════════════════════════════════════════════════════
def run_fusion_ui():
    resolve = get_resolve()
    fusion = resolve.Fusion()
    ui = fusion.UIManager
    disp = bmd.UIDispatcher(ui)  # noqa: F821

    win = disp.AddWindow({
        "ID": "TMM",
        "WindowTitle": "Transient Marker Maker",
        "Geometry": [200, 200, 500, 560],
        "Spacing": 8,
    }, [
        ui.VGroup({"Spacing": 6}, [
            ui.Label({
                "Text": "Transient Marker Maker",
                "Alignment": {"AlignHCenter": True},
                "Font": ui.Font({"PixelSize": 18, "Bold": True}),
            }),
            ui.Label({
                "Text": "Stem split + kick & snare detection + Resolve markers",
                "Alignment": {"AlignHCenter": True},
            }),

            # File
            ui.HGroup({"Spacing": 5}, [
                ui.Label({"Text": "Audio File:", "MinimumSize": [80, 0]}),
                ui.LineEdit({"ID": "FilePath", "PlaceholderText": "Select audio...", "ReadOnly": True}),
                ui.Button({"ID": "BrowseBtn", "Text": "Browse", "MaximumSize": [70, 28]}),
            ]),

            ui.Label({"Text": ""}),
            ui.Label({"Text": "Kick", "Font": ui.Font({"PixelSize": 13, "Bold": True})}),
            ui.HGroup({"Spacing": 5}, [
                ui.Label({"Text": "Sensitivity:", "MinimumSize": [80, 0]}),
                ui.Slider({"ID": "KickSens", "Minimum": 0, "Maximum": 100, "Value": 55, "Orientation": "Horizontal"}),
                ui.Label({"ID": "KickSensVal", "Text": "0.55", "MinimumSize": [40, 0]}),
            ]),
            ui.HGroup({"Spacing": 5}, [
                ui.Label({"Text": "Color:", "MinimumSize": [80, 0]}),
                ui.ComboBox({"ID": "KickColor"}),
            ]),

            ui.Label({"Text": ""}),
            ui.Label({"Text": "Snare", "Font": ui.Font({"PixelSize": 13, "Bold": True})}),
            ui.HGroup({"Spacing": 5}, [
                ui.Label({"Text": "Sensitivity:", "MinimumSize": [80, 0]}),
                ui.Slider({"ID": "SnareSens", "Minimum": 0, "Maximum": 100, "Value": 55, "Orientation": "Horizontal"}),
                ui.Label({"ID": "SnareSensVal", "Text": "0.55", "MinimumSize": [40, 0]}),
            ]),
            ui.HGroup({"Spacing": 5}, [
                ui.Label({"Text": "Color:", "MinimumSize": [80, 0]}),
                ui.ComboBox({"ID": "SnareColor"}),
            ]),

            ui.Label({"Text": ""}),
            ui.HGroup({"Spacing": 5}, [
                ui.Label({"Text": "Min Gap (ms):", "MinimumSize": [80, 0]}),
                ui.SpinBox({"ID": "MinGap", "Minimum": 10, "Maximum": 500, "Value": 100, "SingleStep": 10}),
            ]),

            ui.Label({"Text": ""}),
            ui.TextEdit({"ID": "Status", "ReadOnly": True, "MinimumSize": [0, 80],
                         "Font": ui.Font({"Family": "Consolas", "PixelSize": 11})}),

            ui.HGroup({"Spacing": 8}, [
                ui.Button({"ID": "RunBtn", "Text": "Analyze & Place Markers",
                           "MinimumSize": [0, 36], "Font": ui.Font({"PixelSize": 13, "Bold": True})}),
                ui.Button({"ID": "ClearBtn", "Text": "Clear Markers", "MinimumSize": [0, 36]}),
            ]),
        ]),
    ])

    itm = win.GetItems()

    for c in COLORS:
        itm["KickColor"].AddItem(c)
        itm["SnareColor"].AddItem(c)
    itm["KickColor"].CurrentIndex = 0   # Red
    itm["SnareColor"].CurrentIndex = 1  # Blue

    def log(msg):
        current = itm["Status"].PlainText
        itm["Status"].PlainText = current + msg + "\n"

    def on_browse(ev):
        path = fusion.RequestFile("Select Audio File", "", "*.aif;*.aiff;*.wav;*.mp3;*.flac")
        if path:
            itm["FilePath"].Text = path

    def on_kick_sens(ev):
        itm["KickSensVal"].Text = f"{itm['KickSens'].Value / 100:.2f}"

    def on_snare_sens(ev):
        itm["SnareSensVal"].Text = f"{itm['SnareSens'].Value / 100:.2f}"

    def on_clear(ev):
        tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        if tl:
            r = clear_all_drum_markers(tl)
            log(f"Cleared {r} markers.")

    def on_run(ev):
        audio_path = itm["FilePath"].Text
        if not audio_path or not os.path.isfile(audio_path):
            log("ERROR: Select a valid audio file.")
            return

        ks = itm["KickSens"].Value / 100.0
        ss = itm["SnareSens"].Value / 100.0
        kc = COLORS[itm["KickColor"].CurrentIndex]
        sc = COLORS[itm["SnareColor"].CurrentIndex]
        mg = itm["MinGap"].Value / 1000.0

        itm["Status"].PlainText = ""
        itm["RunBtn"].Enabled = False

        log(f"File: {os.path.basename(audio_path)}")
        log(f"Kick: {ks:.2f} {kc} | Snare: {ss:.2f} {sc}")
        log("")
        log("STEP 1: Separating drums...")

        drums_path, err = separate_drums(audio_path)
        if err:
            log(f"ERROR: {err}")
            itm["RunBtn"].Enabled = True
            return
        log("Drums ready.")
        log("")
        log("STEP 2: Detecting...")

        ko, so = detect_kick_snare(drums_path, ks, ss, mg)
        log(f"  Kick: {len(ko)} | Snare: {len(so)}")

        if not ko and not so:
            log("No hits. Lower sensitivity.")
            itm["RunBtn"].Enabled = True
            return

        log("")
        log("STEP 3: Placing markers...")
        tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        fps = float(tl.GetSetting("timelineFrameRate"))
        clip = find_audio_clip(tl, audio_path)
        if not clip:
            log(f"ERROR: No clip matching '{os.path.basename(audio_path)}'")
            itm["RunBtn"].Enabled = True
            return

        k = place_markers_on_clip(clip, ko, fps, kc, "Kick") if ko else 0
        s = place_markers_on_clip(clip, so, fps, sc, "Snare") if so else 0

        log("")
        log(f"Done! {k} kick + {s} snare markers.")
        itm["RunBtn"].Enabled = True

    def on_close(ev):
        disp.ExitLoop()

    win.On.TMM.Close = on_close
    win.On.BrowseBtn.Clicked = on_browse
    win.On.KickSens.ValueChanged = on_kick_sens
    win.On.SnareSens.ValueChanged = on_snare_sens
    win.On.RunBtn.Clicked = on_run
    win.On.ClearBtn.Clicked = on_clear

    win.Show()
    disp.RunLoop()
    win.Hide()


# ══════════════════════════════════════════════════════════════
#  TKINTER UI (runs from Command Prompt)
# ══════════════════════════════════════════════════════════════
def run_tkinter_ui():
    import base64
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext

    ICON_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABtUlEQVR4nO2aS24CMRBEG5+ADRvufzY2"
        "bLhBWBCkBOZju6q7XRpbQolA9is/xMC428zsB3nc7g9ofja/GDBu98e/v9GDwe8W8AmNlsDidwlYg0VJ"
        "YPKbBexBvCWw+U0Cahf3kuDBrxbQuim2BC9+lYDezbAkePJ3BaCbGH3+pgCFdxBdZ1WAymcYXW9RgNJV"
        "HOV/CVD7Hkf5ZevFqBCZ/LL0ZHSITP7JXreUofC/43o5p91NmpkVFH69nKH52XzoPOANR0Nk8rsFfEKj"
        "JbD4XQLWYFESmPxmAXsQbwlsfpOA2sW9JHjwqwW0bootwYtfJaB3MywJnvxdAegmRp+/KUDhHUTXWRWg"
        "8hlG11sUoHQVR/lfAtS+x1F+2XoxKkQmvyw9GR0ila9e3kYfp99/DjvgAxF0ZPNLZogRGiwOfyg6j8Wj"
        "QwxdGPEOIVEa8wohVRxlh5Asj7NCjD5/tsh4hVC5hsw2OXYItd8Rs1WWFUL1XuLw7fKzQ+QdImOM0GBx"
        "+EPReSweHWLowoh3CInSmFcIqeIoO4RkeZwVYvT5s0XGK4TKNWS2ybFDqP2OmK2yrBCq9xJPwwEAIYcX"
        "b3AAAAAASUVORK5CYII="
    )

    LOGO_B64 = (
        "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"
    )

    root = tk.Tk()
    root.title("Transient Marker Maker")
    root.geometry("520x680")
    root.configure(bg="#1e1e1e")
    root.resizable(False, False)

    try:
        icon_data = base64.b64decode(ICON_B64)
        icon_img = tk.PhotoImage(data=base64.b64encode(icon_data))
        root.iconphoto(True, icon_img)
    except Exception:
        pass

    style = ttk.Style()
    style.theme_use("clam")
    style.configure(".", background="#1e1e1e", foreground="#e0e0e0",
                    fieldbackground="#2d2d2d", borderwidth=0)
    style.configure("TLabel", background="#1e1e1e", foreground="#e0e0e0",
                    font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground="#ffffff")
    style.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#888888")
    style.configure("Section.TLabel", font=("Segoe UI", 12, "bold"), foreground="#cccccc")
    style.configure("TButton", background="#3a3a3a", foreground="#e0e0e0",
                    font=("Segoe UI", 10), padding=6)
    style.map("TButton", background=[("active", "#505050")])
    style.configure("Run.TButton", background="#0066cc", foreground="#ffffff",
                    font=("Segoe UI", 12, "bold"), padding=10)
    style.map("Run.TButton", background=[("active", "#0080ff")])
    style.configure("TCombobox", fieldbackground="#2d2d2d", background="#3a3a3a", foreground="#e0e0e0")
    style.configure("TSpinbox", fieldbackground="#2d2d2d", foreground="#e0e0e0")
    style.configure("Horizontal.TScale", background="#1e1e1e", troughcolor="#3a3a3a")

    pad = {"padx": 12, "pady": 2}

    # Header with logo
    header_frame = ttk.Frame(root)
    header_frame.pack(pady=(12, 2))
    try:
        logo_data = base64.b64decode(LOGO_B64)
        logo_img = tk.PhotoImage(data=base64.b64encode(logo_data))
        logo_small = logo_img.subsample(3, 3)
        tk.Label(header_frame, image=logo_small, bg="#1e1e1e").pack(side="left", padx=(0, 10))
        # prevent GC
        header_frame._logo = logo_small
    except Exception:
        pass

    title_frame = ttk.Frame(header_frame)
    title_frame.pack(side="left")
    ttk.Label(title_frame, text="Transient Marker Maker", style="Header.TLabel").pack(anchor="w")
    ttk.Label(title_frame, text="Stem split  +  kick & snare detection  +  Resolve markers",
              style="Sub.TLabel").pack(anchor="w")

    tk.Frame(root, height=1, bg="#3a3a3a").pack(fill="x", padx=12, pady=(8, 4))

    # File
    ff = ttk.Frame(root)
    ff.pack(fill="x", **pad)
    ttk.Label(ff, text="Audio File:", width=12).pack(side="left")
    file_var = tk.StringVar()
    ttk.Entry(ff, textvariable=file_var, state="readonly", width=38).pack(side="left", padx=(0, 5))

    def browse():
        p = filedialog.askopenfilename(title="Select Audio File",
            filetypes=[("Audio", "*.aif *.aiff *.wav *.mp3 *.flac"), ("All", "*.*")])
        if p: file_var.set(p)

    ttk.Button(ff, text="Browse", command=browse).pack(side="left")

    # Kick
    ttk.Label(root, text="Kick", style="Section.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
    ksf = ttk.Frame(root); ksf.pack(fill="x", **pad)
    ttk.Label(ksf, text="Sensitivity:", width=12).pack(side="left")
    kick_sens = tk.DoubleVar(value=0.55)
    kick_val_lbl = ttk.Label(ksf, text="0.55", width=4)
    ttk.Scale(ksf, from_=0, to=1, variable=kick_sens, orient="horizontal",
              command=lambda v: kick_val_lbl.configure(text=f"{float(v):.2f}")
              ).pack(side="left", fill="x", expand=True, padx=(0, 5))
    kick_val_lbl.pack(side="left")

    kcf = ttk.Frame(root); kcf.pack(fill="x", **pad)
    ttk.Label(kcf, text="Color:", width=12).pack(side="left")
    kick_color = tk.StringVar(value="Red")
    kcc = ttk.Combobox(kcf, textvariable=kick_color, values=COLORS, state="readonly", width=15)
    kcc.pack(side="left")
    kcp = tk.Label(kcf, text="  ", bg=COLOR_HEX["Red"], width=3)
    kcp.pack(side="left", padx=5)
    kcc.bind("<<ComboboxSelected>>", lambda e: kcp.configure(bg=COLOR_HEX.get(kick_color.get(), "#888")))

    # Snare
    ttk.Label(root, text="Snare", style="Section.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
    ssf = ttk.Frame(root); ssf.pack(fill="x", **pad)
    ttk.Label(ssf, text="Sensitivity:", width=12).pack(side="left")
    snare_sens = tk.DoubleVar(value=0.55)
    snare_val_lbl = ttk.Label(ssf, text="0.55", width=4)
    ttk.Scale(ssf, from_=0, to=1, variable=snare_sens, orient="horizontal",
              command=lambda v: snare_val_lbl.configure(text=f"{float(v):.2f}")
              ).pack(side="left", fill="x", expand=True, padx=(0, 5))
    snare_val_lbl.pack(side="left")

    scf = ttk.Frame(root); scf.pack(fill="x", **pad)
    ttk.Label(scf, text="Color:", width=12).pack(side="left")
    snare_color = tk.StringVar(value="Blue")
    scc = ttk.Combobox(scf, textvariable=snare_color, values=COLORS, state="readonly", width=15)
    scc.pack(side="left")
    scp = tk.Label(scf, text="  ", bg=COLOR_HEX["Blue"], width=3)
    scp.pack(side="left", padx=5)
    scc.bind("<<ComboboxSelected>>", lambda e: scp.configure(bg=COLOR_HEX.get(snare_color.get(), "#888")))

    # Min gap
    gf = ttk.Frame(root); gf.pack(fill="x", padx=12, pady=(10, 0))
    ttk.Label(gf, text="Min Gap (ms):", width=12).pack(side="left")
    min_gap = tk.IntVar(value=100)
    ttk.Spinbox(gf, from_=10, to=500, increment=10, textvariable=min_gap, width=6).pack(side="left")

    # Status
    status = scrolledtext.ScrolledText(root, height=8, bg="#2d2d2d", fg="#00ff88",
        font=("Consolas", 9), insertbackground="#00ff88", state="disabled", relief="flat")
    status.pack(fill="x", padx=12, pady=(10, 5))

    def log(msg):
        status.configure(state="normal")
        status.insert("end", msg + "\n")
        status.see("end")
        status.configure(state="disabled")
        root.update_idletasks()

    def clear_log():
        status.configure(state="normal")
        status.delete("1.0", "end")
        status.configure(state="disabled")

    def on_clear():
        r = get_resolve()
        if not r: log("ERROR: No Resolve."); return
        tl = r.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        if not tl: log("ERROR: No timeline."); return
        log(f"Cleared {clear_all_drum_markers(tl)} markers.")

    def pipeline(audio_path):
        try:
            ks = kick_sens.get(); ss = snare_sens.get()
            kc = kick_color.get(); sc = snare_color.get()
            mg = min_gap.get() / 1000.0

            clear_log()
            log(f"File: {os.path.basename(audio_path)}")
            log(f"Kick: {ks:.2f} {kc} | Snare: {ss:.2f} {sc}")
            log("")
            log("STEP 1: Separating drums...")

            dp, err = separate_drums(audio_path)
            if err: log(f"ERROR: {err}"); return
            log("Drums ready.")
            log("")
            log("STEP 2: Detecting...")

            ko, so = detect_kick_snare(dp, ks, ss, mg)
            log(f"  Kick: {len(ko)} | Snare: {len(so)}")
            if not ko and not so: log("No hits. Lower sensitivity."); return

            log("")
            log("STEP 3: Placing markers...")
            r = get_resolve()
            tl = r.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
            fps = float(tl.GetSetting("timelineFrameRate"))
            clip = find_audio_clip(tl, audio_path)
            if not clip: log(f"ERROR: No matching clip."); return

            k = place_markers_on_clip(clip, ko, fps, kc, "Kick") if ko else 0
            s = place_markers_on_clip(clip, so, fps, sc, "Snare") if so else 0
            log("")
            log(f"Done! {k} kick + {s} snare markers.")
        except Exception as e:
            log(f"ERROR: {e}")
        finally:
            root.after(0, lambda: run_btn.configure(state="normal"))

    def on_run():
        ap = file_var.get()
        if not ap or not os.path.isfile(ap): log("ERROR: Select a file."); return
        run_btn.configure(state="disabled")
        threading.Thread(target=pipeline, args=(ap,), daemon=True).start()

    bf = ttk.Frame(root); bf.pack(fill="x", padx=12, pady=(5, 12))
    run_btn = ttk.Button(bf, text="Analyze & Place Markers", style="Run.TButton", command=on_run)
    run_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
    ttk.Button(bf, text="Clear Markers", command=on_clear).pack(side="left")

    root.mainloop()


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
if running_inside_resolve():
    run_fusion_ui()
else:
    run_tkinter_ui()
