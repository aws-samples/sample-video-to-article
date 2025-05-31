import logging
import os
from concurrent.futures import ThreadPoolExecutor
import re

from video2article.utils.bedrock import create_message
from video2article.utils.types import Contents, ContentType, ImageContent, TextContent
from video2article.utils.config import Config
from video2article.utils.language import adjust_text_length, get_language_name

class TranscriptTranslator:
    def __init__(self, config: Config):
        self.config = config
        self.project_folder = str(config.project_folder)
        self.translate_max_workers = config.get_config_value("processors.transcript_translator.translate.max_workers")
        self.translate_batch_size = config.get_config_value("processors.transcript_translator.translate.batch_size")
        self.translate_model_id = config.get_config_value("processors.transcript_translator.translate.model_id")

    def process(
        self, transcript: Contents, thumbnail_contents: dict[int, str], keywords: str
    ) -> Contents:
        logging.info("Starting translation")
        logging.info(f"Translating from {self.config.get_source_language_name()} to {self.config.get_target_language_name()}")
        self.keywords = keywords

        paragraphs = [str(t.value) for t in transcript.get_contents()]

        segments = [
            paragraphs[i : i + self.translate_batch_size]
            for i in range(0, len(paragraphs), self.translate_batch_size)
        ]
        total_segments = len(segments)

        logging.info(
            f"Processing {total_segments} segments with {self.translate_max_workers} parallel workers"
        )

        with ThreadPoolExecutor(max_workers=self.translate_max_workers) as executor:
            results = list(
                executor.map(self._translate_segment, range(total_segments), segments)
            )

        logging.debug(f"Translated content: {results}")
        translated_content = "\n\n".join([result for result in results if result])

        # Adjust text length based on language ratios
        adjusted_content = adjust_text_length(
            translated_content,
            self.config.source_language or "en",  # Provide default value for None
            self.config.target_language
        )

        contents = Contents(
            [
                TextContent(type=ContentType.TEXT, value=paragraph)
                for paragraph in adjusted_content.split("\n\n")
            ]
        )

        # Check if all image tags remain after processing
        if not self._are_all_image_tags_included(
            thumbnail_contents, adjusted_content
        ):
            raise ValueError(
                "Some image tags were not included in the revised content."
            )

        return contents

    def _translate_segment(self, i, segment):
        logging.info(f"Segment {i+1}: Starting translation")
        source = "\n\n".join([paragraph for paragraph in segment if paragraph])
        pattern = r"<image>(\d+)</image>"
        image_ids = set(map(int, re.findall(pattern, source)))
        prompt = f"""I'm going to provide transcript of a presentation video in <transcript> tag and keywords extracted from presentation slides in <keywords> tag.
Please read them carefully and follow ALL the instructions in <instructions></instructions> tag.

<transcript>
{source}
</transcript>

<keywords>
{self.keywords}
</keywords>

<instructions>
- Your task is to translate the transcript from {self.config.get_source_language_name()} to {self.config.get_target_language_name()}.
- Rephrase unclear or unnatural expressions at the phrase level to improve readability, but You MUST NOT omit entire phrases or change the order of sentences.
- Translating into {self.config.get_target_language_name()} does not mean translating every word. Remember that the target audience consists of technical people familiar with original language terminology in their field. So you should retain in English: People names, job titles, company names, product names, event names, location names, technical terms, method names, Amazon/AWS-related terms, and other domain-specific vocabulary for readability. For the nouns, refer to the keywords in <keywords> tag.
- DO NOT combine and split paragraphs in translation. Each source paragraph must correspond to one translated paragraph, separated by blank lines. Ensure that the number of paragraphs in the input and output is ALWAYS exactly the same.
- IMPORTANT: You MUST preserve ALL the image tags (e.g. <image>0</image>) in the transcript. Please note that this transcript contains image tags with the following values: {sorted(image_ids)}. These tags represent crucial timing information for image display and MUST remain in their exact original positions within the text. DO NOT move, modify, or remove any image tags under any circumstances.
- Output only the translated text within <result> tag. You MUST NOT output any other text outside of this tag.
</instructions>"""

        response = create_message(
            messages=[{"role": "user", "content": prompt}],
            system="You are a highly skilled translator with extensive knowledge of IT and product development.",
            temperature=0.2,
            max_tokens=4000,
            stop_sequences=[],
            model_id=self.translate_model_id,
        )
        translated_transcript = (
            response.split("<result>")[1].split("</result>")[0].strip()
        )
        logging.info(f"Segment {i+1}: Completed translation")
        return translated_transcript

    def _are_all_image_tags_included(
        self, thumbnail_contents: dict[int, str], revised_content: str
    ) -> bool:
        # Create a set of thumbnail IDs
        thumbnail_ids = set(thumbnail_contents.keys())

        # Extract all image tag IDs from revised_content
        pattern = r"<image>(\d+)</image>"
        content_ids = set(map(int, re.findall(pattern, revised_content)))

        # Calculate the differences
        missing_ids = thumbnail_ids - content_ids
        extra_ids = content_ids - thumbnail_ids

        if missing_ids or extra_ids:
            # Log error information if there's a mismatch
            logging.error(
                f"Image tag mismatch detected:Thumbnail IDs: {sorted(thumbnail_ids)}, Content IDs: {sorted(content_ids)}, Missing IDs: {sorted(missing_ids)}, Extra IDs: {sorted(extra_ids)}"
            )
            return False

        # Return True if all IDs match
        return True
