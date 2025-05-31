import re
from typing import List
from video2article.utils.types import Contents, ContentType, ImageContent, TextContent
from video2article.utils.config import Config


class ImageTagParser:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.project_folder = str(config.project_folder)

    def process(self, contents: Contents) -> Contents:
        new_contents = Contents()
        image_tag_pattern = re.compile(r'<image>(\d+)</image>')

        for content in contents.get_contents():
            if content.type == ContentType.TEXT:
                text = content.value
                if not isinstance(text, str):
                    continue
                matches = image_tag_pattern.findall(text)

                for image_id in matches:
                    new_contents.add_content(ImageContent(type=ContentType.IMAGE, value=int(image_id)))

                cleaned_text = image_tag_pattern.sub('', text)
                new_contents.add_content(TextContent(type=ContentType.TEXT, value=cleaned_text))
            else:
                new_contents.add_content(content)

        # Copy metadata
        new_contents.title = contents.title
        new_contents.url = contents.url

        return new_contents
