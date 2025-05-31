import logging
import os
import json
from typing import Literal

class JSONFormatter(logging.Formatter):
    """JSON formatter for log output"""
    def __init__(self, uri: str):
        super().__init__()
        self.uri = uri

    def format(self, record):
        log_data = {
            'uri': self.uri,
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage()
        }
        if record.exc_info:
            log_data['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logging(uri:str, output_dir: str, environment: Literal['dev', 'prod'] = 'dev') -> None:
    """
    Configure logging based on environment
    
    Args:
        output_dir: output directory for log file
        environment: 'dev' or 'prod'
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    if environment == 'dev':
        # Development environment settings
        log_file = os.path.join(output_dir, 'app.log')

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    else:
        # Production environment settings
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        json_formatter = JSONFormatter(uri)
        console_handler.setFormatter(json_formatter)
        logger.addHandler(console_handler)

    # Set log levels for third-party libraries
    noisy_loggers = [
        'botocore', 'urllib3', 'weasyprint', 'fontTools',
        'fontTools.subset', 'fontTools.ttLib', 'fontTools.subset.timer',
        'pyppeteer', 'websockets', 'asyncio', 's3transfer', 'boto3', 'PIL.PngImagePlugin'
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
