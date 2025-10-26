#full pipeline - given youtube url, download audio, split stems
import os
import requests
import yt_dlp
import ffmpeg
import boto3
import sys
from dotenv import load_dotenv
from botocore.exceptions import ClientError
import json
from time import sleep, time
import argparse
import shutil

#data utils
from combine_wavs import combine_wavs
from clean_data import clean_data
from extract_stems import extract_stems


#### CONFIG ###
load_dotenv()

#AWS config
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")
RUNPOD_ENDPOINT_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")
RUNPOD_NETWORK_BUCKET = os.getenv("RUNPOD_NETWORK_BUCKET")
REGION = "us-ca-2"

#temp audio file configs
TEMP_DIR = "tmp"
STEMS_PATH = f"{TEMP_DIR}/stems"
YT_WAV_OUTPUT_DIR = f"{TEMP_DIR}/yt_audio.wav" #only directory
YT_WAV_OUTPUT_NAME = "yt_audio"
OUTPUT_S3_PATH = f"s3://{RUNPOD_NETWORK_BUCKET}/{TEMP_DIR}/output"
LOCAL_VC_OUTPUT_PATH = f"{TEMP_DIR}/stems"

DEBUG_MODE = False
TARGET_PITCH_SHIFT = 0  # in octaves

#request configs
with open("request_config.json", "r") as f:
    VC_REQUEST_CONFIG = json.load(f)

def upload_files_to_s3(source_file, target_file, tmp_folder):
    # First copy source_file and target_file renamed to SOURCE.wav and TARGET.wav respectively
    source_renamed = os.path.join(os.path.dirname(source_file), "SOURCE.wav")
    target_renamed = os.path.join(os.path.dirname(target_file), "TARGET.wav")

    os.rename(source_file, source_renamed)
    os.rename(target_file, target_renamed)

    # Update the source_file and target_file variables to point to the renamed files
    source_file = source_renamed
    target_file = target_renamed

    s3 = boto3.client(
        "s3",
        region_name=REGION,
        endpoint_url=AWS_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    for f in [source_file, target_file]:
        key = os.path.join(tmp_folder, os.path.basename(f))
        try:
            print(f"Uploading {f} → s3://{RUNPOD_NETWORK_BUCKET}/{key}")
            s3.upload_file(f, RUNPOD_NETWORK_BUCKET, key)
        except ClientError as e:
            print(f"Error uploading {f}: {e}")
            sys.exit(1)

    print("✅ Upload successful for both files.")
    #return the s3 paths
    source_s3_path = f"s3://{RUNPOD_NETWORK_BUCKET}/{os.path.join(tmp_folder, 'SOURCE.wav')}"
    target_s3_path = f"s3://{RUNPOD_NETWORK_BUCKET}/{os.path.join(tmp_folder, 'TARGET.wav')}"
    return source_s3_path, target_s3_path

def youtube_to_wav(url: str, output_path: str):
    """Downloads the audio from a YouTube video and saves it as a .wav file using yt-dlp."""
        
    temp_file = os.path.join(os.path.dirname(output_path), YT_WAV_OUTPUT_NAME)

    # Download the audio stream directly as WAV using yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_file,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'quiet': True,
    }

    print(f"Downloading audio from: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        #overwrite if tmp exists
        if os.path.exists(temp_file):
            os.remove(temp_file)
        ydl.download([url])

    # Convert to .wav using ffmpeg
    # print(f"Converting to WAV...")
    # ffmpeg.input(temp_file).output(output_path, format='wav', acodec='pcm_s16le', ar=44100).run(quiet=True, overwrite_output=True)

    # Cleanup
    # os.remove(temp_file)
    print(f"Saved WAV file at: {output_path}")
    return output_path

def perform_voice_conversion(source_s3_path: str, target_s3_path: str, output_s3_path: str):
    request_config = VC_REQUEST_CONFIG.copy()
    #TODO - remove this hardcoding
    request_config["input"]["source"] = "/runpod-volume/tmp/SOURCE.wav"
    request_config["input"]["target"] = "/runpod-volume/tmp/TARGET.wav"
    request_config["input"]["output"] = "/runpod-volume/tmp/output"

    # Call the voice conversion API
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(RUNPOD_ENDPOINT_URL, headers=headers, json=request_config)
    if response.status_code != 200:
        print(f"Error: {response.text}")
        sys.exit(1)

    # Poll the RunPod API until the job is completed
    run_id = response.json().get("id")
    if not run_id:
        print("Error: RunPod job ID not found in response.")
        sys.exit(1)

    status = "PENDING"
    while status != "COMPLETED":
        print("Waiting for RunPod job to complete...")
        sleep(30)  # Wait for 30 seconds before checking the status again

        status_response = requests.get(
            f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{run_id}",
            headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"}
        )

        if status_response.status_code != 200:
            print(f"Error checking job status: {status_response.text}")
            sys.exit(1)

        status = status_response.json().get("status")
        print(f"Current job status: {status}")

        if status == "FAILED":
            print("Error: RunPod job failed.")
            sys.exit(1)

    print(f"Voice conversion successful: {response.text}")

    #return the output s3 path
    return output_s3_path


def download_from_s3_folder(s3_folder_path: str, local_folder_path: str):
    try:
        # Initialize the S3 client
        s3 = boto3.client(
            "s3",
            region_name=REGION,
            endpoint_url=AWS_ENDPOINT_URL,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )

        os.makedirs(local_folder_path, exist_ok=True)

        # Parse the bucket name and prefix from the S3 folder path
        if not s3_folder_path.startswith("s3://"):
            raise ValueError("Invalid S3 folder path. Must start with 's3://'.")
        
        s3_path_parts = s3_folder_path[5:].split("/", 1)
        bucket_name = s3_path_parts[0]
        prefix = s3_path_parts[1] if len(s3_path_parts) > 1 else ""

        # List objects in the S3 folder
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if "Contents" not in response:
            print(f"No files found in S3 folder: {s3_folder_path}")
            return

        # Download each file to the local folder
        for obj in response["Contents"]:
            s3_key = obj["Key"]
            file_name = os.path.basename(s3_key)
            local_file_path = os.path.join(local_folder_path, file_name)

            print(f"Downloading {s3_key} to {local_file_path}")
            s3.download_file(bucket_name, s3_key, local_file_path)

        print(f"Downloaded all files from {s3_folder_path} to {local_folder_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main(input_url: str, input_target_voice_path: str = "default_voice"):
    #download from youtube
    #check for existence of input_target_voice_path

    #keep track of runtime
    start_time = time()
    if not os.path.exists(input_target_voice_path):
        print(f"Error: Target voice file {input_target_voice_path} does not exist.")
        sys.exit(1)
    if DEBUG_MODE:
        if os.path.exists(YT_WAV_OUTPUT_DIR):
            print(f"Debug mode: Using existing YouTube audio at {YT_WAV_OUTPUT_DIR}")
            output_wav = YT_WAV_OUTPUT_DIR
    else:
        output_wav = youtube_to_wav(input_url, YT_WAV_OUTPUT_DIR)

    print(f"Downloaded and converted YouTube audio to WAV: {output_wav}")
    #print time
    end_time_dl = time()
    elapsed_time_dl = end_time_dl - start_time
    print(f"Time taken for download and conversion: {elapsed_time_dl:.2f} seconds")
    #check for existence of stems in debug mode
    if DEBUG_MODE:
        if os.path.exists(STEMS_PATH):
            print(f"Debug mode: Using existing stems at {STEMS_PATH}")
    else:
        extract_stems(output_wav, STEMS_PATH)
    print(f"Extracted stems to: {STEMS_PATH}")
    #print time
    end_time_stems = time()
    elapsed_time_stems = end_time_stems - end_time_dl
    print(f"Time taken for stem extraction: {elapsed_time_stems:.2f} seconds")
    #path to vocal stem

    vocal_path = os.path.join(STEMS_PATH, "vocals.wav")
    #create a copy to tmp/archive just in case
    os.makedirs(os.path.join(TEMP_DIR, "inputs"), exist_ok=True)
    shutil.copy2(input_target_voice_path, os.path.join(TEMP_DIR, "inputs", "TARGET.wav"))
    shutil.copy2(vocal_path, os.path.join(TEMP_DIR, "inputs", "SOURCE.wav"))

    #perform operations on these copies
    source_input_path = os.path.join(TEMP_DIR, "inputs", "SOURCE.wav")
    target_input_path = os.path.join(TEMP_DIR, "inputs", "TARGET.wav")

    clean_data(target_input_path, trim_silence=True)
    clean_data(source_input_path, trim_silence=False)
    #upload vocal and target voice to s3

    source_s3_path, target_s3_path = upload_files_to_s3(source_input_path, target_input_path, tmp_folder=TEMP_DIR)

    #once uploaded run voice conversion inference
    output_s3_path = os.path.join("runpod-volume", TEMP_DIR, "output")
    perform_voice_conversion(source_s3_path, target_s3_path, output_s3_path)

    #download output from s3
    download_from_s3_folder(f"s3://{RUNPOD_NETWORK_BUCKET}/{TEMP_DIR}/output", STEMS_PATH)
    
    # Move SOURCE.wav to another subfolder instead of deleting
    archive_folder = os.path.join(STEMS_PATH, "inputs")
    os.makedirs(archive_folder, exist_ok=True)
    os.rename(
        os.path.join(STEMS_PATH, "vocals.wav"),
        os.path.join(archive_folder, "SOURCE_VOCALS.wav")
    )
    #combine stems
    combine_wavs(STEMS_PATH, output_file="final_output.wav")

    end_time = time()
    elapsed_time = end_time - start_time
    print(f"Total processing time: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice conversion pipeline")
    parser.add_argument("--yt_url", type=str, help="YouTube URL of the source audio")
    parser.add_argument("--target", type=str, help="Path to the target voice WAV file")
    parser.add_argument("--shift_pitch", type=float, default=0, help="Pitch shift of target voice in semitones")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Set debug mode if specified
    DEBUG_MODE = args.debug
    TARGET_PITCH_SHIFT = args.shift_pitch
    main(input_url=args.yt_url, input_target_voice_path=args.target)