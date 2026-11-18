
const $ = (id) => document.getElementById(id);

const url = $("youtubeUrl");
const message = $("urlMessage");
const count = $("count");

function validYouTube(value) {
  try {
    const u = new URL(value);
    return [
      "youtube.com",
      "www.youtube.com",
      "m.youtube.com",
      "youtu.be",
      "www.youtu.be",
      "youtube-nocookie.com",
      "www.youtube-nocookie.com"
    ].includes(u.hostname) &&
      (u.hostname.includes("youtu.be")
        ? u.pathname.length > 1
        : u.searchParams.has("v") ||
          u.pathname.startsWith("/shorts/") ||
          u.pathname.startsWith("/embed/"));
  } catch {
    return false;
  }
}

function showMessage(text, color = "#75d9ad") {
  message.textContent = text;
  message.style.color = color;
}

async function apiRequest(endpoint, data) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    throw new Error("Server error: " + response.status);
  }

  return response.json();
}

$("inspectBtn").addEventListener("click", async () => {
  const videoUrl = url.value.trim();

  if (!validYouTube(videoUrl)) {
    return showMessage("Please enter a valid YouTube link.", "#ff858b");
  }

  showMessage("Inspecting video...", "#e6c978");

  try {
    const result = await apiRequest("/api/inspect", {
      youtube_url: videoUrl
    });
    showMessage(result.message);
  } catch (error) {
    showMessage("Cannot connect to backend. Check deployment.", "#ff858b");
  }
});

$("minus").addEventListener("click", () => {
  count.value = Math.max(1, Number(count.value || 3) - 1);
});

$("plus").addEventListener("click", () => {
  count.value = Math.min(10, Number(count.value || 3) + 1);
});

count.addEventListener("change", () => {
  count.value = Math.min(10, Math.max(1, Number(count.value || 3)));
});

document.querySelectorAll(".template").forEach(button => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".template").forEach(item => {
      item.classList.remove("selected");
    });
    button.classList.add("selected");
  });
});

$("generateBtn").addEventListener("click", async () => {
  const videoUrl = url.value.trim();

  if (!validYouTube(videoUrl)) {
    return showMessage("Add a valid YouTube link first.", "#ff858b");
  }

  showMessage("Sending your settings...", "#e6c978");

  try {
    const result = await apiRequest("/api/jobs", {
      youtube_url: videoUrl,
      clip_count: Number(count.value || 3),
      style: $("style")?.value || "Mixed",
      duration_seconds: Number($("duration")?.value || 30),
      aspect_ratio: $("ratio")?.value || "9:16",
      caption_template: document.querySelector(".template.selected")?.textContent.trim() || "Bold Viral",
      font: $("font")?.value || "Inter"
    });

    showMessage(result.message, "#e6c978");
  } catch (error) {
    showMessage("Backend connection failed. Please try again.", "#ff858b");
  }
});
