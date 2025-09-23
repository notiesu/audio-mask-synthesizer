#!/bin/sh

export $(grep -v '^#' .env | xargs)

TRAIN_DATA_PATH=$1
RUN_NAME=$2

RESPONSE=$(curl -s -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/run" \
    -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -H "Content-Type: application/json" \
    -d @train_config.json
)

RUN_ID=$(echo "$RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)

if [ -z "$RUN_ID" ] || [ "$STATUS" = "null" ]; then
    echo "Error: Failed to start RunPod job"
    exit 1
fi

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

