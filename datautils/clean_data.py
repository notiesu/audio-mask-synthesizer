from pydub import AudioSegment, silence
import noisereduce as nr
import numpy as np
import os
import argparse

# === CONFIG ===
MIN_SILENCE_LEN = 500       # ms of silence to detect a split
SILENCE_THRESH = -40        # dBFS threshold for silence
TARGET_DBFS = -20           # normalize loudness target
LOW_PASS_FREQ = 20000       # Hz for low-pass filter (pass almost all frequencies)
HIGH_PASS_FREQ = 20         # Hz for high-pass filter (pass almost all frequencies)
TARGET_SR = 44100           # target sample rate (Hz)

def match_target_amplitude(sound, target_dBFS):
    return sound.apply_gain(target_dBFS - sound.dBFS)

def apply_filters(audio):
    # Apply high-pass and low-pass filters
    audio = audio.high_pass_filter(HIGH_PASS_FREQ)
    audio = audio.low_pass_filter(LOW_PASS_FREQ)
    return audio

def reduce_noise(audio):
    # Convert pydub AudioSegment → np.array → denoise → AudioSegment
    #TODO - this may be producing artifacts 
    return audio  # Placeholder: skip denoising for now
    # samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    # reduced = nr.reduce_noise(y=samples, sr=audio.frame_rate)
    # return audio._spawn(reduced.astype(audio.array_type))

def prevent_clipping(audio):
    if audio.max_dBFS > 0:
        audio = audio.apply_gain(-audio.max_dBFS)
    return audio

def clean_data(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for file in os.listdir(input_dir):
        if not file.endswith(".wav"):
            continue

        path = os.path.join(input_dir, file)
        audio = AudioSegment.from_wav(path)

        # Force mono + target sample rate
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(TARGET_SR)

        # Normalize loudness
        audio = match_target_amplitude(audio, TARGET_DBFS)

        # Apply filters
        audio = apply_filters(audio)

        # Optional denoise (skip if super clean data)
        audio = reduce_noise(audio)

        # Prevent clipping
        audio = prevent_clipping(audio)

        if file.startswith("SOURCE"):
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

            processed_chunks = []
            for i, chunk in enumerate(chunks):
                # Trim leading/trailing silence manually
                chunk = chunk.strip_silence(silence_thresh=SILENCE_THRESH)

                if len(chunk) < 300:
                    continue

                # Re-normalize each chunk
                chunk = match_target_amplitude(chunk, TARGET_DBFS)
                chunk = prevent_clipping(chunk)

                out_path = os.path.join(output_dir, f"{file[:-4]}_{i}.wav")
                chunk.export(out_path, format="wav")
                print(f"Saved {out_path}")

                processed_chunks.append(chunk)

            # Recombine processed chunks in order
            if processed_chunks:
                combined_audio = sum(processed_chunks)
                combined_out_path = os.path.join(output_dir, f"{file[:-4]}_combined.wav")
                combined_audio.export(combined_out_path, format="wav")
                print(f"Saved combined audio: {combined_out_path}")

        print(f"{file}: {len(audio)/1000:.2f}s processed")

    print("Cleaning complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean, split, and recombine audio files.")
    parser.add_argument("input_dir", help="Directory containing raw audio files")
    parser.add_argument("output_dir", help="Directory to save cleaned audio files")
    args = parser.parse_args()

    clean_data(args.input_dir, args.output_dir)
