import logging
import os
from typing import Optional

from video2article.utils.types import Contents, ContentType
from video2article.utils.config import Config
from video2article.utils.bedrock import create_message
from video2article.utils.language import get_character_ratio

class ContentOrganizer:
    def __init__(self, config: Config):
        self.config = config
        self.project_folder = str(config.project_folder)
        self.summary_model_id = config.get_config_value("processors.content_organizer.summary.model_id")
        self.chapters_model_id = config.get_config_value("processors.content_organizer.chapters.model_id")

    def process(self, contents: Contents) -> Contents:
        logging.info("Starting content organization")
        logging.info(f"Source language: {self.config.get_source_language_name()}")
        logging.info(f"Target language: {self.config.get_target_language_name()}")

        # Extract text content for processing
        text_content = []
        for content in contents.get_contents():
            if content.type == ContentType.TEXT:
                text_content.append(str(content.value))

        # Generate summary
        summary = self._generate_summary(text_content)
        contents.add_summary(summary)

        # Generate chapters
        chapters = self._generate_chapters(text_content)
        for chapter in chapters:
            contents.add_chapter(chapter["title"], chapter["segment_start_id"] - 1, chapter["segment_end_id"] - 1)

        logging.info("Content organization completed successfully")
        return contents

    def _generate_summary(self, text_content: list[str]) -> str:
        content = "\n".join(text_content)
        target_lang = self.config.get_target_language_name()

        # Calculate target length based on language ratios
        source_ratio = get_character_ratio(self.config.source_language or "en")
        target_ratio = get_character_ratio(self.config.target_language)
        target_length = int(300 * (source_ratio / target_ratio))

        prompt = f"""Please carefully read the content of the session transcript below and follow the instructions at the end.
<content>
{content}
</content>

<instruction>
- Your task is to write a summary of the session video content in approximately {target_length} characters.
- Based solely on the content within the <content> tag, cover the main topics discussed in the session and write a text that correctly conveys the overall context of what is mentioned in the session.
- Absolutely do not write about anything not mentioned within the <content> tag.
- Write the summary in natural {target_lang}, starting with "In this video," (translated to {target_lang}).
- Ensure the text sounds authentic to native {target_lang} speakers with appropriate language structures, expressions, and politeness levels for the target language.
- Be conscious of mentioning specific data and unique insights to avoid creating a vague summary.
- For proper nouns including people's names, job titles, company names, function names, method names, and technical terms, always use the original lanuguage terms exactly as they appear in the <content> tag without translation.
- Avoid directly appealing to readers about why they should read it. Focus on describing the excellence of the content itself.
- Do not mention the presentation time.
- Output the result within <result> tags. Do not include any other tags within the result, and do not output anything before or after the <result> tags.
</instruction>"""

        response = create_message(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000,
            stop_sequences=[],
            model_id=self.summary_model_id
        )

        result = response.split("<result>")[1].split("</result>")[0].strip()
        logging.debug(f"Generated summary: {result}")
        return result

    def _generate_chapters(self, text_content: list[str]) -> list[dict]:
        text_contents = [f"<paragraph id=\"{i+1}\">\n{content}\n</paragraph>" for i, content in enumerate(text_content)]
        formatted_contents = "\n".join(text_contents)
        target_lang = self.config.get_target_language_name()

        prompt = f"""Below is an article created from a presentation video transcript.
The article is divided into paragraphs, each provided as a paragraph element. Please read it carefully and follow the instructions below. Note that paragraph IDs are consecutive integers starting from 1.
<article>
{formatted_contents}
</article>

<instruction>
Step 1. First, divide the entire article into approximately {len(text_content) // 8} segments (meaningful chunks of consecutive paragraphs) based on the flow of content.
Consider the following points when dividing:
a) Clear changes in topic or subject matter
b) Introduction of new concepts or technologies
c) Change of speakers
d) Changes in timeline or perspective

Step 2. Create appropriate headings for each segment to make it easy for readers to understand. Consider the following points when creating headings:
a) Reflect the main theme or concept of the entire segment (especially the first few paragraphs)
b) Use concrete and concise expressions to make it easy for readers to grasp the content
c) Utilize important terms and expressions used within the segment as much as possible
d) For proper nouns including people's names and technical terms, always use the exact notation as it appears in the segment
e) Be careful not to preview the content of the next segment
f) Vary the sentence structure and style of headings to avoid monotony

Step 3. Output the segment division and heading creation results in the following format within <result> tags:
<result>
[
    {{
        "segment_start_id": [first paragraph ID of the segment],
        "segment_end_id": [last paragraph ID of the segment],
        "title": "[segment heading]"
    }},
    ...
]
</result>

Note:
- Write the output in {target_lang}
- The result must be output in JSON format.
- For short articles, it is not necessary to force multiple segments. Judge appropriately based on the content.
- The first segment starts with paragraph ID:1, so the segment_start_id of the first segment must be 1. The segment_end_id of one segment and the segment_start_id of the next segment must be consecutive values.
</instruction>"""

        response = create_message(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000,
            stop_sequences=[],
            model_id=self.chapters_model_id
        )

        try:
            import json
            result = response.split("<result>")[1].split("</result>")[0].strip()
            chapters = json.loads(result)
            logging.debug(f"Generated chapters: {chapters}")
            return chapters
        except json.JSONDecodeError:
            logging.error("Failed to parse chapter information")
            return [] 