from enum import Enum

SEGMENT_DURATION = 300 # Duration of each segment in seconds
OVERLAP_TIME =  5  # Overlap time between segments in seconds
MIN_SEGMENT_RATIO = 0.3  # Minimum ratio of segment length to be considered valid
THUMBNAIL_INTERVAL = 10 # Interval between thumbnail extractions in seconds

class OutputFormat(Enum):
    PDF = 'pdf'

class SourceType(Enum):
    FILE = "file"

