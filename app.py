import os, re, zipfile, tempfile, subprocess, shutil, math
from pathlib import Path
import gradio as gr
from faster_whisper import WhisperModel

WORK = Path("/tmp/noxclips")
WORK.mkdir(exist_ok=True)
MODEL = None

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout)[-3500:])
    return p.stdout

def get_model():
    global MODEL
    if MODEL is None:
        MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
    return MODEL

def clean_text(s):
    return re.sub(r"\s+", " ", s or "").strip()

def score_segment(text, style):
    t = text.lower()
    words = re.findall(r"\b[\w']+\b", t)
    score = min(len(words), 24) / 24
    score += min(t.count("!") * .35 + t.count("?") * .18, 1.1)
    groups = {
      "Mixed — everything interesting": ["wow","wait","actually","secret","crazy","amazing","unbelievable","never","finally","why","how","best","worst","surprise","love","hate","win","fail","problem","truth"],
      "Funny moments": ["funny","laugh","joke","haha","lol"," hilarious","stupid","bro","bruh","embarrassing","fail","😂"],
      "Surprising moments": ["wow","wait","what","surprise","unexpected","unbelievable","secret","actually","never","suddenly"],
      "Emotional moments": ["love","miss","family","life","heart","cry","sorry","thank","dream","hope","proud","remember"],
      "Exciting moments": ["win","won","fight","challenge","race","fast","crazy","insane","let's go","finally","incredible"]
    }
    for word in groups.get(style, groups["Mixed — everything interesting"]):
        if word.strip() and word in t:
            score += .22
    if len(words) < 5: score -= .35
    if len(words) > 8: score += .12
    return score

def ass_time(seconds):
    h=int(seconds//3600); m=int((seconds%3600)//60); s=seconds%60
    return f"{h}:{m:02d}:{s:05.2f}"

def make_ass(segments, start, end, hook, template, path):
    styles = {
      "Cinematic": ("Arial", 58, "&H0000FFFF", "&H00000000", 1),
      "Viral": ("Arial", 64, "&H0000FFFF", "&H00000000", 1),
      "Podcast": ("Arial", 48, "&H00FFFFFF", "&H00000000", 1),
      "Gaming": ("Arial", 58, "&H0000FFFF", "&H00000000", 1),
      "Motivation": ("Arial", 60, "&H00FFFFFF", "&H00000000", 1),
      "Meme / Funny": ("Arial", 62, "&H0000FFFF", "&H00000000", 1),
    }
    font,size,primary,outline,bold=styles.get(template,styles["Cinematic"])
    header=f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},&H000000FF,&H00101010,&H99000000,{bold},0,1,4,2,2,80,80,170,1
Style: Hook,Arial,68,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,1,0,1,5,2,8,70,70,250,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows=[]
    if hook:
        rows.append(f"Dialogue: 1,0:00:00.00,0:00:02.40,Hook,,0,0,0,,{hook}")
    for seg in segments:
        a=max(0,seg["start"]-start); b=min(end-start,seg["end"]-start)
        if b<=a: continue
        txt=clean_text(seg["text"]).replace("{","").replace("}","")
        if txt:
            rows.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{txt}")
    Path(path).write_text(header+"\n".join(rows),encoding="utf-8")

def process_video(video, count, style, template, aspect, captions):
    if not video:
        raise gr.Error("Upload a video first.")
    source=Path(video)
    if not source.exists():
        raise gr.Error("The uploaded video could not be found.")
    job=WORK / next(tempfile._get_candidate_names())
    job.mkdir(parents=True,exist_ok=True)
    local=job / ("source"+source.suffix.lower())
    shutil.copyfile(source,local)
    try:
        probe=run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(local)])
        duration=float(probe.strip())
    except Exception as e:
        raise gr.Error("Could not read this video. Try MP4 or MOV. "+str(e))
    if duration < 8:
        raise gr.Error("Please upload a video at least 8 seconds long.")
    gr.Info("Loading the free speech-recognition model. First run can take a few minutes.")
    model=get_model()
    segments_iter, info=model.transcribe(str(local), beam_size=1, vad_filter=True)
    segments=[]
    for s in segments_iter:
        txt=clean_text(s.text)
        if txt:
            segments.append({"start":float(s.start),"end":float(s.end),"text":txt})
    if not segments:
        raise gr.Error("No clear speech was detected. This first engine needs spoken audio to find highlights.")
    # Candidate windows centered on speech segments; 25-45s depending on source length.
    clip_len=min(40.0,max(18.0,duration/ max(2,int(count))))
    candidates=[]
    for seg in segments:
        center=(seg["start"]+seg["end"])/2
        start=max(0,min(duration-clip_len,center-clip_len/2))
        end=min(duration,start+clip_len)
        if end-start < 8: continue
        nearby=[x for x in segments if x["end"]>=start and x["start"]<=end]
        text=" ".join(x["text"] for x in nearby)
        sc=score_segment(text,style)
        # modest preference for moments with dense speech
        speech=sum(max(0,min(x["end"],end)-max(x["start"],start)) for x in nearby)
        sc += min(speech/(end-start),1)*.45
        candidates.append((sc,start,end,nearby,text))
    candidates.sort(key=lambda x:x[0],reverse=True)
    selected=[]
    for c in candidates:
        if all(abs(c[1]-old[1]) > clip_len*.62 for old in selected):
            selected.append(c)
        if len(selected)>=int(count): break
    if not selected:
        selected=[(0,0,min(duration,clip_len),segments," ".join(x["text"] for x in segments))]
    selected.sort(key=lambda x:x[1])
    outputs=[]
    zip_path=job/"NoxClips_exports.zip"
    for idx,(score,start,end,nearby,text) in enumerate(selected,1):
        out=job/f"NoxClip_{idx:02d}.mp4"
        hook_words=re.findall(r"\b[\w']+\b",text)
        hook=" ".join(hook_words[:7]).upper()
        hook=re.sub(r"[^A-Z0-9 '!?.,-]","",hook)
        ass=job/f"captions_{idx:02d}.ass"
        if captions:
            make_ass(nearby,start,end,hook,template,ass)
        vf=[]
        if aspect=="9:16 — Shorts / Reels":
            vf.append("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920")
        elif aspect=="1:1 — Square":
            vf.append("scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080")
        else:
            vf.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
        if captions:
            vf.append(f"subtitles='{ass.as_posix()}'")
        cmd=["ffmpeg","-y","-ss",f"{start:.3f}","-i",str(local),"-t",f"{end-start:.3f}","-vf",",".join(vf),"-c:v","libx264","-preset","ultrafast","-crf","25","-c:a","aac","-b:a","128k","-movflags","+faststart",str(out)]
        run(cmd)
        outputs.append(str(out))
    with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
        for p in outputs: z.write(p,arcname=Path(p).name)
    summary=f"Finished {len(outputs)} clips from a {duration/60:.1f}-minute video. Speech detected: {len(segments)} transcript segments. Highlight ranking is an early transcript-based heuristic, not a human-level understanding model."
    return outputs,str(zip_path),summary

with gr.Blocks(title="NoxClips AI Engine",theme=gr.themes.Base(primary_hue="rose",neutral_hue="slate")) as demo:
    gr.Markdown("# 🔴 NOXCLIPS AI ENGINE\nUpload a video, choose a style, and generate short vertical clips. **Free CPU processing can be slow; start with a short test video.**")
    with gr.Row():
        with gr.Column(scale=1):
            video=gr.Video(label="Upload video from gallery",sources=["upload"]
            count=gr.Dropdown([5,6,7,8,9,10],value=5,label="Number of clips")
            style=gr.Dropdown(["Mixed — everything interesting","Funny moments","Surprising moments","Emotional moments","Exciting moments"],value="Mixed — everything interesting",label="Highlight style")
            template=gr.Dropdown(["Cinematic","Viral","Podcast","Gaming","Motivation","Meme / Funny"],value="Cinematic",label="Template")
            aspect=gr.Dropdown(["9:16 — Shorts / Reels","1:1 — Square","16:9 — Landscape"],value="9:16 — Shorts / Reels",label="Output format")
            captions=gr.Checkbox(value=True,label="Burn in transcript captions + opening hook")
            go=gr.Button("⚡ Generate clips",variant="primary")
        with gr.Column(scale=1):
            gallery=gr.Gallery(label="Your generated clips",columns=2,height=420)
            download=gr.File(label="Download all clips (ZIP)")
            status=gr.Textbox(label="Processing result",lines=3)
    go.click(process_video,[video,count,style,template,aspect,captions],[gallery,download,status])
    gr.Markdown("### Current engine notes\n- Uses open-source Whisper tiny speech recognition on CPU and FFmpeg for cutting/rendering.\n- Picks candidate moments using transcript-based scoring. This is an early prototype, not perfect semantic AI.\n- Center-crops vertical video; it does not yet track faces or objects.\n- Long videos may take a long time or exceed free Space limits. No unlimited processing promise.")

demo.queue(max_size=2).launch(server_name="0.0.0.0",server_port=7860)
