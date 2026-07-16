/* Mobile App Suite — shared JS utilities */

// ── Toasts ───────────────────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  const c = document.getElementById('toastContainer');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = message;
  c.appendChild(t);
  setTimeout(() => {
    t.style.opacity = '0';
    t.style.transition = 'opacity .3s';
    setTimeout(() => t.remove(), 300);
  }, duration);
}

// ── Upload areas (drag-drop + click) ─────────────────────────────────────────
function initUploadAreas() {
  document.querySelectorAll('.upload-area').forEach(area => {
    const input = area.querySelector('input[type=file]');
    if (!input) return;

    area.addEventListener('dragover', e => {
      e.preventDefault(); area.classList.add('drag-over');
    });
    area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
    area.addEventListener('drop', e => {
      e.preventDefault(); area.classList.remove('drag-over');
      if (e.dataTransfer.files.length) {
        try {
          const dt = new DataTransfer();
          dt.items.add(e.dataTransfer.files[0]);
          input.files = dt.files;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        } catch (_) {}
      }
    });

    input.addEventListener('change', () => {
      const f = input.files[0];
      if (!f) return;
      const label = area.querySelector('.upload-text');
      if (label) label.innerHTML = `<strong>${f.name}</strong><br>${(f.size/1024).toFixed(1)} KB`;
    });
  });
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tabs').forEach(group => {
    const panes = {};
    group.querySelectorAll('.tab').forEach(tab => {
      const target = tab.dataset.tab;
      if (target) panes[target] = document.getElementById(target);
      tab.addEventListener('click', () => {
        group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        Object.values(panes).forEach(p => p && (p.style.display = 'none'));
        if (target && panes[target]) panes[target].style.display = '';
      });
    });
  });
}

// ── Character counter ─────────────────────────────────────────────────────────
function initCharCounters() {
  document.querySelectorAll('[data-maxlength]').forEach(el => {
    const max = parseInt(el.dataset.maxlength);
    const counter = document.createElement('div');
    counter.style.cssText = 'font-size:11px;color:var(--muted);text-align:right;margin-top:4px';
    el.after(counter);
    const update = () => { counter.textContent = `${el.value.length} / ${max}`; };
    el.addEventListener('input', update); update();
  });
}

// ── Generic form loading state ─────────────────────────────────────────────────
function setLoading(btn, loading, text = '') {
  if (loading) {
    btn.dataset.origText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span>${text || 'Processing…'}`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn.dataset.origText || 'Submit';
    btn.disabled = false;
  }
}

// ── Inline confirm helpers (no browser popup) ──────────────────────────────────
// Usage: <button onclick="showInlineConfirm(this)"> paired with a sibling
//        <span class="inline-confirm"> that holds Yes/No buttons.
function showInlineConfirm(triggerBtn) {
  triggerBtn.style.display = 'none';
  const confirmEl = triggerBtn.nextElementSibling;
  if (confirmEl) confirmEl.style.display = 'flex';
}
function hideInlineConfirm(cancelBtn) {
  const confirmEl = cancelBtn.closest('.inline-confirm');
  if (!confirmEl) return;
  confirmEl.style.display = 'none';
  const trigger = confirmEl.previousElementSibling;
  if (trigger) trigger.style.display = '';
}

// ── Init on DOM ready ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initUploadAreas();
  initTabs();
  initCharCounters();
});
