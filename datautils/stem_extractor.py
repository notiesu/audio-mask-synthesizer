from demucs import pretrained
from demucs.apply import apply_model
import torch
import torchaudio

# Load pretrained Demucs model
model = pretrained.get_model('htdemucs')  # You can use htdemucs_ft or htdemucs6s too
model.eval()

# Load your audio file
wav, sr = torchaudio.load("input.wav")
wav = wav.mean(0, keepdim=True)  # make mono if stereo
wav = wav.to(torch.float32)

# Apply model
with torch.no_grad():
    sources = apply_model(model, wav.unsqueeze(0), split=True, overlap=0.25, progress=True)[0]

# Save stems
stem_names = model.sources  # ['drums', 'bass', 'other', 'vocals']
for name, source in zip(stem_names, sources):
    torchaudio.save(f"{name}.wav", source.cpu(), sr)

print("Done — stems saved.")

#merge stems 
bass, _ = torchaudio.load("bass.wav")
drums, _ = torchaudio.load("drums.wav")
other, _ = torchaudio.load("other.wav")

background = bass + drums + other
torchaudio.save("background.wav", background, sr)