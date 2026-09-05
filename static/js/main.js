// Reusable vanilla JS helpers for PlagiaScan AI Lite
// Typing animation
function initTyping(el, words, speed = 90, pause = 1600) {
  if (!el) return;
  let i = 0, j = 0, deleting = false;
  function tick() {
    const word = words[i % words.length];
    if (!deleting) {
      el.textContent = word.slice(0, ++j);
      if (j === word.length) { deleting = true; setTimeout(tick, pause); return; }
    } else {
      el.textContent = word.slice(0, --j);
      if (j === 0) { deleting = false; i++; }
    }
    setTimeout(tick, deleting ? speed / 2 : speed);
  }
  tick();
}

// Fade-up on scroll (IntersectionObserver)
function initReveal() {
  const els = document.querySelectorAll('[data-reveal]');
  if (!els.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('fade-up');
        obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.12 });
  els.forEach(el => obs.observe(el));
}

// Counter animation
function initCounters() {
  document.querySelectorAll('[data-count]').forEach(el => {
    const target = parseFloat(el.dataset.count);
    const decimals = parseInt(el.dataset.decimals || '0');
    const obs = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (!e.isIntersecting) return;
        let cur = 0;
        const step = target / 60;
        const t = setInterval(() => {
          cur += step;
          if (cur >= target) { cur = target; clearInterval(t); }
          el.textContent = cur.toFixed(decimals);
        }, 16);
        obs.unobserve(el);
      });
    }, { threshold: 0.5 });
    obs.observe(el);
  });
}

// Animate meter bars when visible
function initMeters() {
  document.querySelectorAll('.meter > span[data-width]').forEach(span => {
    const obs = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (!e.isIntersecting) return;
        span.style.width = span.dataset.width + '%';
        obs.unobserve(span);
      });
    }, { threshold: 0.4 });
    obs.observe(span);
  });
}

// Highlight matched paragraphs in a report view
function highlightMatches(containerSelector, matches) {
  const container = document.querySelector(containerSelector);
  if (!container || !matches || !matches.length) return;
  let html = container.innerHTML;
  matches.forEach(m => {
    const snippet = (m.matched_text || '').trim();
    if (snippet.length < 12) return;
    const escaped = snippet.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').slice(0, 80);
    const re = new RegExp(escaped, 'i');
    html = html.replace(re, '<mark class="match">$&</mark>');
  });
  container.innerHTML = html;
}

// Upload form (drag + drop + progress)
function initUploadForm(formId, resultHandler) {
  const form = document.getElementById(formId);
  if (!form) return;
  const dropzone = form.querySelector('.dropzone');
  const fileInput = form.querySelector('input[type="file"]');
  const fileName = form.querySelector('.file-name');
  const progress = form.querySelector('.upload-progress');
  const alertBox = form.querySelector('.upload-alert');
  const submitBtn = form.querySelector('button[type="submit"]');

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());
    ['dragover', 'dragenter'].forEach(ev =>
      dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add('drag'); }));
    ['dragleave', 'drop'].forEach(ev =>
      dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove('drag'); }));
    dropzone.addEventListener('drop', e => {
      if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; updateName(); }
    });
    fileInput.addEventListener('change', updateName);
  }
  function updateName() {
    if (fileInput.files.length && fileName) {
      fileName.textContent = fileInput.files[0].name + ' (' + formatBytes(fileInput.files[0].size) + ')';
    }
  }
  form.addEventListener('submit', e => {
    e.preventDefault();
    if (!fileInput || !fileInput.files.length) {
      showAlert('Please choose a file to upload.', 'danger');
      return;
    }
    const fd = new FormData(form);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', form.action || '/api/upload');
    if (progress) progress.style.display = 'block';
    xhr.upload.onprogress = e => {
      if (e.lengthComputable && progress) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progress.querySelector('.progress-bar').style.width = pct + '%';
      }
    };
    xhr.onload = () => {
      if (progress) progress.style.display = 'none';
      let data;
      try { data = JSON.parse(xhr.responseText); } catch (_) { data = null; }
      if (xhr.status >= 200 && xhr.status < 300 && data && data.report_id) {
        if (resultHandler) resultHandler(data);
        else window.location.href = '/report/' + data.report_id;
      } else {
        const msg = (data && data.error) || 'Upload failed. Please try again.';
        showAlert(msg, 'danger');
        if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = submitBtn.dataset.original || 'Analyze'; }
      }
    };
    xhr.onerror = () => {
      showAlert('Network error. Please try again.', 'danger');
      if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = submitBtn.dataset.original || 'Analyze'; }
    };
    if (submitBtn) { submitBtn.dataset.original = submitBtn.innerHTML; submitBtn.disabled = true; submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Analyzing...'; }
    xhr.send(fd);
  });
  function showAlert(msg, type) {
    if (!alertBox) { alert(msg); return; }
    alertBox.className = 'alert alert-' + type;
    alertBox.textContent = msg;
    alertBox.style.display = 'block';
  }
}
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
// Simple chart renderer (canvas, no library)
function drawBarChart(canvasId, labels, values, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight || 220;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  if (!values.length) return;
  const max = Math.max(...values, 1);
  const pad = 30, barW = (w - pad * 2) / values.length * 0.6;
  const gap = (w - pad * 2) / values.length;
  ctx.fillStyle = color || '#6366f1';
  values.forEach((v, i) => {
    const bh = (v / max) * (h - pad * 2);
    const x = pad + i * gap + (gap - barW) / 2;
    const y = h - pad - bh;
    ctx.fillRect(x, y, barW, bh);
  });
  // labels
  ctx.fillStyle = '#9aa3c7';
  ctx.font = '10px Poppins, sans-serif';
  ctx.textAlign = 'center';
  labels.forEach((l, i) => {
    const x = pad + i * gap + gap / 2;
    ctx.fillText(String(l).slice(5), x, h - 8);
  });
}
function drawLineChart(canvasId, labels, values, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight || 220;
  canvas.width = w * dpr; canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  if (!values.length) return;
  const max = Math.max(...values, 1);
  const pad = 30;
  const stepX = (w - pad * 2) / Math.max(1, values.length - 1);
  ctx.strokeStyle = color || '#8b5cf6';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = pad + i * stepX;
    const y = h - pad - (v / max) * (h - pad * 2);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  // points
  ctx.fillStyle = color || '#8b5cf6';
  values.forEach((v, i) => {
    const x = pad + i * stepX;
    const y = h - pad - (v / max) * (h - pad * 2);
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
  });
}
function drawDoughnut(canvasId, segments) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const size = Math.min(canvas.clientWidth, 240);
  canvas.width = size * dpr; canvas.height = size * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, size, size);
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const cx = size / 2, cy = size / 2, r = size / 2 - 10, ir = r * 0.6;
  let a = -Math.PI / 2;
  segments.forEach(seg => {
    const arc = (seg.value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(a) * ir, cy + Math.sin(a) * ir);
    ctx.arc(cx, cy, r, a, a + arc);
    ctx.arc(cx, cy, ir, a + arc, a, true);
    ctx.closePath();
    ctx.fillStyle = seg.color;
    ctx.fill();
    a += arc;
  });
}
// Auto-run common inits
document.addEventListener('DOMContentLoaded', () => {
  initReveal();
  initCounters();
  initMeters();
});