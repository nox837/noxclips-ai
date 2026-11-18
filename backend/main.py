
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="NoxClips.ai API",
    version="2.1.0"
)


def is_youtube(url: str) -> bool:
    host = urlparse(url).hostname or ""
    allowed = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com"
    }

    if host not in allowed:
        return False

    parsed = urlparse(url)

    if host.endswith("youtu.be"):
        return len(parsed.path.strip("/")) > 0

    return (
        bool(parsed.query and "v=" in parsed.query)
        or parsed.path.startswith("/shorts/")
        or parsed.path.startswith("/embed/")
    )


class InspectRequest(BaseModel):
    youtube_url: HttpUrl



class ClipRequest(BaseModel):
    youtube_url: HttpUrl
    style: str = "Mixed"
    clip_count: int = Field(default=3, ge=1, le=10)
    duration_seconds: int = Field(default=30, ge=10, le=180)
    aspect_ratio: str = "9:16"
    caption_template: str = "Bold Viral"
    font: str = "Inter"
    caption_position: str = "Bottom"
    
    youtube_url: HttpUrl
    style: str = "Mixed"
    clip_count: int = Field(default=3, ge=1, le=10)
    duration_seconds: int = Field(default=30, ge=10, le=180)
    aspect_ratio: str = "9:16"
    caption_template: str = "Bold Viral"
    font: str = "Inter"


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "NoxClips.ai",
        "version": "2.1.0"
    }


@app.post("/api/inspect")
def inspect_video(request: InspectRequest):
    url = str(request.youtube_url)

    if not is_youtube(url):
        return {
            "status": "error",
            "message": "Please provide a valid YouTube video URL."
        }

    return {
        "status": "accepted",
        "message": "YouTube link format is valid. Video inspection requires an authorized video provider."
    }


@app.post("/api/jobs")
def create_job(request: ClipRequest):
    url = str(request.youtube_url)

    if not is_youtube(url):
        return {
            "status": "error",
            "message": "Only supported YouTube URLs are accepted."
        }

    return {
        "status": "processor_not_configured",
        "message": (
            "Your settings reached the NoxClips backend successfully. "
            "Connect an authorized video-processing provider to generate clips."
        ),
        "settings": request.model_dump()
    }


if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend"
    )
