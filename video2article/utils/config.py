from typing import Optional, Dict, Any, List
from pathlib import Path
import yaml
from dataclasses import dataclass
from video2article.utils.language import validate_language_code, get_language_name, LANGUAGE_MAPPING
from video2article.utils.constants import OutputFormat, SourceType

@dataclass
class Config:
    video_title: str
    uri: str
    config_path: Path
    project_name: str
    project_folder: Path
    output_format: OutputFormat
    source_language: str | None
    target_language: str
    transcribe_s3_bucket: Optional[str] = None

    def __post_init__(self):
        self._load_settings()
        self._set_source_type()
        
        # Validate and set language codes
        if self.source_language and not validate_language_code(self.source_language):
            available_langs = self.get_available_languages()
            raise ValueError(f"Unsupported source language code: {self.source_language}\nAvailable languages: {', '.join(available_langs)}")
        if not validate_language_code(self.target_language):
            available_langs = self.get_available_languages()
            raise ValueError(f"Unsupported target language code: {self.target_language}\nAvailable languages: {', '.join(available_langs)}")
    
    def _load_settings(self) -> None:
        """Load settings from config.yaml"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.settings = yaml.safe_load(f)
        else:
            self.settings = {}
    
    def _set_source_type(self) -> None:
        """Set source type based on settings"""
        # Only file source is supported
        if self.uri.startswith(('http://', 'https://')):
            raise ValueError("Unsupported URL format. Only local file paths are supported.")
        if self.transcribe_s3_bucket is None:
            raise ValueError("transcribe_s3_bucket is required for local file sources")
        self.source_type = SourceType.FILE

    def get_config_value(self, key_path: str) -> Any:
        """
        Get a configuration value from the settings using a dot-separated key path.
        
        Args:
            key_path: Dot-separated path to the configuration value (e.g., 'processors.transcript_revisor.revise.max_workers')
            
        Returns:
            The configuration value
            
        Raises:
            KeyError: If the configuration value is not found
        """
        keys = key_path.split('.')
        value = self.settings
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                raise KeyError(f"Config value not found in a yaml file: {key_path}")
            value = value[key]
        return value

    def set_source_language(self, language_code: str) -> None:
        """
        Set the source language code
        
        Args:
            language_code: Language code to set
            
        Raises:
            ValueError: If the language code is not supported
        """
        if not validate_language_code(language_code):
            raise ValueError(f"Unsupported source language code: {language_code}")
        self.source_language = language_code

    def get_source_language_name(self) -> str:
        """Get the full name of the source language"""
        if self.source_language is None:
            raise ValueError(f"Source language code is not set")
        name = get_language_name(self.source_language)
        if name is None:
            raise ValueError(f"Invalid source language code: {self.source_language}")
        return name

    def get_target_language_name(self) -> str:
        """Get the full name of the target language"""
        name = get_language_name(self.target_language)
        if name is None:
            raise ValueError(f"Invalid target language code: {self.target_language}")
        return name

    def get_available_languages(self) -> List[str]:
        """Get a list of available language codes and their names"""
        return [f"{code} ({name})" for code, name in LANGUAGE_MAPPING.items()]
