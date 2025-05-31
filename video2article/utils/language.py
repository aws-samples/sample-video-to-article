from typing import Literal, Optional, Dict, List
import re

# Supported language codes
LanguageCode = Literal['en', 'zh-CN', 'es', 'ar', 'hi', 'fr', 'ja', 'pt', 'ru', 'de']

# Language code to full name mapping
LANGUAGE_MAPPING = {
    'en': 'English',
    'zh-CN': 'Chinese (Simplified)',
    'es': 'Spanish',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'fr': 'French',
    'ja': 'Japanese',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'de': 'German',
    'kr': 'Korean'
}

# Character count ratios for different languages (compared to English)
# These values are approximate and may need adjustment
CHARACTER_RATIOS = {
    'en': 1.0,    # English (base)
    'zh-CN': 0.5, # Chinese (Simplified)
    'es': 1.2,    # Spanish
    'ar': 1.1,    # Arabic
    'hi': 1.1,    # Hindi
    'fr': 1.1,    # French
    'ja': 0.7,    # Japanese
    'pt': 1.2,    # Portuguese
    'ru': 1.1,    # Russian
    'de': 1.1,    # German
    'kr': 1.1     # Korean
}

# Sentence ending patterns for different languages
SENTENCE_ENDINGS = {
    'en': r'[.!?]',
    'zh-CN': r'[。！？]',
    'es': r'[.!?]',
    'ar': r'[.!؟]',
    'hi': r'[.!?]',
    'fr': r'[.!?]',
    'ja': r'[。！？]',
    'pt': r'[.!?]',
    'ru': r'[.!?]',
    'de': r'[.!?]',
    'kr': r'[.!?]'
}

# Transcribe language code to internal language code mapping
TRANSCRIBE_TO_INTERNAL = {
    'en-US': 'en',
    'en-GB': 'en',
    'en-AU': 'en',
    'en-IN': 'en',
    'en-IE': 'en',
    'en-AB': 'en',
    'en-WL': 'en',
    'en-ZA': 'en',
    'en-NZ': 'en',
    'ja-JP': 'ja',
    'zh-CN': 'zh-CN',
    'zh-TW': 'zh-CN',
    'es-ES': 'es',
    'es-US': 'es',
    'ar-AE': 'ar',
    'ar-SA': 'ar',
    'hi-IN': 'hi',
    'fr-FR': 'fr',
    'fr-CA': 'fr',
    'pt-BR': 'pt',
    'pt-PT': 'pt',
    'ru-RU': 'ru',
    'de-DE': 'de',
    'de-CH': 'de',
    'kr-KR': 'kr'
}

def validate_language_code(code: str) -> bool:
    """
    Validate if the given language code is supported
    
    Args:
        code: Language code to validate
        
    Returns:
        bool: True if the code is supported, False otherwise
    """
    return code in LANGUAGE_MAPPING

def get_language_name(code: str) -> Optional[str]:
    """
    Get the full name of a language from its code
    
    Args:
        code: Language code
        
    Returns:
        Optional[str]: Full name of the language if code is valid, None otherwise
    """
    if not code:
        return "Undefined"
    return LANGUAGE_MAPPING.get(code)

def should_translate(source_lang: str, target_lang: str) -> bool:
    """
    Determine if translation is needed between source and target languages
    
    Args:
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        bool: True if translation is needed, False otherwise
    """
    return source_lang != target_lang

def get_character_ratio(language: str) -> float:
    """
    Get the character ratio for a given language compared to English
    
    Args:
        language: Language code
        
    Returns:
        float: Character ratio for the language
    """
    return CHARACTER_RATIOS.get(language, 1.0)

def adjust_text_length(text: str, source_lang: str, target_lang: str) -> str:
    """
    Adjust text length based on language-specific character ratios
    
    Args:
        text: Text to adjust
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        str: Adjusted text
    """
    source_ratio = get_character_ratio(source_lang)
    target_ratio = get_character_ratio(target_lang)
    
    # Calculate target length based on ratios
    target_length = len(text) * (source_ratio / target_ratio)
    
    # For now, just return the original text
    # TODO: Implement actual text length adjustment
    return text

def split_sentences(text: str, language: str) -> List[str]:
    """
    Split text into sentences based on language-specific patterns
    
    Args:
        text: Text to split
        language: Language code
        
    Returns:
        List[str]: List of sentences
    """
    pattern = SENTENCE_ENDINGS.get(language, r'[.!?]')
    sentences = re.split(f'({pattern}\\s+)', text)
    
    # Combine the sentence endings with their sentences
    result = []
    for i in range(0, len(sentences)-1, 2):
        if i+1 < len(sentences):
            result.append(sentences[i] + sentences[i+1])
        else:
            result.append(sentences[i])
    
    return result

def map_transcribe_language(transcribe_code: str) -> str:
    """
    Map Transcribe language code to internal language code
    
    Args:
        transcribe_code: Transcribe language code (e.g., 'en-US', 'ja-JP')
        
    Returns:
        str: Internal language code (e.g., 'en', 'ja')
        
    Raises:
        ValueError: If the language is not supported
    """
    internal_code = TRANSCRIBE_TO_INTERNAL.get(transcribe_code)
    if internal_code is None:
        raise ValueError(f"Unsupported language detected: {transcribe_code}. Supported languages are: {', '.join(TRANSCRIBE_TO_INTERNAL.keys())}")
    return internal_code 