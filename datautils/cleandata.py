from pydub import AudioSegment, silence
import os
import argparse

# === CONFIG ===
MIN_SILENCE_LEN = 500       # ms of silence to detect a split
SILENCE_THRESH = -40        # dBFS threshold for silence
TARGET_DBFS = -20           # normalize loudness target
LOW_PASS_FREQ = 3000        # Hz for low-pass filter
HIGH_PASS_FREQ = 300        # Hz for high-pass filter

def match_target_amplitude(sound, target_dBFS):
    return sound.apply_gain(target_dBFS - sound.dBFS)

def apply_filters(audio):
    # Apply high-pass and low-pass filters
    audio = audio.high_pass_filter(HIGH_PASS_FREQ)
    audio = audio.low_pass_filter(LOW_PASS_FREQ)
    return audio

def main(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for file in os.listdir(input_dir):
        if not file.endswith(".wav"):
            continue

        path = os.path.join(input_dir, file)
        audio = AudioSegment.from_wav(path)

        # Normalize loudness
        audio = match_target_amplitude(audio, TARGET_DBFS)

        # Apply high-pass and low-pass filters
        audio = apply_filters(audio)

        if file.startswith("SOURCE"):
            # If the file starts with "SOURCE", skip silence trimming
            out_path = os.path.join(output_dir, file)
            audio.export(out_path, format="wav")
            print(f"Saved {out_path}")
        else:
            # Split audio by silence
            chunks = silence.split_on_silence(
                audio,
                min_silence_len=MIN_SILENCE_LEN,
                silence_thresh=SILENCE_THRESH,
                keep_silence=200
            )

            for i, chunk in enumerate(chunks):
                # Trim leading/trailing silence from chunk manually
                chunk = chunk.strip_silence(silence_thresh=SILENCE_THRESH)
                # Skip tiny fragments
                if len(chunk) < 300:
                    continue

                out_path = os.path.join(output_dir, f"{file[:-4]}_{i}.wav")
                chunk.export(out_path, format="wav")
                print(f"Saved {out_path}")

    print("Cleaning complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean and split audio files.")
    parser.add_argument("input_dir", help="Directory containing raw audio files")
    parser.add_argument("output_dir", help="Directory to save cleaned audio files")
    args = parser.parse_args()

    main(args.input_dir, args.output_dir)
