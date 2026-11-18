const input=document.getElementById('videoInput');
const video=document.getElementById('videoPreview');
const placeholder=document.getElementById('previewPlaceholder');
const fileInfo=document.getElementById('fileInfo');
const dropzone=document.getElementById('dropzone');
const toast=document.getElementById('toast');
let objectUrl=null;
function notify(message){toast.textContent=message;toast.classList.add('show');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>toast.classList.remove('show'),2600)}
function formatBytes(bytes){if(!bytes)return '0 B';const units=['B','KB','MB','GB'];let i=0,n=bytes;while(n>=1024&&i<3){n/=1024;i++}return `${n.toFixed(i?1:0)} ${units[i]}`}
input.addEventListener('change',()=>{
 const file=input.files&&input.files[0];if(!file)return;
 if(!file.type.startsWith('video/')){notify('Please choose a video file.');input.value='';return}
 if(objectUrl)URL.revokeObjectURL(objectUrl);
 objectUrl=URL.createObjectURL(file);video.src=objectUrl;video.classList.remove('hidden');placeholder.classList.add('hidden');
 document.getElementById('captionSample').classList.remove('hidden');
 document.getElementById('fileName').textContent=file.name;
 document.getElementById('fileMeta').textContent=`${formatBytes(file.size)} · Loading video details…`;
 fileInfo.classList.remove('hidden');dropzone.classList.add('hidden');
 video.onloadedmetadata=()=>{const d=video.duration;const mins=Math.floor(d/60),secs=Math.floor(d%60);document.getElementById('fileMeta').textContent=`${formatBytes(file.size)} · ${mins}:${String(secs).padStart(2,'0')} · Ready to preview`};
 notify('Video loaded locally. Choose a template!');
});
document.getElementById('removeVideo').addEventListener('click',()=>{if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;video.pause();video.removeAttribute('src');video.load();video.classList.add('hidden');placeholder.classList.remove('hidden');fileInfo.classList.add('hidden');dropzone.classList.remove('hidden');input.value='';});
const names={cinematic:'Cinematic',viral:'Viral',podcast:'Podcast',gaming:'Gaming',motivation:'Motivation',meme:'Meme / Funny'};
document.querySelectorAll('.template').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.template').forEach(x=>x.classList.remove('active'));btn.classList.add('active');const name=names[btn.dataset.template];document.getElementById('selectedTemplate').textContent=name;document.getElementById('previewTemplate').textContent=name;const samples={cinematic:'MAKE EVERY<br>MOMENT COUNT.',viral:'WAIT FOR IT!<br>🔥',podcast:'REAL TALK<br>NO FILTER.',gaming:'GAME ON<br>LEVEL UP',motivation:'NO EXCUSES<br>KEEP GOING',meme:'BRUH 💀<br>WHAT?!'};document.getElementById('captionSample').innerHTML=samples[btn.dataset.template];notify(`${name} template selected`)}));
document.getElementById('createBtn').addEventListener('click',()=>{if(!input.files.length){notify('Upload a video first.');return}notify('Your video is ready. AI clipping engine is the next build stage.');document.getElementById('createNote').textContent='Upload and template selection work. Automatic highlight detection, speech-to-text captions, rendering and publishing still need a processing backend and account integrations.'});
document.getElementById('resetBtn').addEventListener('click',()=>{document.getElementById('removeVideo').click();document.querySelector('[data-template="cinematic"]').click();document.getElementById('highlightStyle').selectedIndex=0;document.getElementById('clipCount').value='7';document.getElementById('aspect').selectedIndex=0;document.getElementById('captionStyle').selectedIndex=0;notify('Project reset')});
['dragenter','dragover'].forEach(ev=>dropzone.addEventListener(ev,e=>{e.preventDefault();dropzone.style.borderColor='#f12b35'}));
['dragleave','drop'].forEach(ev=>dropzone.addEventListener(ev,e=>{e.preventDefault();dropzone.style.borderColor=''}));
dropzone.addEventListener('drop',e=>{const f=e.dataTransfer.files[0];if(f){const dt=new DataTransfer();dt.items.add(f);input.files=dt.files;input.dispatchEvent(new Event('change'))}});
