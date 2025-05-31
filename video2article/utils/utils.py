import json
import os
import re


def file_exists(filepath):
    """Check if a file exists."""
    return os.path.exists(filepath)

def save_json(data, filepath):
    """Save data as JSON to the specified filepath."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(filepath):
    """Load JSON data from the specified filepath."""
    with open(filepath, encoding='utf-8') as f:
        return json.load(f)

def get_id_from_thumbnail_path(path):
    """Extract the thumbnail ID from the thumbnail path."""
    thumbnail_match = re.search(r'thumbnail_(\d+)', path)
    if thumbnail_match:
        thumbnail_number = thumbnail_match.group(1)
        return int(thumbnail_number)
    else:
        raise ValueError(f"Thumbnail number not found in {path}")

def get_path_from_thumbnail_id(project_folder, id):
    """Get the thumbnail path from the project folder and thumbnail ID."""
    thumbnail_folder = os.path.join(project_folder, "thumbnails")
    thumbnail_path = os.path.join(thumbnail_folder, f"thumbnail_{id}.jpg")
    return thumbnail_path

