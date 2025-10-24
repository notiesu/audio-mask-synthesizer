import argparse
from demucs import pretrained
from demucs.apply import apply_model
import torch
import torchaudio
import os

def extract_stems(input_file, output_dir):
    # Load pretrained Demucs model
    model = pretrained.get_model('htdemucs')  # You can use htdemucs_ft or htdemucs6s too

    model.eval()

    # Load your audio file
    wav, sr = torchaudio.load(input_file)
    if wav.shape[0] == 1:  # mono
        wav = wav.repeat(2, 1)  # convert to stereo
    wav = wav.to(torch.float32)

    # Apply model
    with torch.no_grad():
        sources = apply_model(model, wav.unsqueeze(0), split=True, overlap=0.25, progress=True)[0]

    # Save stems
    stem_names = model.sources  # ['drums', 'bass', 'other', 'vocals']
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    for name, source in zip(stem_names, sources):
        stem_path = os.path.join(output_dir, f"{name}.wav")
        torchaudio.save(stem_path, source.cpu(), sr)

    # Merge stems
    # TODO - don't know if we need this for right now
    # bass, _ = torchaudio.load(os.path.join(output_dir, "bass.wav"))
    # drums, _ = torchaudio.load(os.path.join(output_dir, "drums.wav"))
    # other, _ = torchaudio.load(os.path.join(output_dir, "other.wav"))

    # background = bass + drums + other
    # torchaudio.save(os.path.join(output_dir, "background.wav"), background, sr)

    print(f"Done — stems saved in {output_dir}.")

def main():
    parser = argparse.ArgumentParser(description="Extract and merge stems from an audio file.")
    parser.add_argument("input_file", type=str, help="Path to the input audio file.")
    parser.add_argument("output_dir", type=str, help="Directory to save the output stems.")
    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    extract_and_merge_stems(args.input_file, args.output_dir)

if __name__ == "__main__":
    main()