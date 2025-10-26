from pydub import AudioSegment
import os
import argparse

OUTPUT_FILE = "combined.wav"
TARGET_SR = 44100  # target sample rate (Hz)

def combine_wavs(input_dir, output_file=OUTPUT_FILE):
    files = [f for f in os.listdir(input_dir) if f.endswith(".wav")]
    base = None

    for f in sorted(files):
        path = os.path.join(input_dir, f)
        audio = AudioSegment.from_file(path).set_frame_rate(TARGET_SR).set_channels(1)

        if base is None:
            base = audio
        else:
            base = base.overlay(audio)  # mix on top

    base.export(output_file, format="wav")
    print(f"Saved {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine WAV files with normalized sample rates.")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory containing input WAV files.")
    args = parser.parse_args()

    combine_wavs(args.input_dir)