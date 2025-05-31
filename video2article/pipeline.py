import logging
import os
import time
from pathlib import Path
from typing import Union

from video2article.document_generators.pdf_generator import PDFGenerator
from video2article.processors.image_tag_parser import ImageTagParser
from video2article.processors.important_thumbnail_filter import ImportantThumbnailFilter
from video2article.processors.thumbnail_content_extractor import ThumbnailContentExtractor
from video2article.processors.transcript_revisor import TranscriptRevisor
from video2article.processors.transcript_translator import TranscriptTranslator
from video2article.processors.content_organizer import ContentOrganizer
from video2article.utils.config import Config
from video2article.utils.language import should_translate
from video2article.video_sources.file_source import FileSource
from video2article.utils.logging import setup_logging


class Pipeline:
    def __init__(self, config: Config):
        self.config = config
        self.project_folder = str(config.project_folder)
        # Create project folder if it does not exist
        os.makedirs(self.project_folder, exist_ok=True)

        # Only FileSource is supported
        self.video_source: FileSource = FileSource(config)

        # Initialize processors
        self.important_thumbnail_filter = ImportantThumbnailFilter(config)
        self.thumbnail_content_extractor = ThumbnailContentExtractor(config)
        self.revisor = TranscriptRevisor(config)
        self.translator = TranscriptTranslator(config)
        self.image_tag_parser = ImageTagParser(config)
        self.content_organizer = ContentOrganizer(config)

        # Initialize PDF generator
        self.pdf_generator = PDFGenerator(config)

    async def process(self) -> None:
        setup_logging(self.config.project_name, str(self.config.project_folder), 'dev')
        # Process video
        logging.info(f"Starting video processing for project: {self.config.project_name}")
        logging.info(f"Config: {self.config}")

        start_time = time.time()

        # Load video source
        await self.video_source.load()
        logging.info("Video source loaded successfully")

        # Extract and process thumbnails
        thumbnail_ids = self.important_thumbnail_filter.process(self.video_source.get_thumbnail_ids())
        logging.info("Important thumbnails filtered successfully")
        thumbnail_contents, keywords = self.thumbnail_content_extractor.process(thumbnail_ids)
        logging.info("Thumbnail content extracted successfully ")

        # Revise transcript
        revised_contents = self.revisor.process(self.video_source.get_captions(), thumbnail_contents, keywords)
        logging.info("Transcript revised successfully")

        # Translate transcript if needed
        if not self.config.source_language:
            raise ValueError("Source language is not set")
        if should_translate(self.config.source_language, self.config.target_language):
            translated_contents = self.translator.process(revised_contents, thumbnail_contents, keywords)
            logging.info("Transcript translated successfully")
        else:
            translated_contents = revised_contents
            logging.info("Skipping translation as source and target languages are the same")

        # Parse thumbnail tags
        translated_output_contents = self.image_tag_parser.process(translated_contents)

        # Organize content (summary and chapters)
        translated_output_contents = self.content_organizer.process(translated_output_contents)

        # Save processed contents
        translated_output_contents.add_url(self.config.uri)
        translated_output_contents.add_title(self.video_source.get_title())
        translated_output_contents.save(os.path.join(self.project_folder, "output_contents.json"))

        # Generate PDF document
        self.pdf_generator.generate_document(self.config.project_name, translated_output_contents)
        logging.info("PDF document generated successfully")

        end_time = time.time()
        logging.info(f"Video processing completed: {int(end_time - start_time):d} seconds")
