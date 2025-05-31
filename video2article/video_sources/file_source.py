import os
import logging
import boto3
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import webvtt
from datetime import timedelta, datetime
import time
import requests
import cv2
from video2article.utils.constants import THUMBNAIL_INTERVAL
from webvtt import WebVTT
from video2article.utils.config import Config
from video2article.utils.language import map_transcribe_language, TRANSCRIBE_TO_INTERNAL
import asyncio

class FileSource:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.video_title = config.video_title
        self.video_path = config.uri
        self.video_file_name = Path(self.video_path).stem
        self.captions: Optional[WebVTT] = None
        self.thumbnail_ids: List[int] = []
        if config.transcribe_s3_bucket is None:
            raise ValueError("S3 bucket not found")
        self.s3_bucket = config.transcribe_s3_bucket
        self.transcribe_client = boto3.client('transcribe')
        self.s3_client = boto3.client('s3')

    async def load(self) -> None:
        """Load and process the video file"""
        logging.info(f"Loading video file: {self.video_path}")
        logging.info("Transcribing video file with Amazon Transcribe. Generally, it takes several minutes to complete.")
        
        # Upload video to S3
        s3_key = f"videos/{self.video_file_name}.mp4"
        self.s3_client.upload_file(self.video_path, self.s3_bucket, s3_key)
        s3_uri = f"s3://{self.s3_bucket}/{s3_key}"
        
        # Start transcription job with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_name = f"transcribe-{self.video_file_name}-{timestamp}"
        self.transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': s3_uri},
            MediaFormat='mp4',
            IdentifyLanguage=True,
            OutputBucketName=self.s3_bucket,
            OutputKey=f'transcripts/{job_name}.json',
            Subtitles={'Formats': ['vtt']}
        )

        # Wait for transcription to complete (timeout after 5 minutes)
        start_time = time.time()
        timeout = 300  # 5 minutes in seconds
        
        while True:
            status = self.transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                break
                
            # Check if timeout reached
            if time.time() - start_time > timeout:
                raise Exception("Transcription process timed out (5 minutes)")
                
            await asyncio.sleep(5)

        if status['TranscriptionJob']['TranscriptionJobStatus'] == 'FAILED':
            raise Exception("Transcription job failed")

        # Get detected language from transcription job
        detected_language = status['TranscriptionJob']['LanguageCode']
        logging.info(f"Detected language: {detected_language}")
        try:
            internal_language = map_transcribe_language(detected_language)
            self.config.set_source_language(internal_language)
            logging.info(f"Mapped language: {self.config.source_language}")
        except ValueError as e:
            logging.error(str(e))
            raise ValueError(f"Transcription detected an unsupported language. Please use one of the supported languages: {', '.join(TRANSCRIBE_TO_INTERNAL.keys())}")

        # Get VTT file from S3
        vtt_key = f"transcripts/{job_name}.vtt"
        project_folder = self.config.project_folder
        local_vtt_path = project_folder / f"{job_name}.vtt"
        
        # Download VTT file from S3
        self.s3_client.download_file(self.s3_bucket, vtt_key, str(local_vtt_path))
        
        self.captions = webvtt.read(str(local_vtt_path))

        # Extract thumbnails
        self._extract_thumbnails()

        # Delete video and transcript files from S3 after processing
        try:
            # Delete uploaded video file
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
            # Delete transcript JSON file
            transcript_json_key = f"transcripts/{job_name}.json"
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=transcript_json_key)
            # Delete transcript VTT file
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=vtt_key)
            logging.info("Deleted video and transcript files from S3.")
        except Exception as e:
            logging.error(f"Failed to delete S3 files: {str(e)}")

    def _extract_thumbnails(self) -> None:
        """Extract thumbnails from the video file at regular intervals"""
        logging.info("Extracting thumbnails")
        thumbnail_folder = self.config.project_folder / "thumbnails"
        thumbnail_folder.mkdir(exist_ok=True)

        try:
            video = cv2.VideoCapture(self.video_path)
            if not video.isOpened():
                raise ValueError("Unable to open video stream")

            fps = video.get(cv2.CAP_PROP_FPS)
            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps

            self.thumbnail_ids = list(range(0, int(duration), THUMBNAIL_INTERVAL))
            for id in self.thumbnail_ids:
                video.set(cv2.CAP_PROP_POS_MSEC, id * 1000)
                success, frame = video.read()
                if success:
                    thumbnail_path = thumbnail_folder / f"thumbnail_{id}.jpg"
                    compression_params = [cv2.IMWRITE_JPEG_QUALITY, 60]
                    cv2.imwrite(str(thumbnail_path), frame, compression_params)
                    logging.debug(f"Thumbnail saved: {thumbnail_path}")
            video.release()

        except Exception as e:
            logging.error(f"Error extracting thumbnails: {str(e)}")
            raise

    def get_title(self) -> str:
        return self.video_title

    def get_captions(self) -> WebVTT:
        if self.captions is None:
            raise ValueError("Captions not loaded")
        return self.captions

    def get_thumbnail_ids(self) -> List[int]:
        return self.thumbnail_ids 