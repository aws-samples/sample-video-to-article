import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

from video2article.utils.bedrock import create_message
from video2article.utils.constants import (
    MIN_SEGMENT_RATIO,
    OVERLAP_TIME,
    SEGMENT_DURATION,
)
from video2article.utils.types import Contents, ContentType, ImageContent, TextContent
from video2article.utils.config import Config
from webvtt import WebVTT

class TranscriptRevisor:

    def __init__(self, config: Config):
        self.config = config
        self.project_folder = str(config.project_folder)
        self.revise_max_workers = config.get_config_value("processors.transcript_revisor.revise.max_workers")
        self.fix_boundary_max_workers = config.get_config_value("processors.transcript_revisor.fix_paragraph_boundary.max_workers")
        self.revise_model_id = config.get_config_value("processors.transcript_revisor.revise.model_id")
        self.fix_boundary_model_id = config.get_config_value("processors.transcript_revisor.fix_paragraph_boundary.model_id")

    def process(self, captions: WebVTT, thumbnail_contents: dict[int, str], keywords: str) -> Contents:
        logging.info("Starting transcript revision")

        # Revise segments
        segments = self._segment_transcript(captions, thumbnail_contents)
        total_segments = len(segments)
        logging.info(f"Processing {total_segments} segments with {self.revise_max_workers} parallel workers")

        with ThreadPoolExecutor(max_workers=self.revise_max_workers) as executor:
            revised_segments = list(executor.map(
                self._revise_single_segment,
                range(len(segments)),
                segments,
                [thumbnail_contents] * len(segments),
                [keywords] * len(segments)
            ))

        logging.debug(f"Revised segments: {revised_segments}")

        # Fix boundaries between segments
        logging.info("Fixing boundeies between segments")
        final_paragraphs = []

        first_segment_paragraphs = revised_segments[0].split('\n\n')
        final_paragraphs.extend(first_segment_paragraphs)

        boundary_tasks = []
        for i in range(1, len(revised_segments)):
            prev_paragraph = revised_segments[i-1].split('\n\n')[-1]
            current_paragraph = revised_segments[i].split('\n\n')[0]
            boundary_tasks.append((prev_paragraph, current_paragraph))

        with ThreadPoolExecutor(max_workers=self.fix_boundary_max_workers) as executor:
            fixed_boundaries = list(executor.map(
                lambda x: self._fix_paragraph_boundary(x[0], x[1]),
                boundary_tasks
            ))

        for i, (fixed_prev, fixed_current) in enumerate(fixed_boundaries, 1):
            final_paragraphs[-1] = fixed_prev
            current_segment_paragraphs = revised_segments[i].split('\n\n')
            final_paragraphs.extend([fixed_current] + current_segment_paragraphs[1:])

        revised_text = "\n\n".join(final_paragraphs)
        logging.debug(f"Boundary fixed revised text: {revised_text}")

        # Check if all image tags remain after processing
        if not self._are_all_image_tags_included(thumbnail_contents, revised_text):
            raise ValueError("Some image tags were not included in the revised content.")

        paragraphs = revised_text.split('\n\n')

        contents = Contents([TextContent(type=ContentType.TEXT, value=paragraph) for paragraph in paragraphs])
        return contents

    def _revise_single_segment(self, i, segment, thumbnail_contents, keywords):
        logging.info(f"Segment {i+1}: Starting revision")
        start_time = max(0, int(SEGMENT_DURATION * (i-0.5)))
        end_time = int(SEGMENT_DURATION * (i+1+0.2))
        relevant_thumbnail_context = self._get_relevant_thumbnail_context(thumbnail_contents, start_time, end_time)
        logging.debug(f"Segment {i+1}: Using thumbnail from {start_time} to {end_time}.")
        revised_segment = self._revise_segment(segment, relevant_thumbnail_context, keywords)
        logging.info(f"Segment {i+1}: Completed revision")
        return revised_segment

    def _convert_time_to_seconds(self, time_str):
        hours, minutes, seconds = time_str.split(":")
        seconds, milliseconds = seconds.split(".")
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000

    def _segment_transcript(self, captions, thumbnail_contents: dict[int, str]) -> list[str]:
        transcript_segments: list[str] = []
        transcript = ""
        start_time = 0
        thumbnail_index = 0
        sorted_thumbnail_ids = sorted(thumbnail_contents.keys())
        total_duration = self._convert_time_to_seconds(captions[-1].end)

        debug_log = ["Transcript Segmentation Debug Log:"]
        debug_log.append(f"Total duration: {total_duration:.2f}s, Total thumbnails: {len(sorted_thumbnail_ids)}")

        # Insert images before the first caption
        first_caption_start = self._convert_time_to_seconds(captions[0].start)
        while thumbnail_index < len(sorted_thumbnail_ids) and sorted_thumbnail_ids[thumbnail_index] < first_caption_start:
            image_time = sorted_thumbnail_ids[thumbnail_index]
            transcript += f"<image>{image_time}</image> "
            debug_log.append(f"Inserted pre-caption image: <image>{image_time}</image>")
            thumbnail_index += 1

        while start_time < total_duration:
            end_time = start_time + SEGMENT_DURATION
            segment_log = f"\nSegment {len(transcript_segments) + 1}: {start_time:.2f}s - {(end_time+OVERLAP_TIME):.2f}s"

            for caption in captions:
                caption_start = self._convert_time_to_seconds(caption.start)
                caption_end = self._convert_time_to_seconds(caption.end)

                if start_time <= caption_start < (end_time + OVERLAP_TIME):
                    caption_log = f"  Caption ({caption_start:.2f}s - {caption_end:.2f}s): "

                    # Insert images before and within the caption
                    while thumbnail_index < len(sorted_thumbnail_ids) and sorted_thumbnail_ids[thumbnail_index] < caption_end:
                        image_time = sorted_thumbnail_ids[thumbnail_index]
                        transcript += f"<image>{image_time}</image> "
                        caption_log += f"<image>{image_time}</image>  "
                        thumbnail_index += 1

                    c = caption.text.replace('\n', ' ') + " "
                    transcript += c
                    caption_log += f"Text: {c}"
                    segment_log += f"\n{caption_log}"

            # Merge the last segment if it's too short
            if end_time >= total_duration and len(transcript_segments) > 0:
                last_segment_duration = total_duration - start_time
                if last_segment_duration < SEGMENT_DURATION * MIN_SEGMENT_RATIO:
                    segment_log += f"\nMerging last segment (duration: {last_segment_duration:.2f}s) with previous segment"
                    transcript_segments[-1] += " " + transcript
                    break

            debug_log.append(segment_log)

            logging.debug(f"append transcript: {transcript}")

            transcript_segments.append(transcript.strip())
            transcript = ""
            start_time = end_time

        # Add remaining image tags to the last segment
        remaining_images = []
        while thumbnail_index < len(sorted_thumbnail_ids):
            image_time = sorted_thumbnail_ids[thumbnail_index]
            remaining_images.append(f"<image>{image_time}</image>")
            thumbnail_index += 1

        if remaining_images:
            transcript_segments[-1] = transcript_segments[-1].rstrip() + " " + " ".join(remaining_images)
            debug_log.append(f"\nAdded remaining images to last segment: {', '.join(map(str, sorted_thumbnail_ids[thumbnail_index:]))}")

        debug_log.append(f"\nSegmentation complete. Total segments: {len(transcript_segments)}")

        logging.debug("\n".join(debug_log))
        return transcript_segments

    def _get_relevant_thumbnail_context(self, thumbnail_contents: dict[int, str], start_time: int, end_time: int) -> str:
        prompt = ""
        for id, content in thumbnail_contents.items():
            if start_time <= id <= end_time:
                prompt += f'<slide index="{id}">'
                prompt += "<content>"
                prompt += content
                prompt += "</content>"
                prompt += "</slide>"
        return prompt

    def _revise_segment(self, segment, relevant_thumbnail_context, keywords):
        pattern = r'<image>(\d+)</image>'
        image_ids = set(map(int, re.findall(pattern, segment)))

        prompt = f"""You are tasked with revising a segment of a presentation transcript.
Below, you will find:
1. The original transcript segment in <transcript></transcript> tag
2. Information extracted from relevant presentation slides in <slides></slides> and <keywords></keywords> tag

Original transcript segment:
<transcript>
{segment}
</transcript>

Relevant slide information:
<slides>
{relevant_thumbnail_context}
</slides>

Keywords in the presentation slides:
<keywords>
{keywords}
</keywords>

Then, follow ALL THESE instructions carefully:
<instructions>
- Your task is to revise the provided speech-to-text transcript of the presentation video in the <transcript></transcript> tag by leveraging the extracted text and image information from the corresponding presentation slides in the <slides></slides> and <keywords></keywords> tag.
- The transcript may contain errors such as mistranscribed words or missing information, so please cross-reference and supplement the transcript using the text and details available in the slides.
- While it is acceptable to rephrase individual phrases or sentences for clarity, you MUST NOT omit entire phrases or change the order of sentences.
- You MUST NOT summarize or abbreviate the transcript, and you MUST NOT use bullet points, numbered lists, or other structural formatting in your output because your task is simply to revise the transcript.
- For people, companies, feature names, method names, and other proper nouns, you MUST use the exact terms and spellings provided in the slides, if available.
- Please remove any filler words (such as "um," "uh," "like," etc.) and repetitive expressions to improve the clarity and conciseness of the transcript.
- Remove all content within square brackets [ ] from the transcript. This includes audio descriptions (e.g., [music], [laughter]), speaker labels (e.g., [John]), and any other bracketed information. While these may provide context, they must not appear in the final output.
- If the first or last sentence of the segment is cut off mid-sentence due to segmentation, do not create a separate paragraph for it. Instead, include these partial sentences with the adjacent complete paragraph. These incomplete sentences will be properly connected in a subsequent process.
- Divide the text into logical paragraphs to enhance readability, separating them with blank lines. Each paragraph MUST contain at least three sentences and ideally range from 40 to 80 words. Ensure that each paragraph MUST NOT exceed 100 words.
- Except for paragraph breaks, you MUST NOT use any line breaks in your output.
- When editing the presentation transcription, you MUST keep the original speaker's perspective. Rather than using third-person references like "the presenter says," you MUST maintain the natural flow of dialogue as if the speaker(s) were directly expressing their thoughts.
- Do not change the original language of the transcript.
- IMPORTANT: You MUST preserve ALL image tags (e.g. <image>0</image>) in the transcript. Please note that this transcript contains image tags with the following values: {sorted(image_ids)}. These tags represent crucial timing information for image display and MUST remain in their exact original positions within the text. DO NOT move, modify, or remove any image tags under any circumstances.
- In the revised transcript, DO NOT include any sentences generated from information that was on the slides in <slides></slides> but not actually spoken in the original transcript in <transcript></transcript>
- Output the revised transcript in the <result></result> tag without any other tags like <transcript></transcript>.  You MUST NOT output any other text outside of this tag.
</instructions>"""

        messages = [
            {"role": "user", "content": prompt}
        ]

        response = create_message(
            messages=messages,
            system="You are an AI assistant specialized in revising and enhancing transcripts.",
            temperature=0,
            max_tokens=4000,
            model_id=self.revise_model_id
        )

        # Extract the revised segment from the response
        revised_segment = response.split("<result>")[-1].split("</result>")[0].strip()
        return revised_segment

    def _are_all_image_tags_included(self, thumbnail_contents: dict[int, str], revised_content: str) -> bool:
        # Create a set of thumbnail IDs
        thumbnail_ids = set(thumbnail_contents.keys())

        # Extract all image tag IDs from revised_content
        pattern = r'<image>(\d+)</image>'
        content_ids = set(map(int, re.findall(pattern, revised_content)))

        # Calculate the differences
        missing_ids = thumbnail_ids - content_ids
        extra_ids = content_ids - thumbnail_ids

        if missing_ids or extra_ids:
            # Log error information if there's a mismatch
            logging.error(f"Image tag mismatch detected:Thumbnail IDs: {sorted(thumbnail_ids)}, Content IDs: {sorted(content_ids)}, Missing IDs: {sorted(missing_ids)}, Extra IDs: {sorted(extra_ids)}")
            return False

        # Return True if all IDs match
        return True

    def _fix_paragraph_boundary(self, paragraph1: str, paragraph2: str) -> list[str]:
        prompt = f"""
The following paragraphs are transcriptions of spoken content, divided by time segments with some overlap. As a result, there may be unnatural breaks or redundancies at the paragraph boundaries, especially between the last few seconds of the first paragraph and the first few seconds of the second paragraph.
Please read them carefully and follow the instructions below:

<paragraphs>
<paragraph id=1> {paragraph1} </paragraph>
<paragraph id=2> {paragraph2} </paragraph>
</paragraphs>

<instructions>
Step 1. Carefully read both paragraphs, paying special attention to the paragraph boundaries.
Step 2. Identify overlaps or unnatural breaks at the paragraph boundaries. Then, eliminate the redundancies, and properly connect sentences that were cut off mid-thought.
- If necessary, you can move parts of sentences across the paragraph boundaries to make the content more logically coherent, focusing on smoothing the transition between paragraphs.
- DO NOT alter any existing text within the paragraphs beyond addressing overlaps, unnatural breaks, and moving sentences at the paragraph boundaries.
- You MUST preserve ALL <image> tags (e.g., <image>10</image>) in pagraphs. <image> tags are crucial for synchronizing the text with visual elements. Their exact position must be maintained to ensure proper timing. DO NOT modify, or remove any <image> tags under any circumstances.
Step 3. Explain the specific changes you are going to make and briefly describe why you are going to make these adjustments, with particular emphasis on how you handled the transition between paragraphs in <thinking> tag
Step 4. Output the TWO revised paragraphs in the following format in <result> tag:

<result>
<paragraph id=1> revised paragraph 1 </paragraph>
<paragraph id=2> revised paragraph 2 </paragraph>
</result>

</instructions>
"""

        response = create_message(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4000,
            stop_sequences=[],
            model_id=self.fix_boundary_model_id
        )
        result = response.split("<result>")[1].split("</result>")[0].strip()
        thinking = response.split('<thinking>')[1].split('</thinking>')[0].strip()
        p1 = result.split('<paragraph id=1>')[1].split('</paragraph>')[0].strip()
        p2 = result.split('<paragraph id=2>')[1].split('</paragraph>')[0].strip()
        logging.debug(f"_fix_paragraph_boundary() Thinking: {thinking}")
        logging.debug(f"_fix_paragraph_boundary() Priginal paragraphs:\n{paragraph1}\n{paragraph2}")
        logging.debug(f"_fix_paragraph_boundary() Fixed paragraphs:\n{p1}\n{p2}")
        return [p1, p2]

