const $ = (id) => document.getElementById(id);
const url = $("youtubeUrl"), message = $("urlMessage"), count = $("count");
function validYouTube(value) {
  try { const u = new URL(value); return ["youtube.com","www.youtube.com","m.youtube.com","youtu.be","www.youtube-nocookie.com"].includes(u.hostname) && (u.hostname.includes("youtu.be") ? u.pathname.length > 1 : u.searchParams.has("v") || u.pathname.startsWith("/shorts/") || u.pathname.startsWith("/embed/")); }
  catch { return false; }
}
$("inspectBtn").addEventListener("click", () => {
  if (!validYouTube(url.value.trim())) { message.textContent = "Please enter a valid YouTube video link."; message.style.color = "#ff858b"; return; }
  message.textContent = "Link format looks valid. Video inspection needs the backend to be connected.";
  message.style.color = "#75d9ad";
});
$("minus").addEventListener("click", () => count.value = Math.max(1, Number(count.value || 3) - 1));
$("plus").addEventListener("click", () => count.value = Math.min(10, Number(count.value || 3) + 1));
count.addEventListener("change", () => count.value = Math.min(10, Math.max(1, Number(count.value || 3))));
document.querySelectorAll(".template").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".template").forEach(item => item.classList.remove("selected"));
  button.classList.add("selected");
}));
$("generateBtn").addEventListener("click", () => {
  if (!validYouTube(url.value.trim())) { message.textContent = "Add a valid YouTube link first."; message.style.color = "#ff858b"; return; }
  message.textContent = "The interface is ready. Connect the authorized video-processing backend to generate clips.";
  message.style.color = "#e6c978";
});
