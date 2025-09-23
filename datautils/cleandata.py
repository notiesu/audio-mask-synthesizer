import os
import numpy as np
import soundfile as sf
import librosa

# Configuration
SRC_DIR = "raw_wavs"
OUT_DIR = "cleaned_wavs"
TARGET_SR = 16000        # Target sample rate
TARGET_DBFS = -20.0      # Target RMS in dBFS
MIN_LEN_SEC = 0.5        # Minimum length after trimming

os.makedirs(OUT_DIR, exist_ok=True)

def normalize_rms(audio, target_dbfs=TARGET_DBFS):
    # Convert target dBFS to linear RMS
    target_rms = 10 ** (target_dbfs / 20)
    rms = np.sqrt(np.mean(audio**2) + 1e-9)
    return audio * (target_rms / (rms + 1e-9))

def trim_silence(audio, top_db=20):
    # Trim leading and trailing silence
    trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
    return trimmed

for fname in os.listdir(SRC_DIR):
    if not fname.lower().endswith(".wav"):
        continue

    # Load audio
    path_in = os.path.join(SRC_DIR, fname)
    audio, sr = librosa.load(path_in, sr=TARGET_SR, mono=True)

    # Trim silence
    audio = trim_silence(audio, top_db=20)

    # Skip very short clips
    if len(audio) < MIN_LEN_SEC * TARGET_SR:
        print(f"Skipping too short file: {fname}")
        continue

    # Normalize RMS
    audio = normalize_rms(audio, TARGET_DBFS)

    # Save cleaned file
    path_out = os.path.join(OUT_DIR, fname)
    sf.write(path_out, audio, TARGET_SR)
    print(f"Processed {fname} → {path_out}")

print("✅ All files processed.")
