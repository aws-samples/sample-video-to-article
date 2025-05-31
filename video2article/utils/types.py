from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from video2article.utils.utils import (
    load_json,
    save_json,
)


@dataclass
class ThumbnailPosition:
    thumbnail_id: int
    paragraph_id: int | None


class ContentType(Enum):
    TEXT = "text"
    IMAGE = "image"
    SUBTITLE = "subtitle"

@dataclass
class TextContent:
    type: ContentType.TEXT
    value: str

@dataclass
class ImageContent:
    type: ContentType.IMAGE
    value: int

@dataclass
class SubtitleContent:
    type: ContentType.SUBTITLE
    value: str

Content = TextContent | ImageContent | SubtitleContent


class Contents:
    def __init__(self, contents: Optional[list[Content]] = None):
        self.contents: list[Content] = contents or []
        self.url: Optional[str] = None
        self.title: Optional[str] = None
        self.summary: Optional[str] = None
        self.chapters: list[dict] = []  # List of chapters with title and content indices

    def add_content(self, content: Content) -> None:
        self.contents.append(content)

    def get_contents(self) -> list[Content]:
        return self.contents

    def add_summary(self, summary: str) -> None:
        self.summary = summary

    def add_chapter(self, title: str, start_index: int, end_index: int) -> None:
        self.chapters.append({
            "title": title,
            "start_index": start_index,
            "end_index": end_index
        })

    def add_thumbnail_position(self, thumbnail_positions: list[dict[str, int]]) -> Contents:
        new_contents = Contents()

        # Create a mapping of paragraph IDs to image IDs
        images_before_paragraphs = {
            pos['paragraph_id']: pos['image_id']
            for pos in thumbnail_positions
            if pos['paragraph_id'] is not None
        }

        # Extract images with no specific paragraph (to be added at the end)
        images_at_end = [
            pos['image_id']
            for pos in thumbnail_positions
            if pos['paragraph_id'] is None
        ]

        # Process contents and insert images where necessary
        for paragraph_index, content in enumerate(self.contents, 1):
            # Insert image before the paragraph if one exists
            if paragraph_index in images_before_paragraphs:
                image_id = images_before_paragraphs[paragraph_index]
                new_contents.add_content(ImageContent(type=ContentType.IMAGE, value=image_id))

            # Add the original content
            new_contents.add_content(content)

        # Add remaining images at the end
        for image_id in images_at_end:
            new_contents.add_content(ImageContent(type=ContentType.IMAGE, value=image_id))

        # Copy metadata
        new_contents.title = self.title
        new_contents.url = self.url
        new_contents.summary = self.summary
        new_contents.chapters = self.chapters

        return new_contents

    def add_url(self, url: str) -> None:
        self.url = url

    def add_title(self, title: str) -> None:
        self.title = title


    def to_dict(self) -> dict[str, any]:
        return {
            "contents": [
                {"type": content.type.value, "value": content.value}
                for content in self.contents
            ],
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "chapters": self.chapters
        }

    def save(self, filepath: str) -> None:
        save_json(self.to_dict(), filepath)

    @classmethod
    def load(cls, filepath: str) -> Contents:
        data = load_json(filepath)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, any]) -> Contents:
        contents = []
        for item in data['contents']:
            if item['type'] == ContentType.TEXT.value:
                contents.append(TextContent(type=ContentType.TEXT, value=item['value']))
            elif item['type'] == ContentType.IMAGE.value:
                contents.append(ImageContent(type=ContentType.IMAGE, value=item['value']))
            elif item['type'] == ContentType.SUBTITLE.value:
                contents.append(SubtitleContent(type=ContentType.SUBTITLE, value=item['value']))
            else:
                raise ValueError(f"Unknown content type: {item['type']}")

        result = cls(contents)
        result.url = data.get('url')
        result.title = data.get('title')
        result.summary = data.get('summary')
        result.chapters = data.get('chapters', [])
        return result


class ContentsEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Contents):
            return obj.to_dict()
        if isinstance(obj, ContentType):
            return obj.value
        if isinstance(obj, (TextContent, ImageContent, SubtitleContent)):
            return {"type": obj.type.value, "value": obj.value}
        return super().default(obj)

