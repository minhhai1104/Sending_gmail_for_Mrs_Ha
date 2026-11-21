/* Gmail Auto Mailer v3.0 — Client Controller (Vanilla ES6, Zero CDN, Strict XSS Escaping) */
(() => {
  'use strict';

  const EMAIL_RE = /^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$/;
  const VI_COLLATOR = new Intl.Collator('vi', { numeric: true, sensitivity: 'base' });

  const SVG_CHECK =
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3.5 8.5 6.5 11.5 12.5 4.5"/></svg>';
  const SVG_CROSS =
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4.5" y1="4.5" x2="11.5" y2="11.5"/><line x1="11.5" y1="4.5" x2="4.5" y2="11.5"/></svg>';
  const SVG_QUESTION =
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5.75 6a2.25 2.25 0 1 1 3.15 2.06c-.62.28-.9.74-.9 1.32v.37"/><circle cx="8" cy="12.35" r="0.7" fill="currentColor" stroke="none"/></svg>';
  const SVG_ALERT =
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="8" y1="3.8" x2="8" y2="8.9"/><circle cx="8" cy="12" r="0.75" fill="currentColor" stroke="none"/></svg>';

  // Event Bus nhận thông điệp 1 chiều từ Python Worker Thread
  const listeners = new Map();
  window.AppBus = {
    on(name, fn) {
      if (!listeners.has(name)) listeners.set(name, []);
      listeners.get(name).push(fn);
    },
    emit(name, payload) {
      const fns = listeners.get(name) || [];
      for (const fn of fns) {
        try { fn(payload); } catch (err) { console.error(err); }
      }
    },
  };

  const state = {
    version: '3.1.0',
    bootstrap: null,
    workspace: null,
    activePage: 'send',
    wsFilter: 'all',
    wsSearch: '',
    wsSort: { col: null, dir: 'ascending' },
    skipSent: true,
    selectedIds: new Set(),
    inspectedId: null,
    previewMode: 'html',
    supFilter: 'all',
    supSearch: '',
    lastFocusedTplField: null,
    wizStep: 1,
    otaInfo: null,
    batchPaused: false,
    dragCounter: 0,
  };

  const $ = (id) => document.getElementById(id);
  const api = () => window.pywebview && window.pywebview.api;

  function esc(text) {
    return String(text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function showToast(message, type = 'info', duration = 3800) {
    const stack = $('toast-stack');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity 0.2s ease';
      setTimeout(() => el.remove(), 220);
    }, duration);
  }

  function formatEta(seconds) {
    if (!Number.isFinite(seconds) || seconds <= 0) return 'Sắp xong';
    if (seconds < 60) return `${seconds} giây`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m} phút ${s} giây`;
  }

  function formatSize(bytes) {
    if (!bytes || bytes <= 0) return '0 KB';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  // ==================== THEME MANAGEMENT ====================
  function resolveTheme(pref) {
    if (pref === 'dark' || pref === 'light') return pref;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(pref) {
    const resolved = resolveTheme(pref);
    document.documentElement.setAttribute('data-theme', resolved);
    $('theme-toggle-label').textContent = resolved === 'dark' ? 'Sáng' : 'Tối';
    document.querySelectorAll('#set-theme-seg .seg-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.themeChoice === pref);
    });
  }

  // ==================== NAVIGATION ====================
  function switchPage(pageName) {
    state.activePage = pageName;
    document.querySelectorAll('.nav-item').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.page === pageName);
    });
    document.querySelectorAll('.page').forEach((sec) => {
      sec.classList.toggle('active', sec.id === `page-${pageName}`);
    });
    if (pageName === 'history') loadHistory();
    if (pageName === 'templates') refreshTemplatePreview();
    if (pageName === 'suppliers') renderSuppliersTable();
  }

  // ==================== BOOTSTRAP RENDER ====================
  function applyBootstrap(boot) {
    state.bootstrap = boot;
    if (boot.version) state.version = boot.version;
    $('sidebar-version').textContent = `v${state.version}`;
    $('set-version-badge').textContent = `v${state.version}`;
    $('nav-count-suppliers').textContent = String((boot.suppliers || []).length);

    applyTheme(boot.prefs?.theme || 'system');

    // Sidebar Gmail Status Pill
    const s = boot.settings;
    const dot = $('gmail-status-dot');
    dot.classList.toggle('ok', Boolean(s.gmail_ready));
    if (s.gmail_ready) {
      $('gmail-pill-title').textContent = s.sender;
      $('gmail-pill-sub').textContent = 'Gmail sẵn sàng (DPAPI)';
    } else {
      $('gmail-pill-title').textContent = s.sender || 'Chưa kết nối Gmail';
      $('gmail-pill-sub').textContent = 'Bấm để hoàn tất cài đặt';
    }

    // Settings Form (Write-Only: không bao giờ điền mật khẩu/token)
    $('set-sender').value = s.sender || '';
    $('set-display-name').value = s.display_name || '';
    $('set-cc').value = (s.cc || []).join('; ');
    $('set-attach-dir').value = s.attach_dir || '';
    $('set-pacing').value = String(s.pacing_seconds ?? 1.8);
    $('set-pacing-val').textContent = `${Number(s.pacing_seconds ?? 1.8).toFixed(1)}s`;
    $('set-retries').value = String(s.max_retries ?? 2);

    const dpapiBadge = $('set-dpapi-badge');
    if (s.has_app_password) {
      dpapiBadge.className = 'badge badge-ok';
      dpapiBadge.textContent = 'Đã mã hóa an toàn (Windows DPAPI)';
    } else {
      dpapiBadge.className = 'badge badge-err';
      dpapiBadge.textContent = 'Chưa thiết lập Mật khẩu ứng dụng';
    }
    $('set-gh-hint').textContent = s.has_github_token
      ? 'Đã lưu GitHub Token bảo mật bằng Windows DPAPI (không hiển thị lại).'
      : 'Chỉ cần dùng nếu kho GitHub Releases để chế độ riêng tư (Private).';

    // Template Studio Fields
    const t = boot.templates;
    $('tpl-subject').value = t.subject || '';
    $('tpl-body').value = t.body || '';
    $('tpl-excel').value = t.excel_name || '';
    $('tpl-pdf').value = t.pdf_name || '';
    renderLogoThumb($('tpl-logo-thumb'), s.logo_data_uri);
    $('btn-clear-logo').classList.toggle('hidden', !s.logo_data_uri);

    // Sample supplier selector in Template Studio
    const sampleSel = $('tpl-preview-sample-sup');
    const prevVal = sampleSel.value;
    sampleSel.innerHTML = '';
    const sups = boot.suppliers && boot.suppliers.length ? boot.suppliers : [{ name: 'ACE' }];
    for (const sup of sups) {
      const opt = document.createElement('option');
      opt.value = sup.name;
      opt.textContent = sup.name;
      sampleSel.appendChild(opt);
    }
    if (prevVal && [...sampleSel.options].some((o) => o.value === prevVal)) {
      sampleSel.value = prevVal;
    }

    renderSuppliersTable();
  }

  function renderLogoThumb(boxEl, dataUri) {
    if (dataUri) {
      boxEl.innerHTML = `<img src="${esc(dataUri)}" alt="Logo công ty" />`;
    } else {
      boxEl.innerHTML = '<span class="text-muted">Chưa có logo</span>';
    }
  }

  // ==================== WORKSPACE RENDER ====================
  function applyWorkspace(ws, preserveSelection = false) {
    state.workspace = ws;
    const plans = ws.plans || [];

    // Sync Period & Mode controls
    $('ws-month').value = String(ws.period.month);
    $('ws-year').value = String(ws.period.year);
    document.querySelectorAll('#page-send .seg-btn').forEach((b) => {
      b.classList.toggle('active', b.dataset.kind === ws.period.kind);
    });
    const reasonChip = $('period-reason-chip');
    if (ws.period.reason) {
      reasonChip.textContent = ws.period.reason;
      reasonChip.classList.remove('hidden');
    } else {
      reasonChip.classList.add('hidden');
    }

    // Source strip
    const srcStrip = $('source-strip');
    if (ws.source.scanned_count > 0) {
      srcStrip.classList.add('has-source');
      $('source-title').textContent = ws.source.label || 'Đã nạp thư mục báo cáo';
      $('source-sub').textContent = `Đã quét ${ws.source.scanned_count} tệp Excel/PDF hợp lệ. Kéo thả thư mục mới bất kỳ lúc nào để thay thế.`;
    } else {
      srcStrip.classList.remove('has-source');
      $('source-title').textContent = 'Kéo thả thư mục hoặc tệp Excel / PDF vào đây';
      $('source-sub').textContent = 'Hoặc bấm "Chọn thư mục" — ứng dụng tự nhận diện kỳ gửi và khớp an toàn vào từng nhà cung cấp.';
    }

    // KPI counts & Sidebar attention badge
    const sum = ws.summary;
    const attentionCount = sum.review + sum.error;
    $('kpi-all').textContent = String(sum.total);
    $('kpi-ready').textContent = String(sum.ready_new);
    $('kpi-attention').textContent = String(attentionCount);
    $('kpi-sent').textContent = String(sum.sent);

    const navBadge = $('nav-badge-send');
    if (attentionCount > 0 && ws.source.scanned_count > 0) {
      navBadge.textContent = String(attentionCount);
      navBadge.classList.remove('hidden');
    } else {
      navBadge.classList.add('hidden');
    }

    // Retry failed button on action bar
    const retryBtn = $('btn-retry-failed-bar');
    if (sum.failed_in_period > 0) {
      retryBtn.textContent = `Gửi lại ${sum.failed_in_period} nhà bị lỗi`;
      retryBtn.classList.remove('hidden');
    } else {
      retryBtn.classList.add('hidden');
    }

    // Rebuild selectedIds
    if (!preserveSelection) {
      state.selectedIds = new Set(
        plans
          .filter((p) => p.sendable && !(state.skipSent && p.already_sent))
          .map((p) => p.supplier_id)
      );
    } else {
      const validIds = new Set(plans.filter((p) => p.sendable).map((p) => p.supplier_id));
      state.selectedIds = new Set([...state.selectedIds].filter((id) => validIds.has(id)));
    }

    // Ensure inspectedId stays valid
    if (!plans.some((p) => p.supplier_id === state.inspectedId)) {
      state.inspectedId = plans.length ? plans[0].supplier_id : null;
    }

    renderWorkspaceAlerts(ws);
    renderQueueList();
    renderInspector();
    renderActionBar();
  }

  function renderWorkspaceAlerts(ws) {
    const container = $('ws-alerts');
    container.innerHTML = '';

    if (!ws.gmail_ready && ws.gmail_problems?.length) {
      const el = document.createElement('div');
      el.className = 'alert alert-err';
      el.innerHTML = `
        <span><strong>Chưa kết nối Gmail:</strong> ${esc(ws.gmail_problems[0])}</span>
        <div class="alert-actions">
          <button class="btn btn-secondary btn-xs" id="alert-goto-settings">Thiết lập Gmail ngay</button>
        </div>`;
      container.appendChild(el);
      el.querySelector('#alert-goto-settings').addEventListener('click', () => switchPage('settings'));
    }

    const dupEntries = Object.entries(ws.duplicate_emails || {});
    if (dupEntries.length > 0) {
      const desc = dupEntries.map(([email, names]) => `${email} (${names.join(', ')})`).join('; ');
      const el = document.createElement('div');
      el.className = 'alert alert-warn';
      el.innerHTML = `<span><strong>Cảnh báo trùng Email giữa các NCC:</strong> ${esc(desc)} — kiểm tra kỹ tránh gửi nhầm bảng phí!</span>`;
      container.appendChild(el);
    }

    if (ws.source.partial_pdf_warning) {
      const el = document.createElement('div');
      el.className = 'alert alert-warn';
      el.innerHTML = '<span><strong>Lưu ý số lượng PDF:</strong> Số tệp PDF ít hơn số tệp Excel trong thư mục. Hãy kiểm tra lại xem đã đủ PO hay nên chọn chế độ Tạm tính.</span>';
      container.appendChild(el);
    }

    if (ws.discovered && ws.discovered.length > 0) {
      const el = document.createElement('div');
      el.className = 'alert alert-info';
      const chips = ws.discovered
        .map(
          (d, idx) =>
            `<button class="btn btn-secondary btn-xs" data-disc-idx="${idx}">+ Thêm "${esc(d.suggested_name)}" (${d.files.length} file)</button>`
        )
        .join('');
      el.innerHTML = `
        <span><strong>Phát hiện ${ws.discovered.length} nhà cung cấp mới</strong> trong thư mục báo cáo:</span>
        <div class="alert-actions">${chips}</div>`;
      container.appendChild(el);
      el.querySelectorAll('[data-disc-idx]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const d = ws.discovered[Number(btn.dataset.discIdx)];
          openSupplierDrawer({ id: '', name: d.suggested_name, recipients: [], aliases: [], note: '', enabled: true });
        });
      });
    }
  }

  function getFilteredPlans() {
    const plans = state.workspace?.plans || [];
    const kw = state.wsSearch.trim().toLowerCase();
    return plans.filter((p) => {
      if (kw && !p.supplier.toLowerCase().includes(kw) && !p.recipients.join(' ').toLowerCase().includes(kw)) {
        return false;
      }
      if (state.wsFilter === 'ready') return p.state === 'ready' && !p.already_sent;
      if (state.wsFilter === 'attention') return p.state === 'review' || p.state === 'error';
      if (state.wsFilter === 'sent') return p.already_sent;
      return true;
    });
  }

  function getPlanStatusMeta(p) {
    if (!p.enabled) return { rank: 4, cls: 'st-muted', label: 'Tạm tắt' };
    if (p.state === 'review') return { rank: 0, cls: 'st-warn', label: 'Cần duyệt' };
    if (p.state === 'error') {
      const atts = p.attachments || [];
      if (atts.some((a) => a.status === 'conflict')) return { rank: 1, cls: 'st-err', label: 'Xung đột' };
      if (atts.some((a) => a.status === 'ambiguous')) return { rank: 1, cls: 'st-err', label: 'Trùng file' };
      if (atts.some((a) => a.status === 'wrong_period')) return { rank: 1, cls: 'st-err', label: 'Sai kỳ' };
      if (atts.some((a) => a.status === 'invalid_file')) return { rank: 1, cls: 'st-err', label: 'File lỗi' };

      const emailMissing = !p.recipients.length;
      const emailInvalid = !emailMissing && p.recipients.some((e) => !EMAIL_RE.test(e));
      const xlsAtt = atts.find((a) => a.file_type === 'excel');
      const pdfAtt = atts.find((a) => a.file_type === 'pdf');
      const xlsMissing = Boolean(xlsAtt && xlsAtt.is_blocked);
      const pdfMissing = Boolean(pdfAtt && pdfAtt.is_blocked);
      const issueCount = Number(emailMissing || emailInvalid) + Number(xlsMissing) + Number(pdfMissing);

      if (issueCount >= 2) return { rank: 1, cls: 'st-err', label: `Thiếu ${issueCount} mục` };
      if (emailMissing) return { rank: 1, cls: 'st-err', label: 'Thiếu email' };
      if (emailInvalid) return { rank: 1, cls: 'st-err', label: 'Email lỗi' };
      if (xlsMissing) return { rank: 1, cls: 'st-err', label: 'Thiếu Excel' };
      if (pdfMissing) return { rank: 1, cls: 'st-err', label: 'Thiếu PDF' };
      return { rank: 1, cls: 'st-err', label: 'Có lỗi' };
    }
    if (p.already_sent) return { rank: 3, cls: 'st-info', label: 'Đã gửi' };
    return { rank: 2, cls: 'st-ok', label: 'Sẵn sàng' };
  }

  function buildEmailIndicatorHtml(p) {
    const emailMissing = !p.recipients.length;
    const emailInvalid = !emailMissing && p.recipients.some((e) => !EMAIL_RE.test(e));
    const dupWarn = (p.warnings || []).find((w) => w.includes('trùng với NCC khác'));
    if (emailMissing) {
      return `<button type="button" class="qt-ind-btn qt-ind-err" data-act="edit-sup" data-sid="${p.supplier_id}" title="Chưa có email — Bấm để thêm" aria-label="Thêm email cho ${esc(p.supplier)}">${SVG_CROSS}</button>`;
    }
    if (emailInvalid) {
      return `<button type="button" class="qt-ind-btn qt-ind-err" data-act="edit-sup" data-sid="${p.supplier_id}" title="Email không hợp lệ — Bấm để sửa" aria-label="Sửa email không hợp lệ cho ${esc(p.supplier)}">${SVG_ALERT}</button>`;
    }
    if (dupWarn) {
      return `<button type="button" class="qt-ind-btn qt-ind-warn" data-act="edit-sup" data-sid="${p.supplier_id}" title="${esc(dupWarn)}" aria-label="Kiểm tra email trùng cho ${esc(p.supplier)}">${SVG_ALERT}</button>`;
    }
    const addrText = p.recipients.join('; ');
    return `<button type="button" class="qt-ind-btn qt-ind-ok" data-act="inspect-row" data-sid="${p.supplier_id}" title="Email: ${esc(addrText)}" aria-label="Email hợp lệ của ${esc(p.supplier)}">${SVG_CHECK}</button>`;
  }

  function buildAttachmentIndicatorHtml(p, fileType) {
    const att = (p.attachments || []).find((a) => a.file_type === fileType);
    const labelType = fileType === 'pdf' ? 'PDF' : 'Excel';
    if (!att) {
      return '<span class="text-muted" aria-hidden="true">—</span>';
    }
    if (att.is_ready) {
      const tip = `${att.file_name}${att.size_label ? ` (${att.size_label})` : ''}`;
      return `<button type="button" class="qt-ind-btn qt-ind-ok" data-act="inspect-row" data-sid="${p.supplier_id}" title="${esc(labelType)}: ${esc(tip)}" aria-label="Đã có tệp ${labelType} cho ${esc(p.supplier)}">${SVG_CHECK}</button>`;
    }
    if (att.needs_review) {
      const tip = `Gợi ý ${att.score}%: ${att.file_name} — Bấm để xem & duyệt`;
      return `<button type="button" class="qt-ind-btn qt-ind-warn" data-act="inspect-att" data-sid="${p.supplier_id}" data-ft="${fileType}" title="${esc(tip)}" aria-label="Xem và duyệt tệp ${labelType} gợi ý cho ${esc(p.supplier)}">${SVG_QUESTION}</button>`;
    }
    if (att.status === 'missing') {
      return `<button type="button" class="qt-ind-btn qt-ind-err" data-act="pick" data-sid="${p.supplier_id}" data-ft="${fileType}" title="Thiếu ${labelType} — Bấm để chọn tệp" aria-label="Chọn tệp ${labelType} cho ${esc(p.supplier)}">${SVG_CROSS}</button>`;
    }
    const tip = `${att.note || `Lỗi tệp ${labelType}`} — Bấm để xử lý`;
    return `<button type="button" class="qt-ind-btn qt-ind-err" data-act="inspect-att" data-sid="${p.supplier_id}" data-ft="${fileType}" title="${esc(tip)}" aria-label="Xử lý lỗi tệp ${labelType} cho ${esc(p.supplier)}">${SVG_ALERT}</button>`;
  }

  function getVisibleSelectablePlans(filtered) {
    if (state.wsFilter === 'sent') {
      return filtered.filter((p) => p.sendable);
    }
    return filtered.filter((p) => p.sendable && !(state.skipSent && p.already_sent));
  }

  function syncCheckAllHeader(filteredOverride = null) {
    const chkAll = $('ws-check-all');
    if (!chkAll) return;
    const filtered = filteredOverride || getFilteredPlans();
    const pool = getVisibleSelectablePlans(filtered);
    if (pool.length === 0) {
      chkAll.checked = false;
      chkAll.indeterminate = false;
      chkAll.disabled = true;
      return;
    }
    chkAll.disabled = false;
    const checkedCount = pool.filter((p) => state.selectedIds.has(p.supplier_id)).length;
    chkAll.checked = checkedCount === pool.length;
    chkAll.indeterminate = checkedCount > 0 && checkedCount < pool.length;
  }

  function comparePlans(a, b, col, dir) {
    const factor = dir === 'ascending' ? 1 : -1;
    if (col === 'name') {
      return factor * VI_COLLATOR.compare(a.supplier, b.supplier);
    }
    if (col === 'status') {
      const diff = getPlanStatusMeta(a).rank - getPlanStatusMeta(b).rank;
      if (diff !== 0) return factor * diff;
      return VI_COLLATOR.compare(a.supplier, b.supplier);
    }
    return 0;
  }

  function syncSortHeaderAria() {
    const headers = document.querySelectorAll('#ws-queue-table thead th[data-sort]');
    headers.forEach((th) => {
      if (state.wsSort.col && th.dataset.sort === state.wsSort.col) {
        th.setAttribute('aria-sort', state.wsSort.dir);
      } else {
        th.removeAttribute('aria-sort');
      }
    });
  }

  function sortQueueInPlace(col) {
    const tbody = $('ws-queue-body');
    const th = document.querySelector(`#ws-queue-table thead th[data-sort="${col}"]`);
    if (!tbody || !th) return;

    const nextDir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
    state.wsSort = { col, dir: nextDir };
    syncSortHeaderAria();

    const rows = [...tbody.rows];
    if (rows.length > 1) {
      const factor = nextDir === 'ascending' ? 1 : -1;
      const colIndex = th.cellIndex;
      const colType = th.dataset.type;
      const keyed = rows.map((row) => ({
        row,
        val: row.cells[colIndex]?.dataset.value ?? row.cells[colIndex]?.textContent.trim() ?? '',
        name: row.dataset.name || '',
      }));
      keyed.sort((a, b) => {
        if (colType === 'number') {
          const d = Number(a.val) - Number(b.val);
          if (d !== 0) return factor * d;
          return VI_COLLATOR.compare(a.name, b.name);
        }
        return factor * VI_COLLATOR.compare(a.val, b.val);
      });
      for (const item of keyed) {
        if (typeof tbody.moveBefore === 'function') {
          tbody.moveBefore(item.row, null);
        } else {
          tbody.appendChild(item.row);
        }
      }
    }

    const statusEl = $('ws-sort-status');
    if (statusEl) {
      const label = col === 'name' ? 'Nhà cung cấp' : 'Trạng thái';
      const dirLabel = nextDir === 'ascending' ? 'tăng dần' : 'giảm dần';
      statusEl.textContent = `Đã sắp xếp theo ${label}, ${dirLabel}, ${rows.length} nhà cung cấp`;
    }
  }

  function updateQueueSelectionClasses(scrollIntoView = false) {
    const tbody = $('ws-queue-body');
    if (!tbody) return;
    let activeRow = null;
    for (const row of tbody.rows) {
      const isSelected = Number(row.dataset.sid) === state.inspectedId;
      row.classList.toggle('selected', isSelected);
      row.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      if (isSelected) activeRow = row;
    }
    if (scrollIntoView && activeRow) {
      activeRow.scrollIntoView({ block: 'nearest' });
    }
  }

  function renderQueueList() {
    const wrap = $('ws-queue-wrap');
    const table = $('ws-queue-table');
    const tbody = $('ws-queue-body');
    const emptyEl = $('ws-queue-empty');
    const pdfTh = $('qt-th-pdf');
    const countEl = $('ws-visible-count');

    const totalCount = (state.workspace?.plans || []).length;
    let filtered = getFilteredPlans();
    if (state.wsSort.col) {
      filtered = [...filtered].sort((a, b) => comparePlans(a, b, state.wsSort.col, state.wsSort.dir));
    }

    const isFinal = state.workspace?.period?.kind === 'Chốt';
    pdfTh.classList.toggle('hidden', !isFinal);
    syncSortHeaderAria();

    if (countEl) {
      countEl.textContent =
        totalCount > 0 && filtered.length !== totalCount
          ? `${filtered.length}/${totalCount}`
          : '';
    }

    const prevScroll = wrap.scrollTop;

    if (filtered.length === 0) {
      tbody.innerHTML = '';
      table.classList.add('hidden');
      emptyEl.classList.remove('hidden');
      syncCheckAllHeader(filtered);
      return;
    }

    table.classList.remove('hidden');
    emptyEl.classList.add('hidden');

    const frag = document.createDocumentFragment();
    for (const p of filtered) {
      const tr = document.createElement('tr');
      const isSelected = p.supplier_id === state.inspectedId;
      tr.className = `qt-row${isSelected ? ' selected' : ''}${p.enabled ? '' : ' is-off'}`;
      tr.dataset.sid = String(p.supplier_id);
      tr.dataset.name = p.supplier;
      tr.setAttribute('aria-selected', isSelected ? 'true' : 'false');

      const checked = state.selectedIds.has(p.supplier_id) && p.sendable;
      const st = getPlanStatusMeta(p);
      const nameTip = p.recipients.length
        ? `${p.supplier} — ${p.recipients.join('; ')}`
        : `${p.supplier} — Chưa có email người nhận`;

      tr.innerHTML = `
        <td class="qt-col-chk">
          <input type="checkbox" class="queue-check" ${checked ? 'checked' : ''} ${p.sendable ? '' : 'disabled'} aria-label="Chọn ${esc(p.supplier)}" />
        </td>
        <td class="qt-col-name" data-value="${esc(p.supplier)}" title="${esc(nameTip)}">
          <div class="qt-name-cell">
            <span class="qt-sup-name">${esc(p.supplier)}</span>
          </div>
        </td>
        <td class="qt-col-ind">${buildEmailIndicatorHtml(p)}</td>
        <td class="qt-col-ind">${buildAttachmentIndicatorHtml(p, 'excel')}</td>
        <td class="qt-col-ind qt-col-pdf${isFinal ? '' : ' hidden'}">${isFinal ? buildAttachmentIndicatorHtml(p, 'pdf') : ''}</td>
        <td class="qt-col-status" data-value="${st.rank}">
          <span class="qt-status ${st.cls}" title="${esc((p.errors?.[0] || p.warnings?.[0] || st.label))}">
            <span class="qt-status-dot" aria-hidden="true"></span>
            <span>${esc(st.label)}</span>
          </span>
        </td>
      `;

      frag.appendChild(tr);
    }

    tbody.innerHTML = '';
    tbody.appendChild(frag);
    wrap.scrollTop = prevScroll;
    syncCheckAllHeader(filtered);
  }

  async function handleInlineRowAction(action, supplierId, fileType) {
    if (action === 'inspect-row') {
      state.inspectedId = supplierId;
      updateQueueSelectionClasses(false);
      renderInspector();
      return;
    }
    if (action === 'inspect-att') {
      state.inspectedId = supplierId;
      updateQueueSelectionClasses(false);
      renderInspector(fileType);
      return;
    }
    if (action === 'edit-sup') {
      state.inspectedId = supplierId;
      updateQueueSelectionClasses(false);
      renderInspector();
      const sup = (state.bootstrap?.suppliers || []).find((s) => s.id === supplierId);
      if (sup) openSupplierDrawer(sup, 'recipients');
      return;
    }
    if (action === 'approve') {
      const res = await api().approve_suggested_match(supplierId, fileType, true);
      if (res.ok) {
        if (res.bootstrap) applyBootstrap(res.bootstrap);
        applyWorkspace(res, true);
        state.selectedIds.add(supplierId);
        renderQueueList();
        renderActionBar();
        showToast('Đã xác nhận khớp file và ghi nhớ bí danh cho kỳ sau.', 'ok');
      } else {
        showToast(res.message || 'Không thể duyệt file.', 'err');
      }
      return;
    }
    if (action === 'pick') {
      state.inspectedId = supplierId;
      updateQueueSelectionClasses(false);
      const res = await api().pick_override_file(supplierId, fileType);
      if (res.cancelled) return;
      if (res.ok) {
        applyWorkspace(res, true);
        showToast('Đã gắn tệp đính kèm cho nhà cung cấp.', 'ok');
      } else {
        showToast(res.message || 'Tệp không hợp lệ.', 'err');
      }
    }
  }

  function renderInspector(highlightFileType = null) {
    const plan = (state.workspace?.plans || []).find((p) => p.supplier_id === state.inspectedId);
    if (!plan) {
      $('inspector-empty').classList.remove('hidden');
      $('inspector-content').classList.add('hidden');
      return;
    }
    $('inspector-empty').classList.add('hidden');
    $('inspector-content').classList.remove('hidden');

    $('insp-supplier-name').textContent = plan.supplier;
    $('insp-from').textContent = plan.from_display;
    $('insp-to').innerHTML = plan.recipients.length
      ? `<div class="email-chips">${plan.recipients.map((e) => `<span class="email-chip">${esc(e)}</span>`).join('')}</div>`
      : '<span class="text-err">Chưa điền email người nhận</span>';

    const hasCc = plan.cc && plan.cc.length > 0;
    $('insp-cc-label').classList.toggle('hidden', !hasCc);
    $('insp-cc').classList.toggle('hidden', !hasCc);
    if (hasCc) $('insp-cc').textContent = plan.cc.join('; ');

    $('insp-subject').textContent = plan.subject;
    $('insp-total-size').textContent = plan.total_bytes > 0 ? `Tổng: ${plan.total_size_label}` : '';

    // Notices
    const notices = $('insp-notices');
    notices.innerHTML = '';
    for (const err of plan.errors || []) {
      const d = document.createElement('div');
      d.className = 'insp-notice err';
      d.textContent = err;
      notices.appendChild(d);
    }
    for (const warn of plan.warnings || []) {
      const d = document.createElement('div');
      d.className = 'insp-notice warn';
      d.textContent = warn;
      notices.appendChild(d);
    }

    // Attachments
    const attBox = $('insp-attachments');
    attBox.innerHTML = '';
    for (const att of plan.attachments || []) {
      const card = document.createElement('div');
      card.className = 'att-card';
      card.dataset.ft = att.file_type;

      let badgeCls = 'badge-err';
      let badgeText = 'Thiếu file';
      if (att.status === 'exact') { badgeCls = 'badge-ok'; badgeText = 'Khớp chuẩn'; }
      else if (att.status === 'auto_matched') { badgeCls = 'badge-ok'; badgeText = 'Tự khớp'; }
      else if (att.status === 'manual_confirmed') { badgeCls = 'badge-ok'; badgeText = 'Đã duyệt tay'; }
      else if (att.status === 'needs_review') { badgeCls = 'badge-warn'; badgeText = `Gợi ý ${att.score}%`; }
      else if (att.status === 'ambiguous') { badgeCls = 'badge-err'; badgeText = 'Trùng nhiều file'; }
      else if (att.status === 'conflict') { badgeCls = 'badge-err'; badgeText = 'Xung đột NCC'; }
      else if (att.status === 'wrong_period') { badgeCls = 'badge-err'; badgeText = 'Sai kỳ tháng'; }
      else if (att.status === 'invalid_file') { badgeCls = 'badge-err'; badgeText = 'File lỗi'; }

      const actionBtns = [];
      if (att.needs_review) {
        actionBtns.push(`<button class="btn btn-warn btn-xs" data-ia="approve" data-ft="${att.file_type}">Chấp nhận &amp; nhớ bí danh</button>`);
      }
      if (att.file_name) {
        actionBtns.push(`<button class="btn btn-ghost btn-xs" data-ia="open" data-ft="${att.file_type}">Mở xem file</button>`);
      }
      actionBtns.push(`<button class="btn btn-secondary btn-xs" data-ia="pick" data-ft="${att.file_type}">${att.file_name ? 'Đổi file' : '+ Chọn file'}</button>`);

      // Candidate buttons when AMBIGUOUS or WRONG_PERIOD
      let candHtml = '';
      if ((att.status === 'ambiguous' || att.status === 'wrong_period') && att.candidates?.length) {
        const cbtns = att.candidates
          .map(
            (c, ci) =>
              `<button class="btn btn-secondary btn-xs" data-ia="cand" data-ft="${att.file_type}" data-ci="${ci}">Chọn: ${esc(c.name)} (${esc(c.size_label)})</button>`
          )
          .join('');
        candHtml = `<div class="att-actions">${cbtns}</div>`;
      }

      const showNoteLine = att.note && !att.is_ready;
      card.innerHTML = `
        <div class="att-card-top">
          <div class="att-name-wrap">
            <span class="badge ${badgeCls}">${badgeText}</span>
            <span class="att-name" title="${esc(att.file_name || att.expected_name)}">${esc(att.file_name || att.expected_name)}</span>
          </div>
          <span class="att-size tabular">${esc(att.size_label)}</span>
          <div class="att-actions">${actionBtns.join('')}</div>
        </div>
        ${showNoteLine ? `<div class="att-note">${esc(att.note)}</div>` : ''}
        ${candHtml}
      `;

      card.querySelectorAll('button[data-ia]').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const ia = btn.dataset.ia;
          const ft = btn.dataset.ft;
          if (ia === 'open') {
            const r = await api().open_attachment_file(plan.supplier_id, ft);
            if (!r.ok) showToast(r.message || 'Không mở được tệp.', 'err');
          } else if (ia === 'pick') {
            await handleInlineRowAction('pick', plan.supplier_id, ft);
          } else if (ia === 'approve') {
            await handleInlineRowAction('approve', plan.supplier_id, ft);
          } else if (ia === 'cand') {
            const r = await api().select_candidate_file(plan.supplier_id, ft, Number(btn.dataset.ci));
            if (r.ok) {
              applyWorkspace(r, true);
              showToast('Đã chọn tệp đính kèm.', 'ok');
            } else {
              showToast(r.message || 'Không chọn được tệp.', 'err');
            }
          }
        });
      });
      attBox.appendChild(card);
    }

    // Sandboxed HTML Preview vs Plaintext
    const iframe = $('send-preview-frame');
    const pre = $('send-preview-text');
    iframe.srcdoc = plan.body_html || '';
    pre.textContent = plan.body_text || '';
    iframe.classList.toggle('hidden', state.previewMode !== 'html');
    pre.classList.toggle('hidden', state.previewMode === 'html');

    if (highlightFileType) {
      const targetCard = attBox.querySelector(`.att-card[data-ft="${highlightFileType}"]`);
      if (targetCard) {
        targetCard.scrollIntoView({ block: 'nearest' });
        targetCard.classList.remove('flash-focus');
        void targetCard.offsetWidth;
        targetCard.classList.add('flash-focus');
        const primaryAction = targetCard.querySelector('button[data-ia="approve"], button[data-ia="cand"], button[data-ia="pick"]');
        if (primaryAction) primaryAction.focus();
      }
    }
  }

  function renderActionBar() {
    const plans = state.workspace?.plans || [];
    const selectedPlans = plans.filter((p) => p.sendable && state.selectedIds.has(p.supplier_id));
    const count = selectedPlans.length;
    const fileCount = selectedPlans.reduce((acc, p) => acc + p.attachments.filter((a) => a.is_ready).length, 0);
    const totalBytes = selectedPlans.reduce((acc, p) => acc + (p.total_bytes || 0), 0);

    $('action-summary').textContent =
      count > 0
        ? `Đã chọn ${count} NCC · ${fileCount} tệp · ${formatSize(totalBytes)}`
        : 'Chưa chọn nhà cung cấp nào';

    const gmailOk = Boolean(state.workspace?.gmail_ready);
    const sendBtn = $('btn-send-now');
    sendBtn.disabled = !gmailOk || count === 0;
    $('btn-send-now-label').textContent = `Gửi ngay (${count} mail)`;
    $('btn-send-test').disabled = !gmailOk;
  }

  // ==================== CONFIRMATION MODAL & FILTER-SAFE SEND ====================
  function showConfirmModal(title, bodyHtml, buttons) {
    $('confirm-title').textContent = title;
    $('confirm-body').innerHTML = bodyHtml;
    const actions = $('confirm-actions');
    actions.innerHTML = '';
    for (const b of buttons) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `btn ${b.cls || 'btn-secondary'}`;
      btn.textContent = b.label;
      btn.addEventListener('click', () => {
        $('confirm-modal').classList.add('hidden');
        if (b.onClick) b.onClick();
      });
      actions.appendChild(btn);
    }
    $('confirm-modal').classList.remove('hidden');
  }

  async function initiateBatchSend() {
    const selectedIds = [...state.selectedIds];
    const visibleIds = getFilteredPlans().map((p) => p.supplier_id);
    const check = await api().check_send_selection(selectedIds, visibleIds);

    if (check.total_selected === 0) {
      showToast('Chưa có nhà cung cấp hợp lệ nào được chọn.', 'warn');
      return;
    }

    const p = state.workspace.period;
    const periodLabel = `Tháng ${String(p.month).padStart(2, '0')}/${p.year} (${p.kind})`;

    if (check.needs_filter_confirm) {
      const visCount = check.total_selected - check.hidden_count;
      const hiddenNames = check.hidden_suppliers.slice(0, 6).join(', ');
      showConfirmModal(
        'Phát hiện nhà cung cấp đang bị ẩn bởi bộ lọc',
        `<p>Bạn đang bật bộ lọc tìm kiếm, nên có <strong>${check.hidden_count} nhà cung cấp đã tick đang bị ẩn</strong> (${esc(hiddenNames)}).</p>
         <p>Để tránh gửi nhầm ngoài ý muốn, bạn muốn gửi nhóm nào cho kỳ <strong>${esc(periodLabel)}</strong>?</p>`,
        [
          { label: 'Hủy', cls: 'btn-secondary' },
          ...(visCount > 0
            ? [{ label: `Chỉ gửi ${visCount} NCC đang hiển thị`, cls: 'btn-secondary', onClick: () => runBatchSend(selectedIds, visibleIds, true) }]
            : []),
          { label: `Gửi toàn bộ ${check.total_selected} NCC đã tick`, cls: 'btn-primary', onClick: () => runBatchSend(selectedIds, visibleIds, false) },
        ]
      );
      return;
    }

    showConfirmModal(
      'Xác nhận gửi email hàng loạt',
      `<p>Hệ thống sẽ gửi <strong>${check.total_selected} email</strong> cho kỳ <strong>${esc(periodLabel)}</strong> kèm giãn cách chống spam tự động.</p>
       <p>Bạn có thể bấm <em>Tạm dừng</em> hoặc <em>Hủy</em> bất cứ lúc nào trong quá trình gửi.</p>`,
      [
        { label: 'Quay lại kiểm tra', cls: 'btn-secondary' },
        { label: `Xác nhận gửi (${check.total_selected} mail)`, cls: 'btn-primary', onClick: () => runBatchSend(selectedIds, visibleIds, false) },
      ]
    );
  }

  async function runBatchSend(selectedIds, visibleIds, onlyVisible) {
    openDispatchDrawer(selectedIds.length);
    const res = await api().start_batch_send(selectedIds, visibleIds, onlyVisible);
    if (!res.ok) {
      $('dispatch-drawer').classList.add('hidden');
      showToast(res.message || 'Không khởi chạy được đợt gửi.', 'err');
    }
  }

  async function runRetryFailed() {
    openDispatchDrawer(0);
    const res = await api().retry_failed_batch();
    if (!res.ok) {
      $('dispatch-drawer').classList.add('hidden');
      showToast(res.message || 'Không có nhà cung cấp lỗi cần gửi lại.', 'warn');
    }
  }

  function openDispatchDrawer(estTotal) {
    state.batchPaused = false;
    $('disp-title').textContent = 'Đang gửi email cho nhà cung cấp...';
    $('disp-subtitle').textContent = 'Đang kết nối bảo mật tới Gmail SMTP...';
    $('disp-progress-fill').style.width = '0%';
    $('disp-kpi-progress').textContent = `0/${estTotal} (0%)`;
    $('disp-kpi-rate').textContent = '0.0 mail/phút';
    $('disp-kpi-eta').textContent = '--';
    $('disp-kpi-ok').textContent = '0';
    $('disp-kpi-fail').textContent = '0';
    $('disp-feed').innerHTML = '';

    $('btn-disp-pause').textContent = 'Tạm dừng';
    $('btn-disp-pause').classList.remove('hidden');
    $('btn-disp-pause').disabled = false;
    $('btn-disp-cancel').classList.remove('hidden');
    $('btn-disp-cancel').disabled = false;
    $('btn-disp-retry').classList.add('hidden');
    $('btn-disp-close').classList.add('hidden');
    $('dispatch-drawer').classList.remove('hidden');
  }

  // ==================== SUPPLIERS PAGE & DRAWER ====================
  function renderSuppliersTable() {
    const tbody = $('sup-table-body');
    const sups = state.bootstrap?.suppliers || [];
    const dups = state.bootstrap?.duplicate_emails || {};
    const dupKeys = Object.keys(dups);

    const dupBanner = $('sup-dup-alert');
    if (dupKeys.length) {
      dupBanner.textContent = `Cảnh báo: Phát hiện ${dupKeys.length} địa chỉ email đang dùng chung cho nhiều nhà cung cấp (${dupKeys.join(', ')}).`;
      dupBanner.classList.remove('hidden');
    } else {
      dupBanner.classList.add('hidden');
    }

    const kw = state.supSearch.trim().toLowerCase();
    const filtered = sups.filter((s) => {
      if (kw && !s.name.toLowerCase().includes(kw) && !s.recipients.join(' ').toLowerCase().includes(kw)) return false;
      if (state.supFilter === 'enabled') return s.enabled;
      if (state.supFilter === 'missing_email') return s.recipients.length === 0;
      return true;
    });

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 28px;" class="text-muted">Chưa có nhà cung cấp nào khớp bộ lọc.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    for (const s of filtered) {
      const tr = document.createElement('tr');
      const aliasBadges = (s.aliases || []).map((a) => `<span class="badge badge-muted">${esc(a)}</span>`).join(' ');
      const emailChips = s.recipients.length
        ? `<div class="email-chips">${s.recipients.map((e) => `<span class="email-chip${EMAIL_RE.test(e) ? '' : ' invalid'}">${esc(e)}</span>`).join('')}</div>`
        : '<span class="badge badge-err">Chưa điền email</span>';

      tr.innerHTML = `
        <td>
          <label class="switch">
            <input type="checkbox" ${s.enabled ? 'checked' : ''} data-toggle-id="${s.id}" />
            <span class="switch-slider"></span>
          </label>
        </td>
        <td>
          <div style="font-weight: 650;">${esc(s.name)}</div>
          ${aliasBadges ? `<div style="margin-top:4px; display:flex; gap:4px; flex-wrap:wrap;">${aliasBadges}</div>` : ''}
        </td>
        <td>${emailChips}</td>
        <td class="text-secondary">${esc(s.note || '—')}</td>
        <td style="text-align: right;">
          <button class="btn btn-ghost btn-xs" data-edit-id="${s.id}">Sửa</button>
          <button class="btn btn-ghost btn-xs text-err" data-del-id="${s.id}">Xóa</button>
        </td>
      `;

      tr.querySelector(`[data-toggle-id="${s.id}"]`).addEventListener('change', async (e) => {
        const res = await api().toggle_supplier(s.id, e.target.checked);
        if (res.ok) {
          applyBootstrap(res.bootstrap);
          applyWorkspace(res.workspace, true);
        }
      });
      tr.querySelector(`[data-edit-id="${s.id}"]`).addEventListener('click', () => openSupplierDrawer(s));
      tr.querySelector(`[data-del-id="${s.id}"]`).addEventListener('click', () => {
        showConfirmModal(
          `Xóa nhà cung cấp "${s.name}"?`,
          '<p>Nhà cung cấp sẽ bị xóa khỏi danh bạ. Lịch sử các email đã gửi trước đây vẫn được giữ nguyên.</p>',
          [
            { label: 'Hủy', cls: 'btn-secondary' },
            {
              label: 'Xác nhận xóa',
              cls: 'btn-danger',
              onClick: async () => {
                const res = await api().delete_supplier(s.id);
                if (res.ok) {
                  applyBootstrap(res.bootstrap);
                  applyWorkspace(res.workspace, true);
                  showToast(`Đã xóa ${s.name}.`, 'ok');
                }
              },
            },
          ]
        );
      });
      tbody.appendChild(tr);
    }
  }

  function openSupplierDrawer(sup, focusField = 'name') {
    $('sup-drawer-title').textContent = sup && sup.id ? `Chỉnh sửa: ${sup.name}` : 'Thêm nhà cung cấp mới';
    $('sup-edit-id').value = sup && sup.id ? String(sup.id) : '';
    $('sup-edit-name').value = sup?.name || '';
    $('sup-edit-recipients').value = (sup?.recipients || []).join('; ');
    $('sup-edit-aliases').value = (sup?.aliases || []).join(', ');
    $('sup-edit-note').value = sup?.note || '';
    $('sup-edit-enabled').checked = sup ? Boolean(sup.enabled) : true;
    $('sup-edit-error').classList.add('hidden');
    updateEmailChipPreview();
    $('supplier-drawer').classList.remove('hidden');
    setTimeout(() => {
      const target = focusField === 'recipients' ? $('sup-edit-recipients') : $('sup-edit-name');
      if (target) target.focus();
    }, 40);
  }

  function updateEmailChipPreview() {
    const raw = $('sup-edit-recipients').value;
    const parts = raw.split(/[;,\s]+/).map((x) => x.trim()).filter(Boolean);
    const box = $('sup-edit-email-chips');
    box.innerHTML = parts
      .map((e) => `<span class="email-chip${EMAIL_RE.test(e) ? '' : ' invalid'}">${esc(e)}</span>`)
      .join('');
  }

  // ==================== TEMPLATE STUDIO ====================
  let tplPreviewTimer = null;
  function scheduleTemplatePreview() {
    clearTimeout(tplPreviewTimer);
    tplPreviewTimer = setTimeout(refreshTemplatePreview, 140);
  }

  async function refreshTemplatePreview() {
    if (!api()) return;
    const p = state.workspace?.period || { month: 9, year: 2026, kind: 'Chốt' };
    const res = await api().preview_template({
      subject: $('tpl-subject').value,
      body: $('tpl-body').value,
      excel_name: $('tpl-excel').value,
      pdf_name: $('tpl-pdf').value,
      supplier_name: $('tpl-preview-sample-sup').value || 'ACE',
      month: p.month,
      year: p.year,
      kind: p.kind,
    });
    $('tpl-preview-subject').textContent = res.subject || '';
    $('tpl-excel-example').textContent = res.excel_example || '';
    $('tpl-pdf-example').textContent = res.pdf_example || '';
    $('tpl-preview-frame').srcdoc = res.body_html || '';
  }

  function insertTokenAtCursor(token) {
    const target = state.lastFocusedTplField || $('tpl-body');
    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? target.value.length;
    target.value = target.value.slice(0, start) + token + target.value.slice(end);
    target.focus();
    target.selectionStart = target.selectionEnd = start + token.length;
    scheduleTemplatePreview();
  }

  // ==================== HISTORY PAGE ====================
  async function loadHistory() {
    if (!api()) return;
    const filters = {
      month: $('hist-month').value,
      year: $('hist-year').value,
      kind: $('hist-kind').value,
      status: $('hist-status').value,
      keyword: $('hist-search').value,
    };
    const res = await api().query_history(filters);
    const st = res.stats;
    $('hist-kpi-total').textContent = String(st.total);
    $('hist-kpi-ok').textContent = String(st.ok_count);
    $('hist-kpi-fail').textContent = String(st.fail_count);
    $('hist-kpi-rate').textContent = `${st.success_rate}%`;
    $('btn-hist-retry').classList.toggle('hidden', st.fail_count === 0);

    const tbody = $('hist-table-body');
    if (!res.records.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 28px;" class="text-muted">Chưa có lịch sử gửi email nào khớp bộ lọc.</td></tr>';
      return;
    }
    tbody.innerHTML = res.records
      .map(
        (r) => `
      <tr>
        <td class="tabular text-secondary">${esc(r.sent_at)}</td>
        <td class="tabular">${esc(r.month)}/${esc(r.year)}</td>
        <td><span class="badge badge-muted">${esc(r.kind)}</span></td>
        <td style="font-weight: 600;">${esc(r.supplier)}</td>
        <td>
          <div style="font-size:12.5px;">${esc(r.recipients)}</div>
          <div class="text-muted" style="font-size:11.5px;">${esc(r.attachments || '(Không đính kèm)')}</div>
        </td>
        <td><span class="badge ${r.status === 'Thành công' ? 'badge-ok' : 'badge-err'}">${esc(r.status)}</span></td>
        <td class="text-secondary" style="font-size:12px;">${esc(r.detail)}</td>
      </tr>`
      )
      .join('');
  }

  // ==================== FIRST-RUN ONBOARDING WIZARD ====================
  function openWizard() {
    const boot = state.bootstrap;
    if (!boot) return;
    $('wiz-sender').value = boot.settings.sender || '';
    $('wiz-name').value = boot.settings.display_name || 'Ms. Ngoc Ha - Haesung Vina';
    $('wiz-password').value = '';
    $('wiz-step1-msg').classList.add('hidden');
    $('wiz-body').value = boot.templates.body || '';
    renderLogoThumb($('wiz-logo-thumb'), boot.settings.logo_data_uri);

    // Step 2 inline suppliers
    const supBox = $('wiz-suppliers-list');
    supBox.innerHTML = '';
    for (const sup of boot.suppliers || []) {
      const row = document.createElement('div');
      row.className = 'wiz-sup-row';
      row.innerHTML = `
        <div style="font-weight: 600;">${esc(sup.name)}</div>
        <input type="text" class="input input-sm" data-wiz-sup-id="${sup.id}" data-wiz-sup-name="${esc(sup.name)}" value="${esc(sup.recipients.join('; '))}" placeholder="email@nhacungcap.vn (cách nhau bằng dấu ;)" />
      `;
      supBox.appendChild(row);
    }

    setWizardStep(1);
    $('wizard-modal').classList.remove('hidden');
  }

  function setWizardStep(step) {
    state.wizStep = step;
    document.querySelectorAll('.wiz-step').forEach((el) => {
      const n = Number(el.dataset.step);
      el.classList.toggle('active', n === step);
      el.classList.toggle('done', n < step);
    });
    document.querySelectorAll('.wiz-pane').forEach((el) => {
      el.classList.toggle('active', Number(el.dataset.pane) === step);
    });
    $('btn-wiz-back').classList.toggle('hidden', step === 1);
    if (step === 1) {
      $('btn-wiz-next').textContent = state.bootstrap?.settings?.has_app_password
        ? 'Kiểm tra / Tiếp tục'
        : 'Kiểm tra Gmail & Tiếp tục';
    } else if (step === 2) {
      $('btn-wiz-next').textContent = 'Lưu danh bạ & Tiếp tục';
    } else {
      $('btn-wiz-next').textContent = 'Hoàn tất & Bắt đầu dùng';
      refreshWizardPreview();
    }
  }

  async function refreshWizardPreview() {
    if (!api()) return;
    const t = state.bootstrap.templates;
    const res = await api().preview_template({
      subject: t.subject,
      body: $('wiz-body').value,
      excel_name: t.excel_name,
      pdf_name: t.pdf_name,
      supplier_name: 'ACE',
      month: state.workspace?.period?.month || 9,
      year: state.workspace?.period?.year || 2026,
      kind: 'Tạm tính',
    });
    $('wiz-preview-frame').srcdoc = res.body_html || '';
  }

  async function handleWizardNext() {
    const nextBtn = $('btn-wiz-next');
    if (state.wizStep === 1) {
      const sender = $('wiz-sender').value.trim();
      const name = $('wiz-name').value.trim();
      const pw = $('wiz-password').value.trim();
      const fb = $('wiz-step1-msg');

      nextBtn.disabled = true;
      nextBtn.textContent = 'Đang kết nối Gmail...';
      try {
        const res = await api().test_and_save_gmail(sender, name, pw);
        fb.classList.remove('hidden', 'ok', 'err');
        fb.classList.add(res.ok ? 'ok' : 'err');
        fb.textContent = res.message;
        if (res.ok) {
          $('wiz-password').value = '';
          applyBootstrap(res.bootstrap);
          applyWorkspace(res.workspace, true);
          setWizardStep(2);
        }
      } finally {
        nextBtn.disabled = false;
        if (state.wizStep === 1) nextBtn.textContent = 'Kiểm tra Gmail & Tiếp tục';
      }
      return;
    }

    if (state.wizStep === 2) {
      nextBtn.disabled = true;
      try {
        const inputs = document.querySelectorAll('#wiz-suppliers-list input[data-wiz-sup-id]');
        for (const inp of inputs) {
          const val = inp.value.trim();
          if (!val) continue;
          const sid = Number(inp.dataset.wizSupId);
          const orig = (state.bootstrap.suppliers || []).find((s) => s.id === sid);
          const r = await api().upsert_supplier({
            id: sid,
            name: orig ? orig.name : inp.dataset.wizSupName,
            recipients: val,
            aliases: orig ? orig.aliases : [],
            note: orig ? orig.note : '',
            enabled: orig ? orig.enabled : true,
          });
          if (!r.ok) {
            showToast(`${inp.dataset.wizSupName}: ${r.message}`, 'err');
            return;
          }
          applyBootstrap(r.bootstrap);
          applyWorkspace(r.workspace, true);
        }
        setWizardStep(3);
      } finally {
        nextBtn.disabled = false;
      }
      return;
    }

    // Step 3 finish
    nextBtn.disabled = true;
    try {
      const t = state.bootstrap.templates;
      const rTpl = await api().save_templates({
        subject: t.subject,
        body: $('wiz-body').value,
        excel_name: t.excel_name,
        pdf_name: t.pdf_name,
      });
      if (!rTpl.ok) {
        showToast(rTpl.message, 'err');
        return;
      }
      const fin = await api().complete_onboarding();
      if (fin.ok) {
        applyBootstrap(fin.bootstrap);
        applyWorkspace(fin.workspace, false);
        $('wizard-modal').classList.add('hidden');
        showToast('Thiết lập hoàn tất! Hãy kéo thả thư mục báo cáo để bắt đầu gửi mail.', 'ok', 4500);
      } else {
        showToast(fin.message, 'err');
      }
    } finally {
      nextBtn.disabled = false;
    }
  }

  // ==================== PASSWORD LIVE COUNTER ====================
  function attachPasswordCounter(inputEl, hintEl) {
    inputEl.addEventListener('input', () => {
      const raw = inputEl.value;
      const clean = raw.replace(/[\s\-]+/g, '');
      if (!clean) {
        hintEl.textContent = 'Nhập 16 ký tự Mật khẩu ứng dụng từ Google (có dấu cách cũng được, app tự lọc).';
        hintEl.style.color = '';
        return;
      }
      if (/[^A-Za-z0-9]/.test(clean)) {
        hintEl.textContent = 'Cảnh báo: Chứa ký tự đặc biệt — đây có vẻ là mật khẩu Gmail thường, không phải App Password 16 ký tự.';
        hintEl.style.color = 'var(--err-fg)';
      } else if (clean.length === 16) {
        hintEl.textContent = 'Định dạng hợp lệ (16/16 ký tự App Password).';
        hintEl.style.color = 'var(--ok-fg)';
      } else {
        hintEl.textContent = `Đang nhập ${clean.length}/16 ký tự...`;
        hintEl.style.color = 'var(--warn-fg)';
      }
    });
  }

  // ==================== EVENT BINDINGS ====================
  function bindEvents() {
    // Sidebar navigation
    document.querySelectorAll('.nav-item').forEach((btn) => {
      btn.addEventListener('click', () => switchPage(btn.dataset.page));
    });
    $('sidebar-gmail-pill').addEventListener('click', () => {
      if (state.bootstrap?.settings?.gmail_ready) switchPage('settings');
      else openWizard();
    });
    $('btn-open-wizard').addEventListener('click', openWizard);
    $('btn-quick-theme').addEventListener('click', async () => {
      const cur = document.documentElement.getAttribute('data-theme');
      const next = cur === 'dark' ? 'light' : 'dark';
      const r = await api().set_theme(next);
      applyTheme(r.theme);
    });

    // External allowlisted links
    document.querySelectorAll('[data-ext]').forEach((btn) => {
      btn.addEventListener('click', () => api().open_external_url(btn.dataset.ext));
    });

    // Period & Mode controls
    const onPeriodChange = async () => {
      const m = Number($('ws-month').value);
      const y = Number($('ws-year').value);
      const activeKind = document.querySelector('#page-send .seg-btn.active')?.dataset.kind || 'Tạm tính';
      const res = await api().set_period_and_kind(m, y, activeKind);
      if (res.ok) applyWorkspace(res, false);
      else showToast(res.message || 'Kỳ gửi chưa hợp lệ.', 'warn');
    };
    $('ws-month').addEventListener('change', onPeriodChange);
    $('ws-year').addEventListener('change', onPeriodChange);
    document.querySelectorAll('#page-send .seg-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#page-send .seg-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        onPeriodChange();
      });
    });

    // Source pickers
    $('btn-pick-folder').addEventListener('click', async () => {
      const res = await api().pick_source_folder();
      if (!res.cancelled && res.ok) {
        applyWorkspace(res, false);
        showToast(`Đã quét ${res.source.scanned_count} tệp và tự khớp nhà cung cấp.`, 'ok');
      }
    });
    $('btn-pick-files').addEventListener('click', async () => {
      const res = await api().pick_source_files();
      if (!res.cancelled && res.ok) {
        applyWorkspace(res, false);
        showToast(`Đã nạp ${res.source.scanned_count} tệp báo cáo.`, 'ok');
      }
    });
    $('btn-refresh-ws').addEventListener('click', async () => {
      const res = await api().refresh_workspace();
      if (res.ok) {
        applyWorkspace(res, true);
        showToast('Đã làm mới danh sách.', 'info', 2000);
      }
    });

    // Queue Filters, Search, Sorting & Compact Table Delegation
    document.querySelectorAll('#ws-kpi-pills .kpi-pill').forEach((pill) => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('#ws-kpi-pills .kpi-pill').forEach((p) => p.classList.remove('active'));
        pill.classList.add('active');
        state.wsFilter = pill.dataset.filter;
        renderQueueList();
      });
    });
    $('ws-search').addEventListener('input', (e) => {
      state.wsSearch = e.target.value;
      renderQueueList();
    });
    document.querySelectorAll('#ws-queue-table thead th[data-sort] > .qt-sort-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const th = btn.closest('th[data-sort]');
        if (th) sortQueueInPlace(th.dataset.sort);
      });
    });
    $('ws-check-all').addEventListener('change', (e) => {
      const pool = getVisibleSelectablePlans(getFilteredPlans());
      if (e.target.checked) {
        for (const p of pool) state.selectedIds.add(p.supplier_id);
      } else {
        for (const p of pool) state.selectedIds.delete(p.supplier_id);
      }
      const tbody = $('ws-queue-body');
      for (const row of tbody.rows) {
        const sid = Number(row.dataset.sid);
        const cb = row.querySelector('.queue-check');
        if (cb && !cb.disabled) cb.checked = state.selectedIds.has(sid);
      }
      syncCheckAllHeader();
      renderActionBar();
    });
    $('ws-queue-body').addEventListener('change', (e) => {
      const cb = e.target.closest('input.queue-check');
      if (!cb || cb.disabled) return;
      const row = cb.closest('tr.qt-row');
      if (!row) return;
      const sid = Number(row.dataset.sid);
      if (cb.checked) state.selectedIds.add(sid);
      else state.selectedIds.delete(sid);
      syncCheckAllHeader();
      renderActionBar();
    });
    $('ws-queue-body').addEventListener('click', (e) => {
      const cb = e.target.closest('input.queue-check');
      if (cb) {
        e.stopPropagation();
        return;
      }
      const btn = e.target.closest('button[data-act]');
      if (btn) {
        e.stopPropagation();
        handleInlineRowAction(btn.dataset.act, Number(btn.dataset.sid), btn.dataset.ft);
        return;
      }
      const row = e.target.closest('tr.qt-row');
      if (!row) return;
      const sid = Number(row.dataset.sid);
      if (state.inspectedId !== sid) {
        state.inspectedId = sid;
        updateQueueSelectionClasses(false);
        renderInspector();
      }
    });
    $('btn-select-all-valid').addEventListener('click', () => {
      for (const p of getVisibleSelectablePlans(getFilteredPlans())) {
        state.selectedIds.add(p.supplier_id);
      }
      renderQueueList();
      renderActionBar();
    });
    $('btn-deselect-all').addEventListener('click', () => {
      state.selectedIds.clear();
      renderQueueList();
      renderActionBar();
    });
    $('chk-skip-sent').addEventListener('change', (e) => {
      state.skipSent = e.target.checked;
      for (const p of state.workspace?.plans || []) {
        if (p.sendable && p.already_sent) {
          if (state.skipSent) state.selectedIds.delete(p.supplier_id);
          else state.selectedIds.add(p.supplier_id);
        }
      }
      renderQueueList();
      renderActionBar();
    });

    // Inspector preview mode & edit
    document.querySelectorAll('.mini-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.mini-tab').forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        state.previewMode = tab.dataset.pmode;
        renderInspector();
      });
    });
    $('btn-insp-edit-sup').addEventListener('click', () => {
      const sup = (state.bootstrap?.suppliers || []).find((s) => s.id === state.inspectedId);
      if (sup) openSupplierDrawer(sup, 'recipients');
    });

    // Action Bar: Send Test & Send Now & Retry Failed
    $('btn-send-test').addEventListener('click', async () => {
      const btn = $('btn-send-test');
      btn.disabled = true;
      showToast('Đang gửi email thử nghiệm về Gmail của bạn...', 'info', 2500);
      try {
        const res = await api().send_test_to_self(state.inspectedId);
        showToast(res.message, res.ok ? 'ok' : 'err', 4500);
      } finally {
        btn.disabled = false;
      }
    });
    $('btn-send-now').addEventListener('click', initiateBatchSend);
    $('btn-retry-failed-bar').addEventListener('click', runRetryFailed);

    // Live Dispatch Controls
    $('btn-disp-pause').addEventListener('click', async () => {
      if (state.batchPaused) {
        await api().resume_batch();
        state.batchPaused = false;
        $('btn-disp-pause').textContent = 'Tạm dừng';
        $('disp-subtitle').textContent = 'Đang tiếp tục gửi các nhà cung cấp còn lại...';
      } else {
        await api().pause_batch();
        state.batchPaused = true;
        $('btn-disp-pause').textContent = 'Tiếp tục';
        $('disp-subtitle').textContent = 'Đang tạm dừng — bấm Tiếp tục bất kỳ lúc nào.';
      }
    });
    $('btn-disp-cancel').addEventListener('click', async () => {
      $('btn-disp-cancel').disabled = true;
      $('btn-disp-pause').disabled = true;
      $('disp-subtitle').textContent = 'Đang dừng an toàn sau email hiện tại...';
      await api().cancel_batch();
    });
    $('btn-disp-retry').addEventListener('click', runRetryFailed);
    $('btn-disp-close').addEventListener('click', () => $('dispatch-drawer').classList.add('hidden'));

    // Suppliers Page & Drawer
    $('btn-add-supplier').addEventListener('click', () => openSupplierDrawer(null));
    $('sup-search').addEventListener('input', (e) => {
      state.supSearch = e.target.value;
      renderSuppliersTable();
    });
    document.querySelectorAll('#sup-filter-seg .seg-btn').forEach((b) => {
      b.addEventListener('click', () => {
        document.querySelectorAll('#sup-filter-seg .seg-btn').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        state.supFilter = b.dataset.sfilter;
        renderSuppliersTable();
      });
    });
    $('sup-edit-recipients').addEventListener('input', updateEmailChipPreview);
    const closeSupDrawer = () => $('supplier-drawer').classList.add('hidden');
    $('btn-sup-drawer-close').addEventListener('click', closeSupDrawer);
    $('btn-sup-drawer-cancel').addEventListener('click', closeSupDrawer);
    $('btn-sup-drawer-save').addEventListener('click', async () => {
      const payload = {
        id: $('sup-edit-id').value,
        name: $('sup-edit-name').value,
        recipients: $('sup-edit-recipients').value,
        aliases: $('sup-edit-aliases').value,
        note: $('sup-edit-note').value,
        enabled: $('sup-edit-enabled').checked,
      };
      const res = await api().upsert_supplier(payload);
      const errBox = $('sup-edit-error');
      if (!res.ok) {
        errBox.textContent = res.message;
        errBox.classList.remove('hidden');
        return;
      }
      errBox.classList.add('hidden');
      applyBootstrap(res.bootstrap);
      applyWorkspace(res.workspace, true);
      closeSupDrawer();
      showToast('Đã lưu thông tin nhà cung cấp.', 'ok');
    });

    // Template Studio
    for (const id of ['tpl-subject', 'tpl-body', 'tpl-excel', 'tpl-pdf']) {
      const el = $(id);
      el.addEventListener('focus', () => { state.lastFocusedTplField = el; });
      el.addEventListener('input', scheduleTemplatePreview);
    }
    $('tpl-preview-sample-sup').addEventListener('change', refreshTemplatePreview);
    document.querySelectorAll('.var-chip').forEach((chip) => {
      chip.addEventListener('click', () => insertTokenAtCursor(chip.dataset.token));
    });
    $('btn-pick-logo').addEventListener('click', async () => {
      const res = await api().pick_logo_image();
      if (res.cancelled) return;
      if (res.ok) {
        applyBootstrap(res.bootstrap);
        applyWorkspace(res.workspace, true);
        refreshTemplatePreview();
        showToast(res.message, 'ok');
      } else {
        showToast(res.message, 'err');
      }
    });
    $('btn-clear-logo').addEventListener('click', async () => {
      const res = await api().clear_logo();
      if (res.ok) {
        applyBootstrap(res.bootstrap);
        applyWorkspace(res.workspace, true);
        refreshTemplatePreview();
        showToast(res.message, 'info');
      }
    });
    $('btn-tpl-save').addEventListener('click', async () => {
      const res = await api().save_templates({
        subject: $('tpl-subject').value,
        body: $('tpl-body').value,
        excel_name: $('tpl-excel').value,
        pdf_name: $('tpl-pdf').value,
      });
      if (res.ok) {
        applyBootstrap(res.bootstrap);
        applyWorkspace(res.workspace, true);
        showToast(res.message, 'ok');
      } else {
        showToast(res.message, 'err', 5000);
      }
    });
    $('btn-tpl-reset').addEventListener('click', async () => {
      const res = await api().reset_default_templates();
      if (res.ok) {
        applyBootstrap(res.bootstrap);
        applyWorkspace(res.workspace, true);
        refreshTemplatePreview();
        showToast('Đã khôi phục mẫu email mặc định của Haesung Vina.', 'ok');
      }
    });

    // History Page
    for (const id of ['hist-month', 'hist-year', 'hist-kind', 'hist-status']) {
      $(id).addEventListener('change', loadHistory);
    }
    let histSearchTimer = null;
    $('hist-search').addEventListener('input', () => {
      clearTimeout(histSearchTimer);
      histSearchTimer = setTimeout(loadHistory, 180);
    });
    $('btn-hist-export').addEventListener('click', async () => {
      const res = await api().export_history_excel();
      if (!res.cancelled && res.ok) showToast('Đang xuất báo cáo Excel...', 'info', 2000);
    });
    $('btn-hist-retry').addEventListener('click', () => {
      switchPage('send');
      runRetryFailed();
    });

    // Settings Page
    attachPasswordCounter($('set-app-password'), $('set-pw-hint'));
    attachPasswordCounter($('wiz-password'), $('wiz-pw-status'));
    $('btn-toggle-pw-vis').addEventListener('click', () => {
      const inp = $('set-app-password');
      const isPw = inp.type === 'password';
      inp.type = isPw ? 'text' : 'password';
      $('btn-toggle-pw-vis').textContent = isPw ? 'Ẩn' : 'Hiện';
    });
    $('btn-wiz-eye').addEventListener('click', () => {
      const inp = $('wiz-password');
      const isPw = inp.type === 'password';
      inp.type = isPw ? 'text' : 'password';
      $('btn-wiz-eye').textContent = isPw ? 'Ẩn' : 'Hiện';
    });

    $('btn-set-save-gmail').addEventListener('click', async () => {
      const btn = $('btn-set-save-gmail');
      btn.disabled = true;
      btn.textContent = 'Đang kiểm tra kết nối...';
      try {
        const res = await api().test_and_save_gmail(
          $('set-sender').value,
          $('set-display-name').value,
          $('set-app-password').value
        );
        if (res.ok) {
          $('set-app-password').value = '';
          $('set-app-password').type = 'password';
          $('btn-toggle-pw-vis').textContent = 'Hiện';
          applyBootstrap(res.bootstrap);
          applyWorkspace(res.workspace, true);
          showToast(res.message, 'ok', 4200);
        } else {
          showToast(res.message, 'err', 5000);
        }
      } finally {
        btn.disabled = false;
        btn.textContent = 'Kiểm tra & Lưu Gmail';
      }
    });
    $('btn-set-test-gmail').addEventListener('click', async () => {
      const btn = $('btn-set-test-gmail');
      btn.disabled = true;
      try {
        const res = await api().test_current_gmail();
        showToast(res.message, res.ok ? 'ok' : 'err', 4200);
      } finally {
        btn.disabled = false;
      }
    });
    $('btn-set-clear-pw').addEventListener('click', async () => {
      const res = await api().clear_app_password();
      applyBootstrap(res.bootstrap);
      applyWorkspace(res.workspace, true);
      showToast(res.message, 'info');
    });

    $('set-pacing').addEventListener('input', (e) => {
      $('set-pacing-val').textContent = `${Number(e.target.value).toFixed(1)}s`;
    });
    $('btn-pick-default-dir').addEventListener('click', async () => {
      const res = await api().pick_default_attach_folder();
      if (!res.cancelled && res.ok) {
        applyBootstrap(res.bootstrap);
        showToast('Đã cập nhật thư mục báo cáo mặc định.', 'ok');
      }
    });
    $('btn-set-save-general').addEventListener('click', async () => {
      const ccList = $('set-cc').value.split(/[;,\s]+/).map((x) => x.trim()).filter(Boolean);
      const res = await api().save_general_settings({
        cc: ccList,
        pacing_seconds: Number($('set-pacing').value),
        max_retries: Number($('set-retries').value),
      });
      if (res.ok) {
        applyBootstrap(res.bootstrap);
        applyWorkspace(res.workspace, true);
        showToast(res.message, 'ok');
      } else {
        showToast(res.message, 'err');
      }
    });

    document.querySelectorAll('#set-theme-seg .seg-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const r = await api().set_theme(btn.dataset.themeChoice);
        applyTheme(r.theme);
      });
    });
    $('btn-check-ota').addEventListener('click', async () => {
      showToast('Đang kiểm tra bản cập nhật trên GitHub Releases...', 'info', 2500);
      await api().check_ota_update(false);
    });
    $('btn-save-gh-token').addEventListener('click', async () => {
      const res = await api().save_github_token($('set-gh-token').value);
      $('set-gh-token').value = '';
      if (res.bootstrap) applyBootstrap(res.bootstrap);
      showToast(res.message, res.ok ? 'ok' : 'err');
    });

    // OTA Banner actions
    $('btn-ota-dismiss').addEventListener('click', () => $('ota-banner').classList.add('hidden'));
    $('btn-ota-install').addEventListener('click', () => {
      if (!state.otaInfo) return;
      showConfirmModal(
        `Cập nhật lên phiên bản v${state.otaInfo.version}`,
        `<p>Hệ thống sẽ tải gói cập nhật, xác thực mã băm toàn vẹn <strong>SHA-256</strong> và tự khởi động lại ứng dụng.</p>
         <p>Toàn bộ cài đặt, danh bạ nhà cung cấp, mật khẩu và lịch sử gửi của bạn được giữ nguyên 100%.</p>`,
        [
          { label: 'Để sau', cls: 'btn-secondary' },
          {
            label: 'Tải & Cập nhật ngay',
            cls: 'btn-primary',
            onClick: async () => {
              $('btn-ota-install').disabled = true;
              $('ota-progress-text').classList.remove('hidden');
              await api().apply_ota_update();
            },
          },
        ]
      );
    });

    // Wizard actions
    $('btn-wiz-close').addEventListener('click', () => $('wizard-modal').classList.add('hidden'));
    $('btn-wiz-back').addEventListener('click', () => setWizardStep(Math.max(1, state.wizStep - 1)));
    $('btn-wiz-next').addEventListener('click', handleWizardNext);
    $('wiz-body').addEventListener('input', () => {
      clearTimeout(tplPreviewTimer);
      tplPreviewTimer = setTimeout(refreshWizardPreview, 160);
    });
    $('btn-wiz-pick-logo').addEventListener('click', async () => {
      const res = await api().pick_logo_image();
      if (!res.cancelled && res.ok) {
        applyBootstrap(res.bootstrap);
        renderLogoThumb($('wiz-logo-thumb'), res.logo_data_uri);
        refreshWizardPreview();
      }
    });

    // Visual Drag-and-Drop feedback overlay
    window.addEventListener('dragenter', (e) => {
      e.preventDefault();
      state.dragCounter += 1;
      $('drop-overlay').classList.remove('hidden');
    });
    window.addEventListener('dragover', (e) => e.preventDefault());
    window.addEventListener('dragleave', () => {
      state.dragCounter = Math.max(0, state.dragCounter - 1);
      if (state.dragCounter === 0) $('drop-overlay').classList.add('hidden');
    });
    window.addEventListener('drop', (e) => {
      e.preventDefault();
      state.dragCounter = 0;
      $('drop-overlay').classList.add('hidden');
    });

    // Keyboard shortcuts & rapid Arrow/Space queue navigation
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        $('confirm-modal').classList.add('hidden');
        $('supplier-drawer').classList.add('hidden');
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        if (state.activePage === 'send') {
          e.preventDefault();
          $('ws-search').focus();
        }
        return;
      }

      if (state.activePage !== 'send') return;
      const anyModalOpen =
        !$('wizard-modal').classList.contains('hidden') ||
        !$('supplier-drawer').classList.contains('hidden') ||
        !$('dispatch-drawer').classList.contains('hidden') ||
        !$('confirm-modal').classList.contains('hidden');
      if (anyModalOpen) return;

      const activeTag = document.activeElement?.tagName;
      const isTextField =
        activeTag === 'TEXTAREA' ||
        activeTag === 'SELECT' ||
        (activeTag === 'INPUT' && document.activeElement.type !== 'checkbox');
      if (isTextField) return;

      const tbody = $('ws-queue-body');
      const rows = tbody ? [...tbody.rows] : [];
      if (!rows.length) return;

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Home' || e.key === 'End') {
        e.preventDefault();
        const curIdx = rows.findIndex((r) => Number(r.dataset.sid) === state.inspectedId);
        let nextIdx = curIdx;
        if (e.key === 'ArrowDown') nextIdx = curIdx < 0 ? 0 : Math.min(rows.length - 1, curIdx + 1);
        else if (e.key === 'ArrowUp') nextIdx = curIdx < 0 ? 0 : Math.max(0, curIdx - 1);
        else if (e.key === 'Home') nextIdx = 0;
        else if (e.key === 'End') nextIdx = rows.length - 1;

        const nextSid = Number(rows[nextIdx].dataset.sid);
        if (nextSid !== state.inspectedId) {
          state.inspectedId = nextSid;
          updateQueueSelectionClasses(true);
          renderInspector();
        }
        return;
      }

      if (e.key === ' ' && document.activeElement === $('ws-queue-wrap')) {
        e.preventDefault();
      }
    });
    window.addEventListener('keyup', (e) => {
      if (e.key !== ' ' || document.activeElement !== $('ws-queue-wrap')) return;
      if (state.activePage !== 'send') return;
      const tbody = $('ws-queue-body');
      const plan = (state.workspace?.plans || []).find((p) => p.supplier_id === state.inspectedId);
      if (tbody && plan && plan.sendable) {
        if (state.selectedIds.has(plan.supplier_id)) state.selectedIds.delete(plan.supplier_id);
        else state.selectedIds.add(plan.supplier_id);
        const row = tbody.querySelector(`tr[data-sid="${plan.supplier_id}"]`);
        const cb = row?.querySelector('.queue-check');
        if (cb) cb.checked = state.selectedIds.has(plan.supplier_id);
        syncCheckAllHeader();
        renderActionBar();
      }
    });
  }

  // ==================== PYTHON -> JS EVENT SUBSCRIPTIONS ====================
  function bindBusEvents() {
    window.AppBus.on('workspace:updated', (ws) => {
      $('drop-overlay').classList.add('hidden');
      switchPage('send');
      applyWorkspace(ws, false);
      showToast(`Đã nhận ${ws.source.scanned_count} tệp báo cáo và tự khớp nhà cung cấp.`, 'ok');
    });

    window.AppBus.on('batch:progress', (p) => {
      $('disp-progress-fill').style.width = `${p.percent}%`;
      $('disp-kpi-progress').textContent = `${p.completed}/${p.total} (${p.percent}%)`;
      $('disp-kpi-rate').textContent = `${Number(p.rate_per_min || 0).toFixed(1)} mail/phút`;
      $('disp-kpi-eta').textContent = p.completed >= p.total ? 'Hoàn tất' : formatEta(p.eta_seconds);
      $('disp-kpi-ok').textContent = String(p.ok_count);
      $('disp-kpi-fail').textContent = String(p.fail_count);
      if (p.current_supplier && !state.batchPaused) {
        $('disp-subtitle').textContent = `Đang gửi cho: ${p.current_supplier}...`;
      }
    });

    window.AppBus.on('batch:item', (item) => {
      const feed = $('disp-feed');
      const row = document.createElement('div');
      row.className = 'feed-item';
      row.innerHTML = `
        <div class="feed-item-left">
          <span class="badge ${item.ok ? 'badge-ok' : 'badge-err'}">${item.ok ? 'Thành công' : 'Lỗi'}</span>
          <span class="feed-sup">${esc(item.supplier)}</span>
          <span class="feed-msg" title="${esc(item.message)}">${esc(item.message)}</span>
        </div>
      `;
      feed.prepend(row);
    });

    window.AppBus.on('batch:done', (summary) => {
      $('btn-disp-pause').classList.add('hidden');
      $('btn-disp-cancel').classList.add('hidden');
      $('btn-disp-close').classList.remove('hidden');
      $('btn-disp-retry').classList.toggle('hidden', !summary.can_retry_failed);

      if (summary.state === 'cancelled') {
        $('disp-title').textContent = 'Đã dừng đợt gửi theo yêu cầu';
        $('disp-subtitle').textContent = `Đã gửi ${summary.ok_count}/${summary.total} thành công, ${summary.fail_count} lỗi.`;
      } else {
        $('disp-title').textContent = summary.fail_count === 0 ? 'Hoàn tất gửi email thành công!' : 'Hoàn tất đợt gửi (có mục bị lỗi)';
        $('disp-subtitle').textContent = `Thành công: ${summary.ok_count} · Lỗi: ${summary.fail_count} — Đã lưu toàn bộ vào lịch sử.`;
      }
      if (summary.workspace) applyWorkspace(summary.workspace, false);
    });

    window.AppBus.on('history:exported', (res) => {
      showToast(res.message, res.ok ? 'ok' : 'err', 4000);
    });

    window.AppBus.on('ota:checked', (info) => {
      if (info.has_update) {
        state.otaInfo = info;
        $('ota-banner-text').textContent = `Đã có phiên bản mới v${info.version} trên GitHub Releases!`;
        $('ota-banner').classList.remove('hidden');
        if (!info.silent) $('btn-ota-install').click();
      } else if (!info.silent) {
        showToast(info.error || info.message || 'Bạn đang dùng phiên bản mới nhất.', info.error ? 'err' : 'ok');
      }
    });

    window.AppBus.on('ota:progress', (p) => {
      $('ota-progress-text').textContent = `Đang tải v${p.version}: ${p.percent}%`;
    });

    window.AppBus.on('ota:restarting', (p) => {
      showToast(`Đã xác thực SHA-256 v${p.version}. Đang khởi động lại để hoàn tất cập nhật...`, 'ok', 5000);
    });

    window.AppBus.on('ota:error', (e) => {
      $('btn-ota-install').disabled = false;
      $('ota-progress-text').classList.add('hidden');
      showToast(`Cập nhật thất bại: ${e.message}`, 'err', 6000);
    });
  }

  // ==================== STARTUP ====================
  async function boot() {
    bindEvents();
    bindBusEvents();
    try {
      const data = await api().get_initial_data();
      applyBootstrap(data);
      applyWorkspace(data.workspace, false);
      if (data.needs_onboarding) {
        openWizard();
      }
    } catch (err) {
      showToast(`Lỗi khởi tạo giao diện: ${err}`, 'err', 6000);
    }
  }

  if (window.pywebview && window.pywebview.api) {
    boot();
  } else {
    window.addEventListener('pywebviewready', boot, { once: true });
  }
})();
