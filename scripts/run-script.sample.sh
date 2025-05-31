#!/bin/bash

# Set parameters
# VIDEO_TITLE="Amazon Cognito Introduction"
# VIDEO_PATH=/data/input/sample_video.mp4
# TRANSCRIBE_S3_BUCKET=video2article-uswest2-012345678901
# TARGET_LANGUAGE=jp
VIDEO_TITLE="<Enter video title here>" 
VIDEO_PATH=/data/input/<Enter video filename here>
TRANSCRIBE_S3_BUCKET=<Enter S3 bucket (in us-west-2) name here>
TARGET_LANGUAGE=<Enter target language here (en: English, zh-CN: Chinese (Simplified), es: Spanish, ar: Arabic, hi: Hindi, fr: French, ja: Japanese, pt: Portuguese, ru: Russian, de: German, kr: Korean)>

# Following values are fixed
OUTPUT_DIR=/data/output
OUTPUT_FORMAT=pdf
CONFIG_PATH=./config.yaml

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    export $(aws configure export-credentials --format env)
fi

# Build Docker image using Dockerfile
echo "Building Docker image..."
if [[ $(uname -m) == 'arm64' ]]; then
    docker build --platform=linux/arm64 -t video2article -f Dockerfile .
else
    docker build -t video2article -f Dockerfile .
fi

# Run container with environment variables
echo "Starting container..."
docker run --rm \
  -v $(pwd)/data:/data \
  -e VIDEO_TITLE="${VIDEO_TITLE}" \
  -e VIDEO_PATH=${VIDEO_PATH} \
  -e OUTPUT_DIR=${OUTPUT_DIR} \
  -e OUTPUT_FORMAT=${OUTPUT_FORMAT} \
  -e LOG_MODE=${LOG_MODE} \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN} \
  -e AWS_DEFAULT_REGION=us-west-2 \
  -e TRANSCRIBE_S3_BUCKET=${TRANSCRIBE_S3_BUCKET} \
  -e TARGET_LANGUAGE=${TARGET_LANGUAGE} \
  -e CONFIG_PATH=${CONFIG_PATH} \
  video2article \