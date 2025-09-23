import os
import numpy as np
from scipy.io import wavfile

def mix_wavs_in_directory(directory, output="mixed_output.wav"):
    wav_files = [f for f in os.listdir(directory) if f.lower().endswith(".wav")]
    if not wav_files:
        raise ValueError("No .wav files found in the directory.")

    signals = []
    sample_rates = []

    for fname in wav_files:
        sr, data = wavfile.read(os.path.join(directory, fname))
        sample_rates.append(sr)

        # Convert stereo to mono by averaging channels
        if data.ndim > 1:
            data = data.mean(axis=1)

        signals.append(data.astype(np.float32))  # use float to prevent overflow

    # Ensure all sample rates match
    if len(set(sample_rates)) != 1:
        raise ValueError("All WAV files must have the same sample rate.")
    sr = sample_rates[0]

    # Pad shorter signals with zeros
    max_len = max(len(s) for s in signals)
    padded = [np.pad(s, (0, max_len - len(s))) for s in signals]

    # Sum all signals
    mixed = np.sum(padded, axis=0)

    # Normalize to int16 range
    mixed /= np.max(np.abs(mixed)) + 1e-9  # avoid division by zero
    mixed = (mixed * 32767).astype(np.int16)

    wavfile.write(output, sr, mixed)
    print(f"✅ Mixed {len(wav_files)} files into {output}")

# Example usage
mix_wavs_in_directory("../inputs/godsplan")
