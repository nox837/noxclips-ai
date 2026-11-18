
import os
import re
import uuid
import zipfile
import shutil
import subprocess
from pathlib import Path

import gradio as gr
from faster_whisper import WhisperModel

WORK = Path("/tmp/noxclips")
WORK.mkdir(exist_ok=True)

MODEL = None


def run(cmd):
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout)[-2500:])
    return p.stdout


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


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def score_segment(text, style):
    t = text.lower()
    words = re.findall(r"\b[\w']+\b", t)
    score = min(len(words), 24) / 24

    score += min(
        t.count("!") * 0.35 + t.count("?") * 0.18,
        1.1
    )

    groups = {
        "Mixed — everything interesting": [
            "wow", "wait", "actually", "secret", "crazy",
            "amazing", "unbelievable", "never", "finally",
            "why", "how", "best", "worst", "surprise",
            "love", "hate", "win", "fail", "truth"
        ],
        "Funny moments": [
            "funny", "laugh", "joke", "haha", "lol",
            "hilarious", "bro", "bruh", "embarrassing", "fail"
        ],
        "Surprising moments": [
            "wow", "wait", "what", "surprise",
            "unexpected", "unbelievable", "secret", "suddenly"
        ],
        "Emotional moments": [
            "love", "miss", "family", "life", "heart",
            "cry", "sorry", "thank", "dream", "hope", "proud"
        ],
        "Exciting moments": [
            "win", "won", "fight", "challenge", "race",
            "fast", "crazy", "insane", "finally", "incredible"
        ]
    }

    for word in groups.get(
        style, groups["Mixed — everything interesting"]
    ):
        if word in t:
            score += 0.22

    if len(words) < 5:
        score -= 0.35
    if len(words) > 8:
        score += 0.12

    return score


def ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def make_ass(segments, start, end, hook, path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,38,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,1,0,1,3,1,2,35,35,110,1
Style: Hook,Arial,48,&H0000FFFF,&H000000FF,&H00000000,&H99000000,1,0,1,4,2,8,35,35,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    rows = []

    if hook:
        rows.append(
            f"Dialogue: 1,0:00:00.00,0:00:02.40,Hook,,0,0,0,,{hook}"
        )

    for seg in segments:
        a = max(0, seg["start"] - start)
        b = min(end - start, seg["end"] - start)

        if b <= a:
            continue

        txt = clean_text(seg["text"])
        txt = txt.replace("{", "").replace("}", "")
        txt = txt.replace("\n", " ")

        if txt:
            rows.append(
                f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{txt}"
            )

    Path(path).write_text(
        header + "\n".join(rows),
        encoding="utf-8"
    )


def process_video(
    video,
    count,
    style,
    template,
    aspect,
    captions,
    progress=gr.Progress()
):
    if not video:
        raise gr.Error("Please upload a video first.")

    source = Path(video)

    if not source.exists():
        raise gr.Error("Uploaded video could not be found.")

    job = WORK / uuid.uuid4().hex
    job.mkdir(parents=True)

    try:
        local = job / ("source" + source.suffix.lower())
        audio = job / "audio.wav"

        progress(0.03, desc="Preparing video")
        shutil.copyfile(source, local)

        probe = run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(local)
        ])

        duration = float(probe.strip())

        if duration < 8:
            raise gr.Error("Video must be at least 8 seconds long.")

        if duration > 600:
            raise gr.Error(
                "For this free server, please use a video shorter than 10 minutes."
            )

        progress(0.08, desc="Extracting audio")

        run([
            "ffmpeg", "-y", "-i", str(local),
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", str(audio)
        ])

        progress(0.12, desc="Loading Whisper AI model")

        model = get_model()

        progress(0.18, desc="Listening for speech")

        segments_iter, info = model.transcribe(
            str(audio),
            beam_size=1,
            best_of=1,
            vad_filter=True,
            condition_on_previous_text=False
        )

        segments = []

        for s in segments_iter:
            txt = clean_text(s.text)

            if txt:
                segments.append({
                    "start": float(s.start),
                    "end": float(s.end),
                    "text": txt
                })

            if s.end:
                progress(
                    min(0.65, 0.18 + (s.end / duration) * 0.47),
                    desc="Analyzing speech"
                )

        if not segments:
            raise gr.Error(
                "No clear speech detected. This version needs spoken audio."
            )

        progress(0.68, desc="Finding interesting moments")

        clip_len = min(25.0, max(12.0, duration / max(2, int(count))))

        candidates = []

        for seg in segments:
            center = (seg["start"] + seg["end"]) / 2
            start = max(
                0,
                min(duration - clip_len, center - clip_len / 2)
            )
            end = min(duration, start + clip_len)

            nearby = [
                x for x in segments
                if x["end"] >= start and x["start"] <= end
            ]

            text = " ".join(x["text"] for x in nearby)
            score = score_segment(text, style)

            speech = sum(
                max(
                    0,
                    min(x["end"], end) - max(x["start"], start)
                )
                for x in nearby
            )

            score += min(speech / max(end - start, 1), 1) * 0.45

            candidates.append((score, start, end, nearby, text))

        candidates.sort(key=lambda x: x[0], reverse=True)

        selected = []

        for candidate in candidates:
            if all(
                abs(candidate[1] - old[1]) > clip_len * 0.65
                for old in selected
            ):
                selected.append(candidate)

            if len(selected) >= int(count):
                break

        if not selected:
            selected = [
                (0, 0, min(duration, clip_len), segments, "")
            ]

        selected.sort(key=lambda x: x[1])

        outputs = []
        total = len(selected)

        for idx, item in enumerate(selected, 1):
            score, start, end, nearby, text = item

            progress(
                0.70 + (idx - 1) / total * 0.27,
                desc=f"Rendering clip {idx} of {total}"
            )

            out = job / f"NoxClip_{idx:02d}.mp4"

            words = re.findall(r"\b[\w']+\b", text)
            hook = " ".join(words[:7]).upper()
            hook = re.sub(r"[^A-Z0-9 '!?.,-]", "", hook)

            vf = []

            if aspect == "9:16 — Shorts / Reels":
                vf.append(
                    "scale=720:1280:force_original_aspect_ratio=increase,"
                    "crop=720:1280,setsar=1"
                )
            elif aspect == "1:1 — Square":
                vf.append(
                    "scale=720:720:force_original_aspect_ratio=increase,"
                    "crop=720:720,setsar=1"
                )
            else:
                vf.append(
                    "scale=1280:720:force_original_aspect_ratio=decrease,"
                    "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1"
                )

            if captions:
                ass = job / f"captions_{idx:02d}.ass"
                make_ass(nearby, start, end, hook, ass)
                vf.append(f"subtitles={ass.as_posix()}")

            run([
                "ffmpeg", "-y",
                "-ss", f"{start:.3f}",
                "-i", str(local),
                "-t", f"{end - start:.3f}",
                "-vf", ",".join(vf),
                "-threads", "1",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-c:a", "aac",
                "-b:a", "96k",
                "-movflags", "+faststart",
                str(out)
            ])

            outputs.append(str(out))

        progress(0.98, desc="Creating download package")

        zip_path = job / "NoxClips_exports.zip"

        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_DEFLATED
        ) as z:
            for output in outputs:
                z.write(output, arcname=Path(output).name)

        progress(1.0, desc="Finished")

        summary = (
            f"Finished {len(outputs)} clips. "
            f"Source duration: {duration / 60:.1f} minutes. "
            "Highlights are selected using transcript-based scoring."
        )

        return outputs, str(zip_path), summary

    except gr.Error:
        shutil.rmtree(job, ignore_errors=True)
        raise

    except Exception as e:
        shutil.rmtree(job, ignore_errors=True)
        raise gr.Error(
            "Processing failed. Try a shorter MP4 video. Details: "
            + str(e)[-1200:]
        )


with gr.Blocks(
    title="NoxClips AI Engine",
    theme=gr.themes.Base(
        primary_hue="rose",
        neutral_hue="slate"
    )
) as demo:

    gr.Markdown(
        "# 🔴 NOXCLIPS AI ENGINE\n"
        "Upload a video and generate short clips. "
        "Free CPU processing can be slow."
    )

    with gr.Row():
        with gr.Column():
            video = gr.Video(
                label="Upload video from gallery",
                sources=["upload"]
            )

            count = gr.Dropdown(
                [5, 6, 7, 8, 9, 10],
                value=5,
                label="Number of clips"
            )

            style = gr.Dropdown(
                [
                    "Mixed — everything interesting",
                    "Funny moments",
                    "Surprising moments",
                    "Emotional moments",
                    "Exciting moments"
                ],
                value="Mixed — everything interesting",
                label="Highlight style"
            )

            template = gr.Dropdown(
                [
                    "Cinematic", "Viral", "Podcast",
                    "Gaming", "Motivation", "Meme / Funny"
                ],
                value="Cinematic",
                label="Template"
            )

            aspect = gr.Dropdown(
                [
                    "9:16 — Shorts / Reels",
                    "1:1 — Square",
                    "16:9 — Landscape"
                ],
                value="9:16 — Shorts / Reels",
                label="Output format"
            )

            captions = gr.Checkbox(
                value=True,
                label="Add captions and opening hook"
            )

            go = gr.Button(
                "⚡ Generate clips",
                variant="primary"
            )

        with gr.Column():
            gallery = gr.Gallery(
                label="Your generated clips",
                columns=2,
                height=420
            )

            download = gr.File(
                label="Download all clips (ZIP)"
            )

            status = gr.Textbox(
                label="Processing result",
                lines=3
            )

    go.click(
        process_video,
        [video, count, style, template, aspect, captions],
        [gallery, download, status]
    )

    gr.Markdown(
        "### Engine information\n"
        "- Whisper Tiny speech recognition\n"
        "- FFmpeg video processing\n"
        "- Transcript-based highlight selection\n"
        "- 720p output to reduce processing load\n"
        "- Free server limits apply; unlimited processing is not guaranteed."
    )


demo.queue(max_size=1).launch(
    server_name="0.0.0.0",
    server_port=7860
)
