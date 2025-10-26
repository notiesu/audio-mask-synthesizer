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

def clean_data(input_file, trim_silence=True, pitch_shift=0):
    audio = AudioSegment.from_wav(input_file)

    # Force mono + target sample rate
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(TARGET_SR)

    # Apply pitch shift
    if pitch_shift != 0:
        audio = shift_pitch(audio, pitch_shift)

    # Normalize loudness
    audio = match_target_amplitude(audio, TARGET_DBFS)

    # Apply filters
    audio = apply_filters(audio)

    # Optional denoise (skip if super clean data)
    # audio = reduce_noise(audio)

    # Prevent clipping
    audio = prevent_clipping(audio)

    if trim_silence:
        audio = trim_audio_silence(audio)

    # Overwrite the input file
    audio.export(input_file, format="wav")
    print(f"Processed and saved: {input_file}")


def trim_audio_silence(audio):
    # Split audio by silence
    chunks = silence.split_on_silence(
        audio,
        min_silence_len=MIN_SILENCE_LEN,
        silence_thresh=SILENCE_THRESH,
        keep_silence=200
    )

    processed_chunks = []
    for chunk in chunks:
        # Trim leading/trailing silence manually
        chunk = chunk.strip_silence(silence_thresh=SILENCE_THRESH)

        if len(chunk) < 300:
            continue

        # Re-normalize each chunk
        chunk = match_target_amplitude(chunk, TARGET_DBFS)
        chunk = prevent_clipping(chunk)

        processed_chunks.append(chunk)

    # Recombine processed chunks in order
    if processed_chunks:
        audio = sum(processed_chunks)

    return audio

def shift_pitch(audio, semitones):
    new_sample_rate = int(audio.frame_rate * (2.0 ** (semitones / 12.0)))
    pitched_audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
    return pitched_audio.set_frame_rate(audio.frame_rate)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean, split, and recombine audio files.")
    parser.add_argument("input_dir", help="Directory containing raw audio files")
    parser.add_argument("output_dir", help="Directory to save cleaned audio files")
    args = parser.parse_args()

    clean_data(args.input_dir, args.output_dir)
