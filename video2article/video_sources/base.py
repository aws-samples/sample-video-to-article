from abc import ABC, abstractmethod

from webvtt import WebVTT
from video2article.utils.config import Config


class VideoSource(ABC):
    @abstractmethod
    def __init__(self, config: Config) -> None:
        pass

    @abstractmethod
    async def load(self) -> None:
        pass

    @abstractmethod
    def get_captions(self) -> WebVTT:
        pass

    @abstractmethod
    def get_thumbnail_ids(self) -> list[int]:
        pass

    @abstractmethod
    def get_title(self) -> str:
        pass
