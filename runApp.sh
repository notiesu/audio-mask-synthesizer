#!/bin/sh

### Args ###
### --source <source> = wav file name within the inputs folder, the voice that will be spoken
### --target <target> = wav file name within the inputs folder - the voice that will be mimicked
### 

# push into s3 temp folder
# Generate a unique temporary folder name

# Usage check

# Load env vars from .env
export $(grep -v '^#' .env | xargs)

#default source_file and target_file
if [ -z "$1" ] || [ -z "$2" ]; then
    SOURCE_FILE="inputs/example_source.wav"
    TARGET_FILE="inputs/example_target.wav"
else
    SOURCE_FILE="inputs/$1"
    TARGET_FILE="inputs/$2"
fi

TMP_FOLDER="tmp/$(date +%s)-$RANDOM"

#Upload input files to S3 tmp folder
for f in "$SOURCE_FILE" "$TARGET_FILE"; do
    aws s3 cp "$f" "s3://$RUNPOD_NETWORK_BUCKET/$TMP_FOLDER/" \
        --region us-ca-2 \
        --endpoint-url https://s3api-us-ca-2.runpod.io || {
        echo "Error uploading $f"
        exit 1
    }
done

# Call RunPod endpoint until it completes
RESPONSE=$(curl -s -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/run" \
    -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"input\": {
          \"source_path\": \"/runpod-volume/$TMP_FOLDER/$(basename $SOURCE_FILE)\",
          \"target_path\": \"/runpod-volume/$TMP_FOLDER/$(basename $TARGET_FILE)\",
          \"output_path\": \"/runpod-volume/$TMP_FOLDER/output\",
          \"inference_flag\": true
        }
    }"
)
RUN_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)

if [ -z "$RUN_ID" ] || [ "$STATUS" = "null" ]; then
    echo "Error: Failed to start RunPod job"
    exit 1
fi

# Poll the RunPod endpoint until the job completes
while [ "$STATUS" != "COMPLETED" ]; do
    sleep 30
    RESPONSE=$(curl -s -X GET "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/status/$RUN_ID" \
        -H "Authorization: Bearer $RUNPOD_API_KEY")
    STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    echo "Current job status: $STATUS"
    if [ "$STATUS" = "FAILED" ]; then
        echo "Error: RunPod job failed"
        exit 1
    fi
done

# RESPONSE=$(curl -s -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/runsync" \
#     -H "Authorization: Bearer $RUNPOD_API_KEY" \
#     -H "Content-Type: application/json" \
#     -d "{
#           \"input\": {
#             \"args\": [
#               \"--source\", \"/runpod-volume/$TMP_FOLDER/$1\",
#               \"--target\", \"/runpod-volume/$TMP_FOLDER/$2\",
#               \"--output\", \"/runpod-volume/$TMP_FOLDER/output.wav\"
#             ]
#           }
#         }") | jq -r .status

# echo $RESPONSE
#Download output file from S3
aws s3 cp "s3://$RUNPOD_NETWORK_BUCKET/$TMP_FOLDER/output" \
    output/ \
    --recursive \
    --region us-ca-2 \
    --endpoint-url https://s3api-us-ca-2.runpod.io || {
    echo "Error downloading output files"
    exit 1
}

#Cleanup TMP_FOLDER in S3
aws s3 rm "s3://$RUNPOD_NETWORK_BUCKET/$TMP_FOLDER" \
    --recursive \
    --region us-ca-2 \
    --endpoint-url https://s3api-us-ca-2.runpod.io || {
    echo "Warning: failed to clean up tmp folder"
}

echo "Pipeline complete: output saved to output/output.wav"