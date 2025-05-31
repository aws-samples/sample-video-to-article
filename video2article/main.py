import os
from datetime import datetime
from pathlib import Path

from video2article.pipeline import Pipeline
from video2article.utils.constants import OutputFormat
from video2article.utils.config import Config


async def process_video(config: Config) -> None:
    """
    Process a video file and output results to the specified directory
    
    Args:
        config: Config object containing all necessary settings
    """
    pipeline = Pipeline(config)
    await pipeline.process()

async def main():
    # Get all required environment variables
    env_vars = {
        'VIDEO_TITLE': os.getenv('VIDEO_TITLE'),
        'VIDEO_PATH': os.getenv('VIDEO_PATH'),
        'OUTPUT_DIR': os.getenv('OUTPUT_DIR'),
        'CONFIG_PATH': os.getenv('CONFIG_PATH'),
        'OUTPUT_FORMAT': os.getenv('OUTPUT_FORMAT'),
        'TRANSCRIBE_S3_BUCKET': os.getenv('TRANSCRIBE_S3_BUCKET'),
        'TARGET_LANGUAGE': os.getenv('TARGET_LANGUAGE'),
    }
    
    required_vars = {k: v for k, v in env_vars.items() 
                    if k not in ['TRANSCRIBE_S3_BUCKET']}
    missing_vars = [k for k, v in required_vars.items() if not v]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    # Validate output format
    if env_vars['OUTPUT_FORMAT'] not in ['pdf']:
        raise ValueError("OUTPUT_FORMAT must be either 'pdf'")
    
    # Generate project name
    current_time = datetime.now().strftime("%Y%m%d%H%M")
    video_stem = Path(env_vars['VIDEO_PATH']).stem[:16] if not env_vars['VIDEO_PATH'].startswith(('http://', 'https://')) else env_vars['VIDEO_PATH'].split('/')[-1][:10]
    project_name = f"{current_time}-{video_stem}"
    project_folder = Path(env_vars['OUTPUT_DIR']) / project_name
    
    # Create Config
    config = Config(
        video_title=env_vars['VIDEO_TITLE'],
        uri=env_vars['VIDEO_PATH'],
        project_name=project_name,
        project_folder=project_folder,
        output_format=OutputFormat[env_vars['OUTPUT_FORMAT'].upper()],
        config_path=Path(env_vars['CONFIG_PATH']),
        transcribe_s3_bucket=env_vars['TRANSCRIBE_S3_BUCKET'],
        source_language=None,
        target_language=env_vars['TARGET_LANGUAGE'],
    )
    
    try:
        await process_video(
            config=config
        )
        print("Processing completed successfully.")
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

