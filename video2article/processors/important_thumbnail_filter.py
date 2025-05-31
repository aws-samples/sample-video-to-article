import base64
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np
from video2article.utils.bedrock import create_message
from video2article.utils.types import Contents, ContentType, ImageContent, TextContent
from video2article.utils.config import Config

class ImportantThumbnailFilter:
    def __init__(self, config: Config):
        self.config = config
        self.project_folder = str(config.project_folder)
        self.ml_filter_max_workers = config.get_config_value("processors.important_thumbnail_filter.filter_thumbnails_by_ml.max_workers")
        self.ml_filter_batch_size = config.get_config_value("processors.important_thumbnail_filter.filter_thumbnails_by_ml.batch_size")
        self.ml_filter_model_id = config.get_config_value("processors.important_thumbnail_filter.filter_thumbnails_by_ml.model_id")
        self.image_filter_change_threshold = config.get_config_value("processors.important_thumbnail_filter.filter_thumbnails_by_image_change.change_threshold")

    def process(self, thumbnail_ids: list[int]) -> list[int]:
        logging.info("Filtering important thumbnails")
        remaining_ids: list[int] = []

        # Perform classical image processing filtering
        remaining_ids = self._filter_thumbnails_by_image_change(thumbnail_ids)
        logging.info(f"Kept {len(remaining_ids)} thumbnails based on classical image-processing filtering")

        # Perform ml-based filtering
        remaining_ids = self._filter_thumbnails_by_ml(remaining_ids)
        logging.info(f"Kept {len(remaining_ids)} thumbnails based on ML-base filtering")

        logging.debug(f"Remaining thumbnail ids: {remaining_ids}")
        return remaining_ids

    def _filter_thumbnails_by_image_change(self, thumbnail_ids: list[int]) -> list[int]:
        """Filter thumbnails based on significant changes in image content."""
        remaining_ids = [thumbnail_ids[0]]  # Always keep the first image
        last_kept_img = self._load_and_preprocess_image(thumbnail_ids[0])

        for current_id in thumbnail_ids[1:]:
            current_img = self._load_and_preprocess_image(current_id)

            if current_img is None:
                logging.warning(f"Could not read image for thumbnail {current_id}")
                continue

            # Calculate the change ratio between the last kept image and the current image
            change_ratio = self._calculate_image_change_ratio(last_kept_img, current_img)

            if change_ratio >= self.image_filter_change_threshold:
                remaining_ids.append(current_id)
                last_kept_img = current_img
                logging.debug(f"Kept thumbnail {current_id}. Change ratio: {change_ratio:.4f}")
            else:
                logging.debug(f"Skipped thumbnail {current_id}. Change ratio: {change_ratio:.4f}")

        return remaining_ids

    def _load_and_preprocess_image(self, image_id: int):
        """Load an image and preprocess it for comparison."""
        img_path = f"{self.project_folder}/thumbnails/thumbnail_{image_id}.jpg"
        img = cv2.imread(img_path)
        if img is not None:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.GaussianBlur(img, (11, 11), 0)
        return img

    def _calculate_image_change_ratio(self, img1, img2):
        """Calculate the ratio of change between two images."""
        diff = cv2.absdiff(img1, img2)
        _, thresh = cv2.threshold(diff, 10, 255, cv2.THRESH_BINARY)
        return np.sum(thresh) / (thresh.shape[0] * thresh.shape[1] * 255)

    def _filter_thumbnails_by_ml(self, thumbnail_ids: list[int]) -> list[int]:
        n = len(thumbnail_ids)
        overlap = 1
        total_batches = (n - 1) // (self.ml_filter_batch_size - overlap) + 1
        eliminated_ids = set()
        logging.info(f"Processing {n} thumbnails in {total_batches} batches with {self.ml_filter_max_workers} parallel workers")

        with ThreadPoolExecutor(max_workers=self.ml_filter_max_workers) as executor:
            future_to_batch = {}
            for i in range(0, n - 1, self.ml_filter_batch_size - overlap):
                end = min(i + self.ml_filter_batch_size, n)
                batch = thumbnail_ids[i:end]
                logging.debug(f"Submitting batch: thumbnail_ids {batch}")
                future = executor.submit(self._remove_unnecessary_thumbnails_in_batch, batch)
                future_to_batch[future] = batch

            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    ids_to_eliminate = future.result()
                    eliminated_ids.update(ids_to_eliminate)
                except Exception as e:
                    logging.error(f"Batch {batch} generated an exception: {e}")
                    raise e

        remaining_ids = sorted(set(thumbnail_ids) - eliminated_ids)
        return remaining_ids

    def _remove_unnecessary_thumbnails_in_batch(self, batch):
        ids = []
        messages: list[dict[str, any]] = [
            {
                "role": "user",
                "content": []
            }
        ]
        for image_id in batch:
            with open(f"{self.project_folder}/thumbnails/thumbnail_{image_id}.jpg", mode="rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")

            messages[0]["content"].append({
                "type": "text",
                "text": f"Image {image_id}:"
            })

            messages[0]["content"].append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64_image
                }
            })

        prompt = """You are an AI assistant tasked with analyzing a series of images extracted from a presentation video. I attached the images above with image IDs using "Image [ID]:" format. Image IDs indicate the timestamps of extracted image frames from the video. The images are provided in chronological order based on these timestamps.
Your task is to review these images and eliminate "unnecessary" images only based on the following criteria:
<criteria>
1. Eliminate images if presentation content (text or visuals on the presentation slides) remains unchanged at all from the previous chronologically retained image. Disregard all other changes, including presenter's dynamic movements, gestures, and expressions changes, and live transcription updates on the video, which may appear at the top of slides or bottom of the video. Focus solely on presentation content changes.
2. Images should be eliminated if they lack meaningful presentation content, including: blank screens, shots showing only the presenter or panelist without any slide content, frames missing both presenter and slides, or any images with significant visual degradation that makes content difficult to comprehend.
3. Images where text or visuals from different slides are visible should be eliminated.
4. If an image meets the criteria to be kept based on conditions 1-3, but the next image by timestamp shows either identical content with better visibility (e.g., clearer view, larger slide display, sharper image quality) or the same content plus progressive slide animations (e.g., additional bullet points, new diagram components), eliminate the current image and keep the next one instead.
</criteria>

Follow these steps of instructions:
<instructions>
1. Analyze each image attached above very carefully, and determine if it should be kept or eliminated considering all the criteria. Please be extremely careful not to mismatch images and image IDs.
2. Document your careful thought process for each image in one <thinking> tag. Explain your decision to keep or eliminate the image.
3. After analyzing all images, create a final list of the IDs of unnecessary images that should be removed.
4. Output the final list of unnecessary image IDs in <ids> tags, separated by commas. For example: <ids>2,4,6,8,9</ids> or <ids></ids>
</instructions>"""

        messages[0]["content"].append({
            "type": "text",
            "text": prompt
        })

        message = create_message(
                messages=messages,
                system="You are an AI assistant tasked with analyzing a series of images extracted from a presentation video. I will provide you with pairs of Image IDs and corresponding images. Please ensure you correctly understand the relationship between each ID and its associated image.",
                temperature=0,
                max_tokens=4000,
                model_id=self.ml_filter_model_id)

        match = re.search(r'<ids>(.*?)</ids>', message)
        thinking = message.split('<thinking>')[1].split('</thinking>')[0].strip()
        logging.debug(f"_remove_unnecessary_thumbnails_in_batch(), Thinking: {thinking}")
        if match:
            ids = [int(id) for id in match.group(1).split(',') if id]
        else:
            ids = []
        logging.debug(f"_remove_unnecessary_thumbnails_in_batch(), Eliminated thumbnail ids: {ids}")
        return ids
