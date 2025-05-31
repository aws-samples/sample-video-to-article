import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from video2article.utils.bedrock import create_message
from video2article.utils.types import Contents, ContentType, ImageContent, TextContent
from video2article.utils.config import Config
from video2article.utils.utils import (
    get_id_from_thumbnail_path,
    get_path_from_thumbnail_id,
)

class ThumbnailContentExtractor:
    def __init__(self, config: Config):
        self.config = config
        self.project_folder = str(config.project_folder)
        self.thumbnail_max_workers = config.get_config_value("processors.thumbnail_content_extractor.extract_thumbnail_contents.max_workers")
        self.thumbnail_extract_model_id = config.get_config_value("processors.thumbnail_content_extractor.extract_thumbnail_contents.model_id")
        self.thumbnail_keywords_model_id = config.get_config_value("processors.thumbnail_content_extractor.extract_keywords.model_id")

    def process(self, thumbnail_ids:list[int]) -> tuple[dict[int, str], str]:
        logging.info("Extracting thumbnail contents")
        logging.info(f"Processing {len(thumbnail_ids)} thumbnails with {self.thumbnail_max_workers} parallel workers")

        thumbnail_contents = {}
        with ThreadPoolExecutor(max_workers=self.thumbnail_max_workers) as executor:
            future_to_id = {executor.submit(self._process_single_thumbnail, id): id for id in thumbnail_ids}
            for future in as_completed(future_to_id):
                id = future_to_id[future]
                try:
                    content = future.result()
                    thumbnail_contents[id] = content
                    logging.debug(f"Processed thumbnail: {id}")
                except Exception as e:
                    logging.error(f"Error extracting thumbnail content for id {id}: {str(e)}")
                    raise

        thumbnail_contents = dict(sorted(thumbnail_contents.items()))

        # Extract keywords
        keywords = self._extract_keywords(thumbnail_contents)

        return thumbnail_contents, keywords

    def _process_single_thumbnail(self, thumbnail_id: int) -> str:
        thumbnail_path = get_path_from_thumbnail_id(self.project_folder, thumbnail_id)
        with open(thumbnail_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")

        prompt = """This is an image taken from specific points in a presentation video. 
Please transcribe all text visible in the presentation slides and output within <text> tags accurately.
However, for images where presentation slides are not shown or where slides are significantly cut off making the entire text unclear, please do not include anything within the tags.
When transcribing, please structure the output in Markdown format to clearly convey the slide's organization.
Do NOT output more than one <text> tag. Do NOT output other than <text> tag."""

        system = "You are a highly capable AI designed to accurately extract information from images."

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64_image
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        response = create_message(
            messages=messages,
            system=system,
            temperature=0,
            max_tokens=2000,
            stop_sequences=[],
            model_id=self.thumbnail_extract_model_id
        )

        thumbnail_id = get_id_from_thumbnail_path(thumbnail_path)
        return response

    def _extract_keywords(self, thumbnail_contents: dict[int, str]) -> str:
        prompt = f"""Your task is to extract keywords, and key phrases from presentation contents.
I'll provide extracted texts from presentation slides, paired with their slide IDs in <info> tag. Please analyze this information carefully and follow the instructions in <instructions> </instructions>:

<info> {thumbnail_contents} </info>

<instructions>
Your task is to extract keywords and key phrases from <info> tag accurately.
I would like you to accurately list up important keywords, unfamiliar new terms, and key phrases, since I want to use the information when revising the presentation transcript.
Keywords include people names, job titles, company names, product names, event names, location names, technical terms, method names, Amazon/AWS-related terms, and other domain-specific vocabulary.
Depending on the length of the presentation, please extract approximately 30 to 100 keywords and key phrases. 
However, you DO NOT output words or phrases that do not appear in the <info> tag.
List each words or phrases on a separate line.
Add a brief explanation after a colon for all words and phrases, except when their meaning is completely unimaginable from the given context.
Output your results within <result> tags without any other tags.
</instructions>
"""

        messages = [
            {"role": "user", "content": prompt}
        ]

        response = create_message(
            messages=messages,
            temperature=0,
            max_tokens=4000,
            model_id=self.thumbnail_keywords_model_id
        )

        # Extract the revised segment from the response
        keywords = response.split("<result>")[-1].split("</result>")[0].strip()
        logging.debug(f"Extracted keywords: {keywords}")
        return keywords
