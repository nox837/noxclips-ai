from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field
from urllib.parse import urlparse, parse_qs

app = FastAPI(title="NoxClips.ai API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ClipRequest(BaseModel):
    youtube_url: HttpUrl
    style: str = "Mixed"
    clip_count: int = Field(default=3, ge=1, le=10)
    duration_seconds: int = Field(default=30, ge=10, le=180)
    aspect_ratio: str = "9:16"
    caption_template: str = "Bold Viral"

def is_youtube(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com"}

@app.get("/health")
def health():
    return {"status": "ok", "app": "NoxClips.ai", "version": "2.0.0"}

@app.post("/api/jobs")
def create_job(request: ClipRequest):
    if not is_youtube(str(request.youtube_url)):
        return {"error": "Only YouTube URLs are supported."}
    # Safe starter: job orchestration is intentionally not connected to a downloader.
    # Add an authorized source/provider for videos the user owns or has permission to process.
    return {
        "status": "backend_not_connected",
        "message": "Request validated. Connect an authorized video source and processing worker to start a real job.",
        "settings": request.model_dump()
    }
