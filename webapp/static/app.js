// Container Damage Detection - Web UI logic.
// Mirrors gui/main_window.py: model load, per-stage params, image/video/
// webcam flows, damage alert popups, save/record.
(() => {
  const sessionId = crypto.randomUUID();

  const $ = (id) => document.getElementById(id);
  const canvas = $("display");
  const ctx = canvas.getContext("2d");
  const emptyHint = $("empty-hint");
  const statusLabel = $("status-label");
  const modelInfo = $("model-info");
  const resultsList = $("results-list");
  const fpsLabel = $("fps-label");

  const btnStop = $("btn-stop");
  const btnSave = $("btn-save");
  const btnRecord = $("btn-record");
  const btnWebcam = $("btn-webcam");

  let hasModel = false;
  let mode = null; // null | 'image' | 'video' | 'webcam'
  let lastImageFile = null;
  let activeSocket = null;
  let webcamStream = null;
  let webcamTimer = null;
  const hiddenVideo = document.createElement("video");
  const grabCanvas = document.createElement("canvas");

  let mediaRecorder = null;
  let recordedChunks = [];

  // ---------------------------------------------------------------- canvas
  function setStatus(text) { statusLabel.textContent = text; }

  function drawImageContain(img) {
    emptyHint.style.display = "none";
    const cw = canvas.width, ch = canvas.height;
    ctx.fillStyle = "#202020";
    ctx.fillRect(0, 0, cw, ch);
    const scale = Math.min(cw / img.width, ch / img.height);
    const w = img.width * scale, h = img.height * scale;
    ctx.drawImage(img, (cw - w) / 2, (ch - h) / 2, w, h);
    btnSave.disabled = false;
  }

  function drawB64(b64) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => { drawImageContain(img); resolve(); };
      img.src = "data:image/jpeg;base64," + b64;
    });
  }

  // ------------------------------------------------------------- results UI
  function updateResultsList(detections) {
    resultsList.innerHTML = "";
    const containers = detections.filter((d) => d.kind === "container");
    const damages = detections.filter((d) => d.kind === "damage");
    if (containers.length === 0) {
      resultsList.appendChild(li("Không phát hiện container nào."));
      return;
    }
    containers.forEach((c, idx) => {
      resultsList.appendChild(li(`[Container #${idx}] conf=${c.conf.toFixed(2)} box=${JSON.stringify(c.box)}`));
      const own = damages.filter((d) => d.container_idx === idx);
      if (own.length === 0) {
        resultsList.appendChild(li("    (không phát hiện hư hỏng)"));
      }
      own.forEach((d) => {
        resultsList.appendChild(li(`    - ${d.label} conf=${d.conf.toFixed(2)} box=${JSON.stringify(d.box)}`));
      });
    });
  }

  function li(text) {
    const el = document.createElement("li");
    el.textContent = text;
    return el;
  }

  // -------------------------------------------------------------- popups
  let popupOffset = 0;
  function showAlertPopup(alert) {
    if (!$("cb-popup").checked) return;
    const layer = $("popup-layer");
    const div = document.createElement("div");
    div.className = "damage-popup";
    const offset = (popupOffset++ % 8) * 28;
    div.style.top = `${60 + offset}px`;
    div.style.left = `${60 + offset}px`;
    div.innerHTML = `
      <button class="close-btn">&times;</button>
      <img src="data:image/jpeg;base64,${alert.snapshot_b64}">
      <div>Loại hư hỏng: ${alert.label}</div>
      <div>Độ tin cậy: ${(alert.conf * 100).toFixed(0)}%</div>
      <div>Container #${alert.container_idx ?? "?"}</div>
      <div>Vị trí (khung gốc): [${alert.box.join(", ")}]</div>
    `;
    div.querySelector(".close-btn").onclick = () => div.remove();
    layer.appendChild(div);
  }

  // --------------------------------------------------------------- backend
  async function fetchJson(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async function populateModels() {
    const data = await fetchJson("/api/models");
    const containerSel = $("select-container-model");
    const damageSel = $("select-damage-model");
    containerSel.innerHTML = "";
    damageSel.innerHTML = "";
    if (data.models.length === 0) {
      const opt = new Option("(Không tìm thấy .pt trong thư mục weights/)", "");
      containerSel.add(opt.cloneNode(true));
      damageSel.add(opt);
      return;
    }
    data.models.forEach((m) => {
      containerSel.add(new Option(m, m));
      damageSel.add(new Option(m, m));
    });
    if (data.guess.container) containerSel.value = data.guess.container;
    if (data.guess.damage) damageSel.value = data.guess.damage;
  }

  async function populateDevices() {
    const data = await fetchJson("/api/devices");
    const sel = $("select-device");
    sel.innerHTML = "";
    data.devices.forEach((d) => sel.add(new Option(d, d)));
    if (data.devices.length > 1) sel.value = data.devices[1];
    if (Object.keys(data.warnings).length > 0) {
      const details = Object.entries(data.warnings).map(([k, v]) => `${k}: ${v}`).join("; ");
      sel.title = `Một số GPU không dùng được, đã ẩn: ${details}`;
    }
  }

  async function loadSelectedModel() {
    const containerPath = $("select-container-model").value;
    const damagePath = $("select-damage-model").value;
    if (!containerPath || !damagePath) {
      modelInfo.textContent = "Chưa chọn model hợp lệ";
      return;
    }
    const device = $("select-device").value || "cpu";
    setStatus(`Đang nạp model ${containerPath} + ${damagePath} trên ${device}...`);
    try {
      const data = await fetchJson("/api/session/load_model", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, container_path: containerPath, damage_path: damagePath, device }),
      });
      modelInfo.textContent =
        `Container model: ${containerPath}\n  Lớp: ${data.container_names.join(", ")}\n` +
        `Damage model: ${damagePath}\n  Lớp: ${data.damage_names.join(", ")}\n` +
        `Device: ${device}`;
      hasModel = true;
      setStatus("Nạp model thành công");
      await pushParams();
      if (mode === "image" && lastImageFile) await detectImage(lastImageFile);
    } catch (e) {
      hasModel = false;
      modelInfo.textContent = "Lỗi nạp model";
      alert(`Lỗi nạp model: ${e.message}`);
      setStatus("Lỗi nạp model");
    }
  }

  function buildParamsBody() {
    return {
      session_id: sessionId,
      container: {
        conf: parseFloat($("container-conf").value),
        iou: parseFloat($("container-iou").value),
        imgsz: parseInt($("container-imgsz").value, 10),
      },
      damage: {
        conf: parseFloat($("damage-conf").value),
        iou: parseFloat($("damage-iou").value),
        imgsz: parseInt($("damage-imgsz").value, 10),
      },
      padding_ratio: parseInt($("padding").value, 10) / 100.0,
      display: {
        show_labels: $("cb-labels").checked,
        show_conf: $("cb-conf").checked,
        show_container_box: $("cb-container-box").checked,
      },
      cooldown_seconds: parseFloat($("cooldown").value),
    };
  }

  async function pushParams() {
    if (!hasModel) return;
    try {
      await fetchJson("/api/session/params", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildParamsBody()),
      });
    } catch (e) {
      setStatus(`Lỗi cập nhật tham số: ${e.message}`);
    }
  }

  let paramDebounce = null;
  function onParamsChanged() {
    clearTimeout(paramDebounce);
    paramDebounce = setTimeout(async () => {
      await pushParams();
      if (mode === "image" && lastImageFile) await detectImage(lastImageFile);
    }, 200);
  }

  // ----------------------------------------------------------- image mode
  async function detectImage(file) {
    if (!hasModel) {
      alert("Vui lòng chọn model trước.");
      return;
    }
    stopStream();
    mode = "image";
    lastImageFile = file;
    setStatus(`Ảnh: ${file.name}`);
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("file", file);
    try {
      const data = await fetchJson("/api/detect_image", { method: "POST", body: form });
      await drawB64(data.annotated_image_b64);
      updateResultsList(data.detections);
      fpsLabel.textContent = "FPS: - (ảnh tĩnh)";
      data.alerts.forEach(showAlertPopup);
    } catch (e) {
      setStatus(`Lỗi: ${e.message}`);
    }
  }

  // ----------------------------------------------------------- video mode
  async function startVideo(file) {
    if (!hasModel) {
      alert("Vui lòng chọn model trước.");
      return;
    }
    stopStream();
    mode = "video";
    setStatus(`Video: ${file.name}`);
    const form = new FormData();
    form.append("file", file);
    const { video_id } = await fetchJson("/api/upload_video", { method: "POST", body: form });

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/video/${video_id}?session_id=${sessionId}`);
    activeSocket = ws;
    ws.onmessage = (ev) => handleStreamMessage(JSON.parse(ev.data));
    ws.onclose = () => { if (activeSocket === ws) finishStream(); };
    btnStop.disabled = false;
    btnRecord.disabled = false;
  }

  // ----------------------------------------------------------- webcam mode
  async function startWebcam() {
    if (!hasModel) {
      alert("Vui lòng chọn model trước.");
      return;
    }
    stopStream();
    try {
      webcamStream = await navigator.mediaDevices.getUserMedia({ video: true });
    } catch (e) {
      alert(`Không mở được webcam: ${e.message}`);
      return;
    }
    mode = "webcam";
    setStatus("Webcam");
    hiddenVideo.srcObject = webcamStream;
    await hiddenVideo.play();
    grabCanvas.width = hiddenVideo.videoWidth || 640;
    grabCanvas.height = hiddenVideo.videoHeight || 480;

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/webcam?session_id=${sessionId}`);
    activeSocket = ws;
    ws.onopen = () => {
      webcamTimer = setInterval(() => sendWebcamFrame(ws), 150); // ~6-7 fps, keeps server responsive
    };
    ws.onmessage = (ev) => handleStreamMessage(JSON.parse(ev.data));
    ws.onclose = () => { if (activeSocket === ws) finishStream(); };
    btnStop.disabled = false;
    btnRecord.disabled = false;
  }

  function sendWebcamFrame(ws) {
    if (ws.readyState !== WebSocket.OPEN) return;
    const gctx = grabCanvas.getContext("2d");
    gctx.drawImage(hiddenVideo, 0, 0, grabCanvas.width, grabCanvas.height);
    const dataUrl = grabCanvas.toDataURL("image/jpeg", 0.7);
    const b64 = dataUrl.substring(dataUrl.indexOf(",") + 1);
    ws.send(JSON.stringify({ type: "frame", image_b64: b64 }));
  }

  // --------------------------------------------------------- shared stream
  function handleStreamMessage(msg) {
    if (msg.type === "frame") {
      drawB64(msg.annotated_image_b64);
      updateResultsList(msg.detections);
      fpsLabel.textContent = `FPS: ${msg.fps.toFixed(1)}`;
    } else if (msg.type === "alert") {
      showAlertPopup(msg);
    } else if (msg.type === "done") {
      setStatus("Video kết thúc");
      finishStream();
    } else if (msg.type === "error") {
      setStatus(`Lỗi: ${msg.message}`);
      finishStream();
    }
  }

  function cleanupLocal() {
    if (webcamTimer) { clearInterval(webcamTimer); webcamTimer = null; }
    if (webcamStream) { webcamStream.getTracks().forEach((t) => t.stop()); webcamStream = null; }
    stopRecording();
    btnStop.disabled = true;
    btnRecord.disabled = true;
    activeSocket = null;
  }

  // socket closed by the server itself (video EOF/"done", or error)
  function finishStream() {
    cleanupLocal();
  }

  // user clicked "Dừng"
  function stopStream() {
    if (activeSocket) {
      try {
        if (activeSocket.readyState === WebSocket.OPEN) {
          mode === "video" ? activeSocket.send("stop") : activeSocket.send(JSON.stringify({ type: "stop" }));
        }
        activeSocket.close();
      } catch (e) { /* already closed */ }
    }
    cleanupLocal();
  }

  // -------------------------------------------------------------- save
  $("btn-save").addEventListener("click", () => {
    canvas.toBlob((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "result.png";
      a.click();
      URL.revokeObjectURL(a.href);
    }, "image/png");
  });

  // ------------------------------------------------------------ recording
  function toggleRecording() {
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      const stream = canvas.captureStream(20);
      recordedChunks = [];
      mediaRecorder = new MediaRecorder(stream, { mimeType: "video/webm" });
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunks.push(e.data); };
      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: "video/webm" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "output.webm";
        a.click();
        URL.revokeObjectURL(a.href);
        setStatus("Đã lưu video (định dạng .webm - giới hạn của trình duyệt)");
      };
      mediaRecorder.start();
      btnRecord.textContent = "■ Dừng ghi";
      setStatus("Đang ghi video kết quả (.webm)...");
    } else {
      stopRecording();
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    mediaRecorder = null;
    btnRecord.textContent = "● Ghi video kết quả";
  }

  // ------------------------------------------------------------ wiring
  $("input-image").addEventListener("change", (e) => {
    if (e.target.files[0]) detectImage(e.target.files[0]);
    e.target.value = "";
  });
  $("input-video").addEventListener("change", (e) => {
    if (e.target.files[0]) startVideo(e.target.files[0]);
    e.target.value = "";
  });
  btnWebcam.addEventListener("click", startWebcam);
  btnStop.addEventListener("click", stopStream);
  btnRecord.addEventListener("click", toggleRecording);

  $("btn-reload-model").addEventListener("click", loadSelectedModel);
  $("select-container-model").addEventListener("change", loadSelectedModel);
  $("select-damage-model").addEventListener("change", loadSelectedModel);
  $("select-device").addEventListener("change", loadSelectedModel);

  [
    "container-conf", "container-iou", "container-imgsz", "padding",
    "damage-conf", "damage-iou", "damage-imgsz",
  ].forEach((id) => $(id).addEventListener("input", onParamsChanged));
  ["cb-container-box", "cb-labels", "cb-conf"].forEach((id) => $(id).addEventListener("change", onParamsChanged));
  $("cooldown").addEventListener("change", onParamsChanged);

  const liveLabels = {
    "container-conf": "lbl-container-conf", "container-iou": "lbl-container-iou",
    "damage-conf": "lbl-damage-conf", "damage-iou": "lbl-damage-iou", "padding": "lbl-padding",
  };
  Object.entries(liveLabels).forEach(([inputId, labelId]) => {
    $(inputId).addEventListener("input", () => { $(labelId).textContent = $(inputId).value; });
  });

  // ------------------------------------------------------------- startup
  (async function init() {
    await Promise.all([populateModels(), populateDevices()]);
    await loadSelectedModel();
  })();
})();
