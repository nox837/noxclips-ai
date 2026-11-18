
import os
import re
import math
import shutil
import zipfile
import subprocess
import tempfile
from pathlib import Path

import gradio as gr
from faster_whisper import WhisperModel

APP_DIR = Path("/tmp/noxclips")
APP_DIR.mkdir(exist_ok=True)

MODEL = None

# Words and phrases that can indicate interesting moments.
INTEREST_WORDS = {
    "wow", "crazy", "insane", "unbelievable", "amazing", "shocking",
    "secret", "truth", "mistake", "never", "always", "impossible",
    "money", "win", "lose", "fight", "love", "hate", "funny",
    "problem", "danger", "fail", "success", "surprise", "actually",
    "seriously", "wait", "why", "how", "because", "remember"
}


def get_model():
    global MODEL
    if MODEL is None:
        MODEL = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8",
            cpu_threads=2,
            num_workers=1
        )
    return MODEL


def run_command(command):
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2500:])
    return result


def get_duration(video):
    result = run_command([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video)
    ])
    return float(result.stdout.strip())


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def transcribe(video):
    model = get_model()
    segments, info = model.transcribe(
        str(video),
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False
    )

    output = []
    for segment in segments:
        text = clean_text(segment.text)
        if text:
            output.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "text": text
            })

    return output


def score_window(segments, start, end):
    selected = [
        s for s in segments
        if s["end"] > start and s["start"] < end
    ]

    if not selected:
        return 0, ""

    words = " ".join(s["text"] for s in selected)
    tokens = re.findall(r"\b[\w']+\b", words.lower())
    count = len(tokens)

    if count < 12:
        return 0, words

    unique_ratio = len(set(tokens)) / max(count, 1)
    interesting = sum(1 for word in tokens if word in INTEREST_WORDS)
    questions = words.count("?")
    exclamations = words.count("!")
    sentence_count = max(1, len(selected))

    coverage = sum(
        max(0, min(s["end"], end) - max(s["start"], start))
        for s in selected
    )
    speech_density = min(1.0, coverage / max(end - start, 1))

    # A practical transcript-based score, not a guarantee of virality.
    score = (
        min(count / 90, 1.5) * 2.0
        + unique_ratio * 2.0
        + interesting * 0.65
        + questions * 0.8
        + exclamations * 0.5
        + min(sentence_count / 8, 1.0)
        + speech_density * 2.0
    )

    return score, words


def find_highlights(segments, duration, wanted, clip_length):
    clip_length = min(float(clip_length), duration)
    if clip_length < 8:
        raise ValueError("The video is too short to create clips.")

    step = max(2.5, clip_length * 0.18)
    candidates = []

    start = 0.0
    while start + 8 < duration:
        end = min(start + clip_length, duration)
        score, transcript = score_window(segments, start, end)

        if score > 0:
            candidates.append({
                "start": start,
                "end": end,
                "score": score,
                "transcript": transcript
            })

        start += step

    if not candidates:
        raise ValueError(
            "I couldn't find enough clear speech. Try a video with more talking."
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)

    chosen = []
    minimum_gap = clip_length * 0.70

    for candidate in candidates:
        if all(
            abs(candidate["start"] - item["start"]) >= minimum_gap
            for item in chosen
        ):
            chosen.append(candidate)

        if len(chosen) >= wanted:
            break

    # Fill remaining slots if the video has fewer separated moments.
    if len(chosen) < wanted:
        for candidate in candidates:
            if candidate not in chosen:
                chosen.append(candidate)
            if len(chosen) >= wanted:
                break

    return sorted(chosen[:wanted], key=lambda x: x["start"])


def ass_time(seconds):
    seconds = max(0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def ass_escape(text):
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", " ")
    )


def make_subtitles(segments, clip, output_path, vertical):
    font_size = 52 if vertical else 34
    margin = 100 if vertical else 45

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial,{font_size},&H00FFFFFF,&H0000FFFF,"
        "&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,"
        f"50,50,{margin},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text"
    ]

    for segment in segments:
        start = max(segment["start"], clip["start"])
        end = min(segment["end"], clip["end"])

        if end <= start:
            continue

        text = ass_escape(segment["text"])
        lines.append(
            f"Dialogue: 0,{ass_time(start - clip['start'])},"
            f"{ass_time(end - clip['start'])},Default,,0,0,0,,{text}"
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def make_clip(video, clip, segments, index, aspect, captions):
    folder = APP_DIR / "results"
    folder.mkdir(exist_ok=True)

    output = folder / f"NoxClips_{index:02d}.mp4"
    subtitle_file = folder / f"captions_{index:02d}.ass"

    vertical = aspect == "9:16"

    if aspect == "9:16":
        width, height = 720, 1280
    elif aspect == "1:1":
        width, height = 1080, 1080
    else:
        width, height = 1280, 720

    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        "setsar=1"
    ]

    if captions:
        make_subtitles(segments, clip, subtitle_file, vertical)
        filters.append(f"subtitles={subtitle_file}")

    command = [
        "ffmpeg", "-y",
        "-ss", str(clip["start"]),
        "-i", str(video),
        "-t", str(clip["end"] - clip["start"]),
        "-vf", ",".join(filters),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "27",
        "-threads", "2",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output)
    ]

    run_command(command)
    return output


def make_title(transcript):
    words = clean_text(transcript).split()
    if not words:
        return "Interesting moment"

    # Use the opening phrase as a simple clip label.
    title = " ".join(words[:9])
    if len(words) > 9:
        title += "..."
    return title


def create_clips(video, number, clip_length, aspect, captions):
    if not video:
        raise gr.Error("Upload a video first.")

    video_path = Path(video)
    if not video_path.exists():
        raise gr.Error("The uploaded video could not be found.")

    result_folder = APP_DIR / "results"
    if result_folder.exists():
        shutil.rmtree(result_folder)
    result_folder.mkdir(parents=True)

    try:
        duration = get_duration(video_path)

        yield [], None, "🎧 Reading the video and finding interesting moments..."

        segments = transcribe(video_path)

        if not segments:
            raise ValueError("No speech was detected in this video.")

        yield [], None, "🧠 Scoring different moments in the video..."

        highlights = find_highlights(
            segments,
            duration,
            int(number),
            int(clip_length)
        )

        gallery = []
        clip_files = []

        for index, clip in enumerate(highlights, 1):
            yield (
                gallery,
                None,
                f"✂️ Creating clip {index} of {len(highlights)}..."
            )

            output = make_clip(
                video_path,
                clip,
                segments,
                index,
                aspect,
                captions
            )

            clip_files.append(output)
            title = make_title(clip["transcript"])
            gallery.append((str(output), f"Clip {index}: {title}"))

        zip_path = APP_DIR / "NoxClips_Export.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in clip_files:
                archive.write(file, arcname=file.name)

        yield (
            gallery,
            str(zip_path),
            f"✅ Finished! Created {len(clip_files)} clips. "
            "Download the ZIP to save them."
        )

    except Exception as error:
        raise gr.Error(f"NoxClips error: {error}")


with gr.Blocks(
    theme=gr.themes.Soft(primary_hue="violet", neutral_hue="slate"),
    title="NoxClips AI"
) as app:

    gr.Markdown(
        """
        # ⚡ NOXCLIPS AI
        ### Turn long videos into short highlights.

        Upload a video. NoxClips analyses the speech, ranks possible moments,
        and creates separate MP4 clips.
        """
    )

    with gr.Row():
        with gr.Column():
            video = gr.Video(
                label="Upload video from your phone gallery",
                sources=["upload"],
                type="filepath"
            )

            number = gr.Slider(
                minimum=5,
                maximum=10,
                value=5,
                step=1,
                label="Number of clips"
            )

            clip_length = gr.Slider(
                minimum=15,
                maximum=60,
                value=30,
                step=5,
                label="Clip length in seconds"
            )

            aspect = gr.Radio(
                choices=["9:16", "1:1", "16:9"],
                value="9:16",
                label="Video format"
            )

            captions = gr.Checkbox(
                value=True,
                label="Burn subtitles into clips"
            )

            create = gr.Button(
                "⚡ CREATE MY CLIPS",
                variant="primary",
                size="lg"
            )

        with gr.Column():
            status = gr.Textbox(
                label="Progress",
                value="Ready. Upload a video to begin.",
                interactive=False
            )

            gallery = gr.Gallery(
                label="Your finished clips",
                columns=1,
                height=500,
                object_fit="contain"
            )

            download = gr.File(label="Download all clips (ZIP)")

    create.click(
        fn=create_clips,
        inputs=[video, number, clip_length, aspect, captions],
        outputs=[gallery, download, status]
    )

    gr.Markdown(
        """
        ---
        **NoxClips note:** Highlight selection uses speech transcription
        and scoring heuristics. It is not a guarantee of viral moments.
        Vertical clips preserve the full frame with padding; automatic
        face tracking is not included yet. Processing speed depends on
        the free server's available resources.
        """
    )


if __name__ == "__main__":
    app.queue().launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
