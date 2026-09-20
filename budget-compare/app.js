/** @typedef {{ id: string, type: '비용'|'자본'|'수익', name: string, prev: number, curr: number, prevPlan?: number, prevExec?: number, confirmed?: number, bizName?: string, note: string }} BudgetItem */

/** @type {'plan'|'exec'} 비용 전년 비교 기준 */
let costBaseline = 'exec';

const STORAGE_KEY = 'budget-compare-v1';
let saveTimer = null;
let isDirty = false;

/** 작업 저장에 사용 중인 파일 핸들. 있으면 [작업 저장]이 같은 파일에 덮어쓴다. */
let fileHandle = null;

/** 서버(Supabase)에 저장된 작업. 있으면 [서버 저장]이 같은 작업을 덮어쓴다. */
let currentWorkId = null;
let currentWorkTitle = '';
const API_BASE = '/api/budget';

function uid() {
  return crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2);
}

function getDefaultItems() {
  return [
    { id: uid(), type: '비용', name: '인건비', prev: 0, prevPlan: 100000, prevExec: 95000, curr: 110000, bizName: '', note: '' },
    { id: uid(), type: '비용', name: '운영비', prev: 0, prevPlan: 50000, prevExec: 48000, curr: 48000, bizName: '', note: '' },
    { id: uid(), type: '비용', name: '여비', prev: 0, prevPlan: 12000, prevExec: 11500, curr: 15000, bizName: '', note: '' },
    { id: uid(), type: '자본', name: '설비투자', prev: 200000, curr: 220000, bizName: '', note: '' },
    { id: uid(), type: '자본', name: '전산장비', prev: 30000, curr: 45000, bizName: '', note: '증액' },
    { id: uid(), type: '수익', name: '사업수익', prev: 300000, curr: 320000, bizName: '', note: '' },
    { id: uid(), type: '수익', name: '기타수익', prev: 20000, curr: 25000, bizName: '', note: '' },
  ];
}

/** @type {BudgetItem[]} */
let items = getDefaultItems();

function canUseStorage() {
  try {
    const k = '__budget_compare_test__';
    localStorage.setItem(k, '1');
    localStorage.removeItem(k);
    return true;
  } catch (_) {
    return false;
  }
}

function buildPayload() {
  return {
    version: 1,
    savedAt: new Date().toISOString(),
    costBaseline,
    prevYear: document.getElementById('prevYear')?.value || '2026',
    currYear: document.getElementById('currYear')?.value || '2027',
    items,
  };
}

/** 작업 중 임시 보관용. 영구 보관은 [작업 저장]이 담당한다. */
function saveState() {
  try {
    if (!canUseStorage()) {
      updateSaveStatus(null, true, '임시 보관 불가 — [작업 저장]으로 보관해 주세요');
      return false;
    }

    const payload = buildPayload();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    isDirty = false;
    updateSaveStatus(payload.savedAt);
    return true;
  } catch (err) {
    console.warn('임시 보관 실패:', err);
    updateSaveStatus(null, true, '임시 보관 실패 — [작업 저장]으로 보관해 주세요');
    return false;
  }
}

function markDirty() {
  isDirty = true;
  updateSaveStatus(null, false, null, true);
}

function scheduleSave() {
  markDirty();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => saveState(), 400);
}

function loadState() {
  try {
    if (!canUseStorage()) {
      updateSaveStatus(null, true, '임시 보관 불가 — [작업 불러오기]로 이어서 작업하세요');
      return false;
    }
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    return applyPayload(JSON.parse(raw));
  } catch (err) {
    console.warn('저장 불러오기 실패:', err);
    return false;
  }
}

/** 저장 데이터(로컬 저장·파일 공통)를 화면 상태에 반영한다. */
function applyPayload(data) {
  try {
    if (!data || !Array.isArray(data.items) || !data.items.length) return false;

    items = data.items.map((row) => ({
      id: row.id || uid(),
      type: row.type === '자본' || row.type === '수익' ? row.type : '비용',
      name: String(row.name || ''),
      prev: toNum(row.prev),
      curr: toNum(row.curr),
      prevPlan: row.prevPlan !== undefined ? toNum(row.prevPlan) : undefined,
      prevExec: row.prevExec !== undefined ? toNum(row.prevExec) : undefined,
      confirmed: row.confirmed !== undefined && row.confirmed !== null && row.confirmed !== ''
        ? toNum(row.confirmed)
        : undefined,
      bizName: String(row.bizName || ''),
      note: String(row.note || ''),
    }));

    if (data.costBaseline === 'plan' || data.costBaseline === 'exec') {
      costBaseline = data.costBaseline;
    }
    const prevEl = document.getElementById('prevYear');
    const currEl = document.getElementById('currYear');
    if (prevEl && data.prevYear) prevEl.value = data.prevYear;
    if (currEl && data.currYear) currEl.value = data.currYear;

    document.querySelectorAll('input[name="costBaseline"]').forEach((el) => {
      /** @type {HTMLInputElement} */ (el).checked = el.value === costBaseline;
    });

    isDirty = false;
    updateSaveStatus(data.savedAt || null);
    return true;
  } catch (err) {
    console.warn('저장 데이터 적용 실패:', err);
    return false;
  }
}

function buildFileName() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const prev = document.getElementById('prevYear')?.value || '';
  const curr = document.getElementById('currYear')?.value || '';
  const years = prev && curr ? `${prev}-${curr}_` : '';
  return `예산비교_${years}${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}.json`;
}

/** 작업 상태를 .json 파일로 저장. 같은 파일에 덮어쓸 수 있으면 그렇게 하고, 아니면 내려받기로 처리한다. */
async function saveToFile(useExistingHandle = true) {
  flushActiveCurrInput();
  const json = JSON.stringify(buildPayload(), null, 2);

  if (window.showSaveFilePicker) {
    try {
      if (!useExistingHandle || !fileHandle) {
        fileHandle = await window.showSaveFilePicker({
          suggestedName: buildFileName(),
          types: [{ description: '예산 비교 작업 파일', accept: { 'application/json': ['.json'] } }],
        });
      }
      const writable = await fileHandle.createWritable();
      await writable.write(json);
      await writable.close();
      isDirty = false;
      saveState();
      updateSaveStatus(new Date().toISOString(), false, `작업 저장됨 (${fileHandle.name})`);
      return true;
    } catch (err) {
      if (err && err.name === 'AbortError') return false;
      console.warn('파일 저장 실패, 내려받기로 대체:', err);
      fileHandle = null;
    }
  }

  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = buildFileName();
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  isDirty = false;
  saveState();
  updateSaveStatus(new Date().toISOString(), false, '작업 파일을 내려받았습니다');
  return true;
}

async function loadFromFile(file) {
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    if (!applyPayload(data)) {
      alert('이 파일에서 작업 내용을 찾지 못했습니다.\n엑셀 파일이라면 [엑셀 불러오기]를 사용해 주세요.');
      return;
    }
    currentWorkId = null;
    currentWorkTitle = '';
    render();
    saveState();
    updateSaveStatus(data.savedAt || null, false, `작업 불러옴 (${file.name})`);
  } catch (err) {
    console.error('작업 불러오기 실패:', err);
    alert('파일을 읽지 못했습니다.\n[작업 저장]으로 만든 .json 파일인지 확인해 주세요.');
  }
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`서버 응답 ${res.status} ${detail}`);
  }
  return res.status === 204 ? null : res.json();
}

function defaultWorkTitle() {
  const prev = document.getElementById('prevYear')?.value || '';
  const curr = document.getElementById('currYear')?.value || '';
  return `예산비교 ${prev}-${curr}`;
}

/** asNew=true면 이름을 새로 받아 별도 작업으로 저장한다. */
async function saveToServer(asNew = false) {
  flushActiveCurrInput();
  let title = currentWorkTitle;
  if (asNew || !currentWorkId) {
    const input = prompt('서버에 저장할 작업 이름을 입력하세요.', title || defaultWorkTitle());
    if (input === null) return false;
    title = input.trim() || defaultWorkTitle();
  }
  try {
    const body = JSON.stringify({ title, payload: buildPayload() });
    const saved = !asNew && currentWorkId
      ? await apiFetch(`/works/${currentWorkId}`, { method: 'PUT', body })
      : await apiFetch('/works', { method: 'POST', body });
    currentWorkId = saved.id;
    currentWorkTitle = saved.title;
    isDirty = false;
    saveState();
    updateSaveStatus(saved.updated_at, false, `서버에 저장됨 (${saved.title})`);
    return true;
  } catch (err) {
    console.error('서버 저장 실패:', err);
    updateSaveStatus(null, true, '서버 저장 실패 — [작업 저장]으로 파일에 보관해 주세요');
    return false;
  }
}

async function loadFromServer(id) {
  if (isDirty && !confirm('저장하지 않은 수정 내용이 있습니다.\n서버 작업으로 바꿀까요?')) return false;
  try {
    const work = await apiFetch(`/works/${id}`);
    if (!applyPayload(work.payload)) {
      alert('작업 내용을 화면에 적용하지 못했습니다.');
      return false;
    }
    currentWorkId = work.id;
    currentWorkTitle = work.title;
    fileHandle = null;
    render();
    saveState();
    updateSaveStatus(work.updated_at, false, `서버에서 불러옴 (${work.title})`);
    return true;
  } catch (err) {
    console.error('서버 불러오기 실패:', err);
    alert('서버에서 작업을 불러오지 못했습니다.');
    return false;
  }
}

async function openServerWorks() {
  let dlg = document.getElementById('serverWorksDialog');
  if (!dlg) {
    dlg = document.createElement('dialog');
    dlg.id = 'serverWorksDialog';
    dlg.innerHTML = `
      <h3 style="margin:0 0 12px">서버에 저장된 작업</h3>
      <div id="serverWorksList" style="min-width:420px;max-height:50vh;overflow:auto"></div>
      <div style="margin-top:12px;text-align:right"><button type="button" id="serverWorksClose">닫기</button></div>`;
    document.body.appendChild(dlg);
    dlg.querySelector('#serverWorksClose').addEventListener('click', () => dlg.close());
  }
  const list = dlg.querySelector('#serverWorksList');
  list.textContent = '불러오는 중…';
  dlg.showModal();

  try {
    const works = await apiFetch('/works');
    list.textContent = '';
    if (!works.length) {
      list.textContent = '저장된 작업이 없습니다.';
      return;
    }
    works.forEach((w) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid #eee';

      const label = document.createElement('span');
      label.style.flex = '1';
      const when = new Date(w.updated_at).toLocaleString('ko-KR');
      label.textContent = `${w.title}  (${when})`;   // textContent: 작업 이름을 HTML로 해석하지 않음

      const openBtn = document.createElement('button');
      openBtn.type = 'button';
      openBtn.textContent = '불러오기';
      openBtn.addEventListener('click', async () => {
        if (await loadFromServer(w.id)) dlg.close();
      });

      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.textContent = '삭제';
      delBtn.addEventListener('click', async () => {
        if (!confirm(`'${w.title}' 작업을 서버에서 삭제할까요?\n되돌릴 수 없습니다.`)) return;
        try {
          await apiFetch(`/works/${w.id}`, { method: 'DELETE' });
          if (currentWorkId === w.id) { currentWorkId = null; currentWorkTitle = ''; }
          row.remove();
        } catch (err) {
          console.error(err);
          alert('삭제하지 못했습니다.');
        }
      });

      row.append(label, openBtn, delBtn);
      list.appendChild(row);
    });
  } catch (err) {
    console.error(err);
    list.textContent = '목록을 불러오지 못했습니다.';
  }
}

function clearSavedState() {
  if (!confirm('화면을 샘플 데이터로 초기화할까요?\n저장해 둔 .json 파일은 지워지지 않습니다.')) return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (_) { /* ignore */ }
  fileHandle = null;
  currentWorkId = null;
  currentWorkTitle = ''; 
  items = getDefaultItems();
  costBaseline = 'exec';
  document.querySelectorAll('input[name="costBaseline"]').forEach((el) => {
    /** @type {HTMLInputElement} */ (el).checked = el.value === 'exec';
  });
  const prevEl = document.getElementById('prevYear');
  const currEl = document.getElementById('currYear');
  if (prevEl) prevEl.value = '2026';
  if (currEl) currEl.value = '2027';
  isDirty = false;
  render();
  updateSaveStatus(null);
}

function updateSaveStatus(iso, failed = false, customMsg = null, dirty = false) {
  const el = document.getElementById('saveStatus');
  if (!el) return;
  el.classList.remove('is-saved', 'is-error', 'is-dirty');

  if (failed) {
    el.classList.add('is-error');
    el.textContent = customMsg || '임시 보관 실패 — [작업 저장]으로 보관해 주세요';
    return;
  }
  if (dirty || isDirty) {
    el.classList.add('is-dirty');
    el.textContent = '수정 중…';
    return;
  }
  if (!iso) {
    el.textContent = customMsg || '작업 저장 안 됨';
    return;
  }
  if (customMsg) {
    el.classList.add('is-saved');
    el.textContent = customMsg;
    return;
  }
  const d = new Date(iso);
  const time = Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  el.classList.add('is-saved');
  el.textContent = time ? `저장됨 ${time}` : '저장됨';
}

/** 입력 중인 금년 칸 값도 저장 대상에 반영한다. */
function flushActiveCurrInput() {
  const active = document.activeElement;
  if (active instanceof HTMLInputElement && active.getAttribute('data-field') === 'curr') {
    const tr = active.closest('tr');
    const item = tr?.dataset?.id ? findItem(tr.dataset.id) : null;
    if (item) {
      item.curr = formatCurrField(active, '');
      if (tr) updateRowDelta(tr, item);
      refreshTotals();
    }
  }
}

function focusNextCurrInput(current) {
  const fields = Array.from(document.querySelectorAll('input.input-curr'));
  const idx = fields.indexOf(current);
  if (idx < 0) return;
  const next = fields[idx + 1];
  if (!next) {
    current.blur();
    return;
  }
  next.focus();
  next.select();
}

/**
 * 금액을 원 단위 정수로 읽는다.
 * 소수를 남기면 화면(반올림 표시)과 엑셀(원값)이 어긋나 행 합계가 1원씩 틀어진다.
 */
function toNum(v) {
  const n = Number(String(v).replace(/,/g, '').replace(/[^\d.-]/g, ''));
  return Number.isFinite(n) ? Math.round(n) : 0;
}

function formatWon(n) {
  return Math.round(n).toLocaleString('ko-KR');
}

/** 금년 입력란: 숫자만 남기고 천단위 콤마 표시 + Del/Backspace·커서 보정 */
function formatCurrField(el, inputType) {
  const caret = el.selectionStart ?? 0;
  const lastDigits = el.dataset.digits ?? '';
  let digits = String(el.value).replace(/[^\d]/g, '');
  const digitsBeforeCaret = String(el.value).slice(0, caret).replace(/[^\d]/g, '').length;

  // Del/Backspace가 콤마(,)만 지운 경우 → 숫자 한 자리도 함께 삭제
  if (
    digits === lastDigits &&
    digits.length > 0 &&
    (inputType === 'deleteContentForward' || inputType === 'deleteContentBackward')
  ) {
    if (inputType === 'deleteContentForward') {
      digits = digits.slice(0, digitsBeforeCaret) + digits.slice(digitsBeforeCaret + 1);
    } else if (digitsBeforeCaret > 0) {
      digits = digits.slice(0, digitsBeforeCaret - 1) + digits.slice(digitsBeforeCaret);
    }
  }

  if (digits === '') {
    el.value = '';
    el.dataset.digits = '';
    return 0;
  }

  const n = Number(digits);
  const formatted = formatWon(n);
  el.value = formatted;
  el.dataset.digits = digits;

  // 커서: 캐럿 앞 숫자 개수 유지 (Backspace로 숫자를 지운 경우 그 개수 그대로)
  let digitPos = digitsBeforeCaret;
  if (
    inputType === 'deleteContentBackward' &&
    lastDigits.length > 0 &&
    digits.length === lastDigits.length - 1
  ) {
    digitPos = digitsBeforeCaret; // 이미 한 자리 줄어든 상태의 before-count
  }
  if (
    inputType === 'deleteContentForward' &&
    lastDigits.length > 0 &&
    digits.length === lastDigits.length - 1
  ) {
    digitPos = digitsBeforeCaret;
  }

  const newPos = caretPosFromDigitCount(formatted, digitPos);
  try {
    el.setSelectionRange(newPos, newPos);
  } catch (_) { /* ignore */ }

  return n;
}

function caretPosFromDigitCount(formatted, digitCount) {
  if (digitCount <= 0) return 0;
  let seen = 0;
  for (let i = 0; i < formatted.length; i += 1) {
    if (/\d/.test(formatted[i])) {
      seen += 1;
      if (seen >= digitCount) return i + 1;
    }
  }
  return formatted.length;
}

function calcDiff(prev, curr) {
  return curr - prev;
}

function calcRate(prev, curr) {
  if (prev === 0) return curr === 0 ? 0 : null;
  return ((curr - prev) / prev) * 100;
}

function formatRate(rate) {
  if (rate === null) return '—';
  const sign = rate > 0 ? '+' : '';
  return `${sign}${rate.toFixed(1)}%`;
}

function formatDiff(diff) {
  const sign = diff > 0 ? '+' : '';
  return `${sign}${formatWon(diff)}`;
}

function deltaClass(diff) {
  if (diff > 0) return 'delta-up';
  if (diff < 0) return 'delta-down';
  return 'delta-zero';
}

function sumBy(list, key) {
  return list.reduce((acc, row) => acc + row[key], 0);
}

/**
 * 편성액(curr) 대비 확정예산(confirmed) 비교값.
 * confirmed가 없으면(=미확정) diff/rate는 null로 두고 화면에서 '—'로 표시한다.
 */
function getConfirmDiff(item) {
  const base = item.curr;
  const hasConfirmed = item.confirmed !== undefined && item.confirmed !== null;
  if (!hasConfirmed) return { hasConfirmed, base, confirmed: null, diff: null, rate: null };
  const diff = calcDiff(base, item.confirmed);
  const rate = calcRate(base, item.confirmed);
  return { hasConfirmed, base, confirmed: item.confirmed, diff, rate };
}

/** @param {BudgetItem} item */
function getPrev(item) {
  if (item.type === '비용') {
    if (costBaseline === 'plan') return item.prevPlan ?? item.prev ?? 0;
    return item.prevExec ?? item.prev ?? 0;
  }
  return item.prev;
}

function sumPrev(list) {
  return list.reduce((acc, row) => acc + getPrev(row), 0);
}

function costBaselineLabel() {
  return costBaseline === 'plan' ? '편성액' : '실행예산';
}

function updateCostBaselineLabels() {
  const label = costBaselineLabel();
  const outHead = document.getElementById('outlayPrevHead');
  const bizHead = document.getElementById('bizCostPrevHead');
  const printNote = document.getElementById('printBaselineNote');
  if (outHead) outHead.textContent = `전년 (비용: ${label})`;
  if (bizHead) bizHead.textContent = `비용 전년 (${label})`;
  if (printNote) printNote.textContent = `비용 비교 기준: 2026 ${label}`;
}

function printPage() {
  window.print();
}

function render() {
  updateCostBaselineLabels();
  const outlay = items.filter((i) => i.type === '비용' || i.type === '자본');
  const revenue = items.filter((i) => i.type === '수익');

  renderOutlay(outlay);
  renderRevenue(revenue);
  renderSummary(outlay, revenue);
  renderBizAggregates();
  renderConfirm(outlay);
}

function renderOutlay(rows) {
  const body = document.getElementById('outlayBody');
  const foot = document.getElementById('outlayFoot');
  body.innerHTML = '';

  rows.forEach((row) => {
    const prev = getPrev(row);
    const diff = calcDiff(prev, row.curr);
    const rate = calcRate(prev, row.curr);
    const tr = document.createElement('tr');
    tr.dataset.id = row.id;
    tr.innerHTML = `
      <td class="col-type">
        <select data-field="type" aria-label="구분">
          <option value="비용" ${row.type === '비용' ? 'selected' : ''}>비용</option>
          <option value="자본" ${row.type === '자본' ? 'selected' : ''}>자본</option>
        </select>
      </td>
      <td class="col-name"><input type="text" data-field="name" value="${escapeAttr(row.name)}" /></td>
      <td class="col-num"><span class="prev-readonly">${formatWon(prev)}</span></td>
      <td class="col-num">
        <input type="text" class="input-curr" data-field="curr" data-digits="${row.curr}" value="${formatWon(row.curr)}" inputmode="numeric" aria-label="금년 예산" autocomplete="off" />
      </td>
      <td class="col-num ${deltaClass(diff)}" data-role="diff">${formatDiff(diff)}</td>
      <td class="col-num ${deltaClass(diff)}" data-role="rate">${formatRate(rate)}</td>
      <td class="col-biz"><input type="text" data-field="bizName" value="${escapeAttr(row.bizName || '')}" /></td>
      <td class="col-note"><input type="text" data-field="note" value="${escapeAttr(row.note)}" /></td>
      <td class="col-action no-print"><button type="button" class="btn-icon" data-action="delete" title="삭제">×</button></td>
    `;
    body.appendChild(tr);
  });

  renderOutlayFoot(rows);
}

function renderOutlayFoot(rows) {
  const foot = document.getElementById('outlayFoot');
  const cost = rows.filter((r) => r.type === '비용');
  const capital = rows.filter((r) => r.type === '자본');
  const costPrev = sumPrev(cost);
  const costCurr = sumBy(cost, 'curr');
  const capPrev = sumPrev(capital);
  const capCurr = sumBy(capital, 'curr');
  const totalPrev = costPrev + capPrev;
  const totalCurr = costCurr + capCurr;

  foot.innerHTML = `
    <tr>
      <td colspan="2">소계 (비용)</td>
      <td class="col-num">${formatWon(costPrev)}</td>
      <td class="col-num">${formatWon(costCurr)}</td>
      <td class="col-num ${deltaClass(costCurr - costPrev)}">${formatDiff(costCurr - costPrev)}</td>
      <td class="col-num ${deltaClass(costCurr - costPrev)}">${formatRate(calcRate(costPrev, costCurr))}</td>
      <td colspan="3"></td>
    </tr>
    <tr>
      <td colspan="2">소계 (자본)</td>
      <td class="col-num">${formatWon(capPrev)}</td>
      <td class="col-num">${formatWon(capCurr)}</td>
      <td class="col-num ${deltaClass(capCurr - capPrev)}">${formatDiff(capCurr - capPrev)}</td>
      <td class="col-num ${deltaClass(capCurr - capPrev)}">${formatRate(calcRate(capPrev, capCurr))}</td>
      <td colspan="3"></td>
    </tr>
    <tr>
      <td colspan="2">합계 (비용+자본)</td>
      <td class="col-num">${formatWon(totalPrev)}</td>
      <td class="col-num">${formatWon(totalCurr)}</td>
      <td class="col-num ${deltaClass(totalCurr - totalPrev)}">${formatDiff(totalCurr - totalPrev)}</td>
      <td class="col-num ${deltaClass(totalCurr - totalPrev)}">${formatRate(calcRate(totalPrev, totalCurr))}</td>
      <td colspan="3"></td>
    </tr>
  `;
}

function renderRevenue(rows) {
  const body = document.getElementById('revenueBody');
  const foot = document.getElementById('revenueFoot');
  body.innerHTML = '';

  rows.forEach((row) => {
    const diff = calcDiff(row.prev, row.curr);
    const rate = calcRate(row.prev, row.curr);
    const tr = document.createElement('tr');
    tr.dataset.id = row.id;
    tr.innerHTML = `
      <td class="col-name"><input type="text" data-field="name" value="${escapeAttr(row.name)}" /></td>
      <td class="col-num"><span class="prev-readonly">${formatWon(row.prev)}</span></td>
      <td class="col-num">
        <input type="text" class="input-curr" data-field="curr" data-digits="${row.curr}" value="${formatWon(row.curr)}" inputmode="numeric" aria-label="금년 예산" autocomplete="off" />
      </td>
      <td class="col-num ${deltaClass(diff)}" data-role="diff">${formatDiff(diff)}</td>
      <td class="col-num ${deltaClass(diff)}" data-role="rate">${formatRate(rate)}</td>
      <td class="col-note"><input type="text" data-field="note" value="${escapeAttr(row.note)}" /></td>
      <td class="col-action no-print"><button type="button" class="btn-icon" data-action="delete" title="삭제">×</button></td>
    `;
    body.appendChild(tr);
  });

  renderRevenueFoot(rows);
}

function renderRevenueFoot(rows) {
  const foot = document.getElementById('revenueFoot');
  const prev = sumPrev(rows);
  const curr = sumBy(rows, 'curr');
  foot.innerHTML = `
    <tr>
      <td>합계</td>
      <td class="col-num">${formatWon(prev)}</td>
      <td class="col-num">${formatWon(curr)}</td>
      <td class="col-num ${deltaClass(curr - prev)}">${formatDiff(curr - prev)}</td>
      <td class="col-num ${deltaClass(curr - prev)}">${formatRate(calcRate(prev, curr))}</td>
      <td colspan="2"></td>
    </tr>
  `;
}

/** 편성액 대비 확정예산 섹션. 비용·자본 항목만 대상으로 한다 — 수익은 '확정'이라는 절차가 적용되지 않는다. */
function renderConfirm(rows) {
  const body = document.getElementById('confirmBody');
  if (!body) return;

  body.innerHTML = rows
    .map((row) => {
      const { hasConfirmed, base, confirmed, diff, rate } = getConfirmDiff(row);
      const cls = hasConfirmed ? deltaClass(diff) : 'delta-zero';
      return `
        <tr data-id="${row.id}">
          <td class="col-type">${escapeAttr(row.type)}</td>
          <td class="col-name">${escapeAttr(row.name)}</td>
          <td class="col-num"><span class="prev-readonly">${formatWon(base)}</span></td>
          <td class="col-num">
            <input type="text" class="input-curr" data-field="confirmed" data-digits="${hasConfirmed ? confirmed : ''}" value="${hasConfirmed ? formatWon(confirmed) : ''}" placeholder="미확정" inputmode="numeric" aria-label="확정예산" autocomplete="off" />
          </td>
          <td class="col-num ${cls}" data-role="diff">${hasConfirmed ? formatDiff(diff) : '—'}</td>
          <td class="col-num ${cls}" data-role="rate">${hasConfirmed ? formatRate(rate) : '—'}</td>
          <td class="col-biz">${escapeAttr(row.bizName || '')}</td>
        </tr>
      `;
    })
    .join('');

  renderConfirmFoot(rows);
}

/** 확정된 항목만 합산한 소계. 미확정 항목을 합계에 섞으면 '확정 기준 증감률'의 의미가 흐려진다. */
function renderConfirmFoot(rows) {
  const foot = document.getElementById('confirmFoot');
  if (!foot) return;

  const confirmedRows = rows.filter((r) => r.confirmed !== undefined && r.confirmed !== null);
  const planSum = sumBy(confirmedRows, 'curr');
  const confSum = confirmedRows.reduce((acc, r) => acc + r.confirmed, 0);
  const diff = confSum - planSum;

  foot.innerHTML = `
    <tr>
      <td colspan="2">합계 (확정 ${confirmedRows.length}/${rows.length}건)</td>
      <td class="col-num">${formatWon(planSum)}</td>
      <td class="col-num">${formatWon(confSum)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatDiff(diff)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatRate(calcRate(planSum, confSum))}</td>
      <td></td>
    </tr>
  `;
}

function renderSummary(outlay, revenue) {
  const body = document.getElementById('summaryBody');
  if (!body) return;

  const cost = outlay.filter((i) => i.type === '비용');
  const capital = outlay.filter((i) => i.type === '자본');

  const lines = [
    { label: '비용', prev: sumPrev(cost), curr: sumBy(cost, 'curr') },
    { label: '자본', prev: sumPrev(capital), curr: sumBy(capital, 'curr') },
    { label: '합계 (비용+자본)', prev: sumPrev(outlay), curr: sumBy(outlay, 'curr'), strong: true },
    { label: '수익', prev: sumPrev(revenue), curr: sumBy(revenue, 'curr'), gap: true },
  ];

  body.innerHTML = lines
    .map((l) => {
      const diff = l.curr - l.prev;
      const cls = [l.strong ? 'is-strong' : '', l.gap ? 'is-gap' : ''].filter(Boolean).join(' ');
      return `
        <tr class="${cls}">
          <td>${escapeAttr(l.label)}</td>
          <td class="col-num">${formatWon(l.prev)}</td>
          <td class="col-num">${formatWon(l.curr)}</td>
          <td class="col-num ${deltaClass(diff)}">${formatDiff(diff)}</td>
          <td class="col-num ${deltaClass(diff)}">${formatRate(calcRate(l.prev, l.curr))}</td>
        </tr>
      `;
    })
    .join('');
}

/**
 * 사업명을 묶음 기준으로 정규화한다.
 * 엑셀에서 들어온 이름은 줄바꿈·연속 공백·비단절 공백이 섞여 있어,
 * 그대로 두면 같은 사업이 두 줄로 나뉘어 합계가 어긋난다.
 */
function bizKey(name) {
  const s = String(name || '')
    .replace(/[\s\u00a0\u200b]+/g, ' ')
    .trim();
  return s || '(사업명 없음)';
}

/** @returns {{ name: string, costPrev: number, costCurr: number, capPrev: number, capCurr: number, revPrev: number, revCurr: number }[]} */
function aggregateByBiz() {
  /** @type {Map<string, { name: string, costPrev: number, costCurr: number, capPrev: number, capCurr: number, revPrev: number, revCurr: number }>} */
  const map = new Map();

  items.forEach((row) => {
    const name = bizKey(row.bizName);
    if (!map.has(name)) {
      map.set(name, {
        name,
        costPrev: 0,
        costCurr: 0,
        capPrev: 0,
        capCurr: 0,
        revPrev: 0,
        revCurr: 0,
      });
    }
    const agg = map.get(name);
    const prev = getPrev(row);
    if (row.type === '비용') {
      agg.costPrev += prev;
      agg.costCurr += row.curr;
    } else if (row.type === '자본') {
      agg.capPrev += prev;
      agg.capCurr += row.curr;
    } else if (row.type === '수익') {
      agg.revPrev += prev;
      agg.revCurr += row.curr;
    }
  });

  return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name, 'ko'));
}

function renderBizAggregates() {
  const rows = aggregateByBiz();
  const outBody = document.getElementById('bizOutlayBody');
  const outFoot = document.getElementById('bizOutlayFoot');
  const revBody = document.getElementById('bizRevenueBody');
  const revFoot = document.getElementById('bizRevenueFoot');
  if (!outBody || !revBody) return;

  outBody.innerHTML = '';
  revBody.innerHTML = '';

  let sumCostPrev = 0;
  let sumCostCurr = 0;
  let sumCapPrev = 0;
  let sumCapCurr = 0;
  let sumRevPrev = 0;
  let sumRevCurr = 0;

  rows.forEach((r) => {
    const totalPrev = r.costPrev + r.capPrev;
    const totalCurr = r.costCurr + r.capCurr;
    const diff = totalCurr - totalPrev;
    sumCostPrev += r.costPrev;
    sumCostCurr += r.costCurr;
    sumCapPrev += r.capPrev;
    sumCapCurr += r.capCurr;
    sumRevPrev += r.revPrev;
    sumRevCurr += r.revCurr;

    if (r.costPrev || r.costCurr || r.capPrev || r.capCurr) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="col-biz-name">${escapeAttr(r.name)}</td>
        <td class="col-num">${formatWon(r.costPrev)}</td>
        <td class="col-num">${formatWon(r.costCurr)}</td>
        <td class="col-num">${formatWon(r.capPrev)}</td>
        <td class="col-num">${formatWon(r.capCurr)}</td>
        <td class="col-num">${formatWon(totalPrev)}</td>
        <td class="col-num">${formatWon(totalCurr)}</td>
        <td class="col-num ${deltaClass(diff)}">${formatDiff(diff)}</td>
        <td class="col-num ${deltaClass(diff)}">${formatRate(calcRate(totalPrev, totalCurr))}</td>
      `;
      outBody.appendChild(tr);
    }

    if (r.revPrev || r.revCurr) {
      const revDiff = r.revCurr - r.revPrev;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="col-biz-name">${escapeAttr(r.name)}</td>
        <td class="col-num">${formatWon(r.revPrev)}</td>
        <td class="col-num">${formatWon(r.revCurr)}</td>
        <td class="col-num ${deltaClass(revDiff)}">${formatDiff(revDiff)}</td>
        <td class="col-num ${deltaClass(revDiff)}">${formatRate(calcRate(r.revPrev, r.revCurr))}</td>
      `;
      revBody.appendChild(tr);
    }
  });

  const outTotalPrev = sumCostPrev + sumCapPrev;
  const outTotalCurr = sumCostCurr + sumCapCurr;
  const outDiff = outTotalCurr - outTotalPrev;
  outFoot.innerHTML = `
    <tr>
      <td>합계</td>
      <td class="col-num">${formatWon(sumCostPrev)}</td>
      <td class="col-num">${formatWon(sumCostCurr)}</td>
      <td class="col-num">${formatWon(sumCapPrev)}</td>
      <td class="col-num">${formatWon(sumCapCurr)}</td>
      <td class="col-num">${formatWon(outTotalPrev)}</td>
      <td class="col-num">${formatWon(outTotalCurr)}</td>
      <td class="col-num ${deltaClass(outDiff)}">${formatDiff(outDiff)}</td>
      <td class="col-num ${deltaClass(outDiff)}">${formatRate(calcRate(outTotalPrev, outTotalCurr))}</td>
    </tr>
  `;

  const revDiff = sumRevCurr - sumRevPrev;
  revFoot.innerHTML = `
    <tr>
      <td>합계</td>
      <td class="col-num">${formatWon(sumRevPrev)}</td>
      <td class="col-num">${formatWon(sumRevCurr)}</td>
      <td class="col-num ${deltaClass(revDiff)}">${formatDiff(revDiff)}</td>
      <td class="col-num ${deltaClass(revDiff)}">${formatRate(calcRate(sumRevPrev, sumRevCurr))}</td>
    </tr>
  `;
}

function escapeAttr(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;');
}

function findItem(id) {
  return items.find((i) => i.id === id);
}

function updateRowDelta(tr, item) {
  const prev = getPrev(item);
  const diff = calcDiff(prev, item.curr);
  const rate = calcRate(prev, item.curr);
  const diffEl = tr.querySelector('[data-role="diff"]');
  const rateEl = tr.querySelector('[data-role="rate"]');
  if (diffEl) {
    diffEl.textContent = formatDiff(diff);
    diffEl.className = `col-num ${deltaClass(diff)}`;
  }
  if (rateEl) {
    rateEl.textContent = formatRate(rate);
    rateEl.className = `col-num ${deltaClass(diff)}`;
  }
}

function updateConfirmRowDelta(tr, item) {
  const { hasConfirmed, diff, rate } = getConfirmDiff(item);
  const cls = hasConfirmed ? deltaClass(diff) : 'delta-zero';
  const diffEl = tr.querySelector('[data-role="diff"]');
  const rateEl = tr.querySelector('[data-role="rate"]');
  if (diffEl) {
    diffEl.textContent = hasConfirmed ? formatDiff(diff) : '—';
    diffEl.className = `col-num ${cls}`;
  }
  if (rateEl) {
    rateEl.textContent = hasConfirmed ? formatRate(rate) : '—';
    rateEl.className = `col-num ${cls}`;
  }
}

function refreshTotals() {
  const outlay = items.filter((i) => i.type === '비용' || i.type === '자본');
  const revenue = items.filter((i) => i.type === '수익');
  renderOutlayFoot(outlay);
  renderRevenueFoot(revenue);
  renderSummary(outlay, revenue);
  renderBizAggregates();
  renderConfirmFoot(outlay);
}

function onTableChange(e) {
  const target = e.target;
  if (!(target instanceof HTMLElement)) return;
  const tr = target.closest('tr');
  if (!tr || !tr.dataset.id) return;

  const item = findItem(tr.dataset.id);
  if (!item) return;

  if (target.matches('[data-action="delete"]')) {
    items = items.filter((i) => i.id !== item.id);
    render();
    scheduleSave();
    return;
  }

  const field = target.getAttribute('data-field');
  if (!field) return;

  // 금년 입력은 input 이벤트에서 처리 — change 시 표 전체 재그리지 않음
  if (field === 'curr') {
    item.curr = formatCurrField(/** @type {HTMLInputElement} */ (target), e.inputType);
    updateRowDelta(tr, item);
    refreshTotals();
    scheduleSave();
    return;
  }

  if (field === 'type') {
    const newType = /** @type {'비용'|'자본'} */ (target.value);
    if (newType === '비용' && item.type !== '비용') {
      const p = item.prev ?? 0;
      item.prevPlan = p;
      item.prevExec = p;
      item.prev = 0;
    } else if (newType === '자본' && item.type === '비용') {
      item.prev = getPrev(item);
      delete item.prevPlan;
      delete item.prevExec;
    }
    item.type = newType;
    render();
    scheduleSave();
    return;
  }
  if (field === 'name' || field === 'note' || field === 'bizName') {
    item[field] = /** @type {HTMLInputElement} */ (target).value;
  }
  render();
  scheduleSave();
}

function bindTables() {
  ['outlayTable', 'revenueTable'].forEach((id) => {
    const table = document.getElementById(id);
    table.addEventListener('change', onTableChange);
    table.addEventListener('click', (e) => {
      const target = e.target;
      if (target instanceof HTMLElement && target.matches('[data-action="delete"]')) {
        onTableChange(e);
      }
    });
    table.addEventListener('input', (e) => {
      const target = e.target;
      if (!(target instanceof HTMLInputElement)) return;
      const field = target.getAttribute('data-field');
      const tr = target.closest('tr');
      if (!tr || !tr.dataset.id) return;
      const item = findItem(tr.dataset.id);
      if (!item) return;

      if (field === 'curr') {
        if (!target.dataset.digits) {
          target.dataset.digits = String(item.curr).replace(/[^\d]/g, '');
        }
        item.curr = formatCurrField(target, e.inputType);
        updateRowDelta(tr, item);
        scheduleTotalsRefresh();
        scheduleSave();
        return;
      }
      if (field === 'name' || field === 'note' || field === 'bizName') {
        item[field] = target.value;
        if (field === 'bizName') scheduleTotalsRefresh();
        scheduleSave();
      }
    });
    table.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const target = e.target;
      if (!(target instanceof HTMLInputElement)) return;
      if (target.getAttribute('data-field') !== 'curr') return;
      e.preventDefault();

      const tr = target.closest('tr');
      if (!tr || !tr.dataset.id) return;
      const item = findItem(tr.dataset.id);
      if (!item) return;

      item.curr = formatCurrField(target, '');
      updateRowDelta(tr, item);
      refreshTotals();
      saveState();
      focusNextCurrInput(target);
    });
    table.addEventListener('focusout', (e) => {
      const target = e.target;
      if (!(target instanceof HTMLInputElement)) return;
      if (target.getAttribute('data-field') !== 'curr') return;
      const tr = target.closest('tr');
      if (!tr || !tr.dataset.id) return;
      const item = findItem(tr.dataset.id);
      if (!item) return;
      item.curr = formatCurrField(target, '');
      updateRowDelta(tr, item);
      refreshTotals();
      saveState();
    });
  });
}

/**
 * confirmTable 전용 바인딩. outlayTable/revenueTable과 달리 행 추가·삭제나
 * type/name 편집이 없고 'confirmed' 입력 한 칸만 다루므로 onTableChange를
 * 공유하지 않고 별도로 둔다.
 */
function bindConfirmTable() {
  const table = document.getElementById('confirmTable');
  if (!table) return;

  const applyConfirmedInput = (target, inputType) => {
    const tr = target.closest('tr');
    if (!tr || !tr.dataset.id) return null;
    const item = findItem(tr.dataset.id);
    if (!item) return null;
    if (!target.dataset.digits && item.confirmed !== undefined) {
      target.dataset.digits = String(item.confirmed);
    }
    const n = formatCurrField(target, inputType);
    item.confirmed = target.dataset.digits === '' ? undefined : n;
    updateConfirmRowDelta(tr, item);
    return item;
  };

  table.addEventListener('input', (e) => {
    const target = e.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (target.getAttribute('data-field') !== 'confirmed') return;
    if (!applyConfirmedInput(target, e.inputType)) return;
    scheduleTotalsRefresh();
    scheduleSave();
  });

  table.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const target = e.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (target.getAttribute('data-field') !== 'confirmed') return;
    e.preventDefault();
    if (!applyConfirmedInput(target, '')) return;
    refreshTotals();
    saveState();
    focusNextCurrInput(target);
  });

  table.addEventListener('focusout', (e) => {
    const target = e.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (target.getAttribute('data-field') !== 'confirmed') return;
    if (!applyConfirmedInput(target, '')) return;
    refreshTotals();
    saveState();
  });
}

let totalsTimer = null;
function scheduleTotalsRefresh() {
  clearTimeout(totalsTimer);
  totalsTimer = setTimeout(refreshTotals, 200);
}

function openAddDialog() {
  document.getElementById('addDialog').showModal();
}

function closeAddDialog() {
  document.getElementById('addDialog').close();
}

function onAddSubmit(e) {
  e.preventDefault();
  const type = /** @type {'비용'|'자본'|'수익'} */ (document.getElementById('newType').value);
  const name = document.getElementById('newName').value.trim();
  if (!name) return;

  const prevVal = toNum(document.getElementById('newPrev').value);
  const currVal = toNum(document.getElementById('newCurr').value);
  const note = document.getElementById('newNote').value.trim();

  if (type === '비용') {
    items.push({
      id: uid(),
      type,
      name,
      prev: 0,
      prevPlan: prevVal,
      prevExec: prevVal,
      curr: currVal,
      bizName: '',
      note,
    });
  } else {
    items.push({
      id: uid(),
      type,
      name,
      prev: prevVal,
      curr: currVal,
      bizName: '',
      note,
    });
  }
  document.getElementById('addForm').reset();
  document.getElementById('newNote').value = '신규';
  closeAddDialog();
  render();
  scheduleSave();
}

/**
 * 엑셀 기대 형식 (27년도 예산요구안.xlsx 기준):
 * - 시트: `비용예산…` / `자본예산…` / `수익예산…` 읽음, `27년 사업명` 무시
 * - 항목명: 세부활동 (없으면 WBS명·오더명)
 * - 비용 전년: `2026 편성액` + `26년 실행예산` (화면에서 선택)
 * - 자본·수익 전년: `2026 편성액`
 * - 금년: `27년 예산요구안` (비어 있으면 0 → 화면에서 입력)
 */
function detectSheetType(sheetName) {
  const name = String(sheetName || '').replace(/\s+/g, '');
  if (name.includes('사업명') && !name.includes('예산')) return null;
  if (name.includes('수익')) return '수익';
  if (name.includes('자본')) return '자본';
  if (name.includes('비용') || name.includes('경비')) return '비용';
  return null;
}

function normHeader(h) {
  return String(h || '')
    .replace(/\r?\n/g, '')
    .replace(/\s+/g, '')
    .toLowerCase();
}

/** 헤더가 keys 중 하나와 같거나 포함되면 해당 셀 값 반환 */
function pickField(row, keys, mode = 'exact') {
  const entries = Object.entries(row);
  const norms = keys.map(normHeader);

  for (const [k, v] of entries) {
    if (v === undefined || v === null || String(v).trim() === '') continue;
    const nk = normHeader(k);
    for (const key of norms) {
      if (!key) continue;
      if (mode === 'exact' && nk === key) return v;
      if (mode === 'includes' && (nk.includes(key) || key.includes(nk))) return v;
    }
  }
  return '';
}

function pickCostPlan(row) {
  const preferred = pickField(row, ['2026편성액', '전년', '전년도', '전년예산', '전년편성'], 'includes');
  if (preferred !== '') return toNum(preferred);
  for (const [k, v] of Object.entries(row)) {
    const nk = normHeader(k);
    if (nk.includes('2026') && nk.includes('편성') && !nk.includes('실행')) return toNum(v);
  }
  for (const [k, v] of Object.entries(row)) {
    const nk = normHeader(k);
    if (nk.includes('편성액') && !nk.includes('27') && !nk.includes('2027') && !nk.includes('요구') && !nk.includes('실행')) {
      return toNum(v);
    }
  }
  return 0;
}

function pickCostExec(row) {
  for (const [k, v] of Object.entries(row)) {
    const nk = normHeader(k);
    if (nk.includes('실행예산')) return toNum(v);
  }
  const exec = pickField(row, ['26년실행예산', '실행예산'], 'includes');
  if (exec !== '') return toNum(exec);
  return 0;
}

function pickCapitalPrev(row) {
  return pickCostPlan(row);
}

function pickCurrAmount(row) {
  const preferred = pickField(
    row,
    ['27년예산요구안', '2027편성액', '금년', '금년도', '금년예산', '예산요구안'],
    'includes'
  );
  if (preferred !== '') return toNum(preferred);

  for (const [k, v] of Object.entries(row)) {
    const nk = normHeader(k);
    if ((nk.includes('27') || nk.includes('2027')) && (nk.includes('요구') || nk.includes('편성') || nk.includes('예산'))) {
      return toNum(v);
    }
  }
  return 0;
}

function mapRowToItem(row, type) {
  const name = String(
    pickField(row, ['세부활동', '항목명', '항목', 'WBS명', '오더명', '예산과목', '내역'], 'exact') ||
    pickField(row, ['세부활동', 'WBS명', '오더명'], 'includes')
  ).trim();

  if (!name || /^(합계|소계|총계|계)$/.test(name.replace(/\s+/g, ''))) {
    return null;
  }

  const bizName = String(
    pickField(row, ['사업명(2027년)', '사업명 (2027년)', '사업명(2027년)'], 'includes') ||
    pickField(row, ['사업명(2026년)', '사업명 (2026년)'], 'includes') ||
    ''
  ).trim();

  // 비고: 엑셀 비고·구분1·구분2·소분류를 합치지 않고 비고 컬럼만 (없으면 소분류)
  const note =
    String(pickField(row, ['비고', '메모'], 'exact') || '').trim() ||
    String(pickField(row, ['소분류'], 'exact') || '').trim();

  const prevPlan = type === '비용' ? pickCostPlan(row) : 0;
  const prevExec = type === '비용' ? pickCostExec(row) : 0;
  const prev = type === '비용' ? 0 : pickCapitalPrev(row);
  const curr = pickCurrAmount(row);
  if (!prevPlan && !prevExec && !prev && !curr && !name) return null;

  /** @type {BudgetItem} */
  const item = {
    id: uid(),
    type,
    name,
    prev,
    curr,
    bizName,
    note,
  };
  if (type === '비용') {
    item.prevPlan = prevPlan;
    item.prevExec = prevExec;
  }
  return item;
}

function importSheet(file) {
  const reader = new FileReader();
  reader.onload = (ev) => {
    try {
      if (typeof XLSX === 'undefined') {
        alert('엑셀 라이브러리를 불러오지 못했습니다. 네트워크 연결을 확인하세요.');
        return;
      }

      const data = new Uint8Array(ev.target.result);
      const wb = XLSX.read(data, { type: 'array' });
      const mapped = [];
      const usedSheets = [];

      wb.SheetNames.forEach((sheetName) => {
        const type = detectSheetType(sheetName);
        if (!type) return;

        const sheet = wb.Sheets[sheetName];
        const rows = XLSX.utils.sheet_to_json(sheet, { defval: '', raw: true });
        if (!rows.length) return;

        let count = 0;
        rows.forEach((r) => {
          const item = mapRowToItem(r, type);
          if (item) {
            mapped.push(item);
            count += 1;
          }
        });
        if (count) usedSheets.push(`${sheetName} (${count}건)`);
      });

      if (!mapped.length) {
        alert(
          '인식된 항목이 없습니다.\n' +
          '비용예산 / 자본예산 / 수익예산 시트에서\n' +
          '세부활동, 26년 실행예산(또는 2026 편성액), 27년 예산요구안 컬럼을 확인하세요.'
        );
        return;
      }

      items = mapped;
      currentWorkId = null;
      currentWorkTitle = '';
      const prevEl = document.getElementById('prevYear');
      const currEl = document.getElementById('currYear');
      if (prevEl && !prevEl.dataset.userEdited) prevEl.value = '2026';
      if (currEl && !currEl.dataset.userEdited) currEl.value = '2027';
      render();
      saveState();
      console.info('불러온 시트:', usedSheets.join(', '), '/ 총', mapped.length, '건');
    } catch (err) {
      console.error(err);
      alert('파일을 읽는 중 오류가 발생했습니다.');
    }
  };
  reader.readAsArrayBuffer(file);
}

/** 비용 또는 자본 시트를 각각 생성 (사업명·비고 분리) */
function buildTypedRows(type) {
  const rows = items.filter((i) => i.type === type);
  const data = rows.map((row) => {
    const prev = getPrev(row);
    const diff = calcDiff(prev, row.curr);
    const rate = calcRate(prev, row.curr);
    const base = {
      항목명: row.name,
      전년: prev,
      금년: row.curr,
      증감액: diff,
      증감률: rate === null ? '' : Number(rate.toFixed(1)),
      사업명: row.bizName || '',
      비고: row.note || '',
    };
    if (type === '비용') {
      return {
        ...base,
        '2026 편성액': row.prevPlan ?? 0,
        '2026 실행예산': row.prevExec ?? 0,
        '비교 기준': costBaselineLabel(),
      };
    }
    return base;
  });

  const prev = sumPrev(rows);
  const curr = sumBy(rows, 'curr');
  const rate = calcRate(prev, curr);
  const total = {
    항목명: `합계 (${type})`,
    전년: prev,
    금년: curr,
    증감액: curr - prev,
    증감률: rate === null ? '' : Number(rate.toFixed(1)),
    사업명: '',
    비고: '',
  };
  if (type === '비용') {
    total['2026 편성액'] = rows.reduce((a, r) => a + (r.prevPlan ?? 0), 0);
    total['2026 실행예산'] = rows.reduce((a, r) => a + (r.prevExec ?? 0), 0);
    total['비교 기준'] = costBaselineLabel();
  }
  data.push(total);
  return data;
}

function buildRevenueRows() {
  const rows = items.filter((i) => i.type === '수익');
  const data = rows.map((row) => {
    const prev = getPrev(row);
    const diff = calcDiff(prev, row.curr);
    const rate = calcRate(prev, row.curr);
    return {
      항목명: row.name,
      전년: prev,
      금년: row.curr,
      증감액: diff,
      증감률: rate === null ? '' : Number(rate.toFixed(1)),
      사업명: row.bizName || '',
      비고: row.note || '',
    };
  });
  const prev = sumPrev(rows);
  const curr = sumBy(rows, 'curr');
  const rate = calcRate(prev, curr);
  data.push({
    항목명: '합계',
    전년: prev,
    금년: curr,
    증감액: curr - prev,
    증감률: rate === null ? '' : Number(rate.toFixed(1)),
    사업명: '',
    비고: '',
  });
  return data;
}

function buildSummaryRows() {
  const cost = items.filter((i) => i.type === '비용');
  const capital = items.filter((i) => i.type === '자본');
  const revenue = items.filter((i) => i.type === '수익');
  const costPrev = sumPrev(cost);
  const costCurr = sumBy(cost, 'curr');
  const capPrev = sumPrev(capital);
  const capCurr = sumBy(capital, 'curr');
  const revPrev = sumPrev(revenue);
  const revCurr = sumBy(revenue, 'curr');
  const prevYear = document.getElementById('prevYear').value;
  const currYear = document.getElementById('currYear').value;

  const rateOf = (p, c) => {
    const r = calcRate(p, c);
    return r === null ? '' : Number(r.toFixed(1));
  };

  return [
    { 구분: '기준연도', 전년: prevYear, 금년: currYear, 증감액: '', 증감률: '' },
    { 구분: '비용 비교 기준', 전년: costBaselineLabel(), 금년: '', 증감액: '', 증감률: '' },
    { 구분: '비용', 전년: costPrev, 금년: costCurr, 증감액: costCurr - costPrev, 증감률: rateOf(costPrev, costCurr) },
    { 구분: '자본', 전년: capPrev, 금년: capCurr, 증감액: capCurr - capPrev, 증감률: rateOf(capPrev, capCurr) },
    {
      구분: '비용+자본',
      전년: costPrev + capPrev,
      금년: costCurr + capCurr,
      증감액: costCurr + capCurr - (costPrev + capPrev),
      증감률: rateOf(costPrev + capPrev, costCurr + capCurr),
    },
    { 구분: '수익', 전년: revPrev, 금년: revCurr, 증감액: revCurr - revPrev, 증감률: rateOf(revPrev, revCurr) },
  ];
}

function buildBizOutlayExportRows() {
  const rows = aggregateByBiz().filter((r) => r.costPrev || r.costCurr || r.capPrev || r.capCurr);
  const data = rows.map((r) => {
    const totalPrev = r.costPrev + r.capPrev;
    const totalCurr = r.costCurr + r.capCurr;
    const rate = calcRate(totalPrev, totalCurr);
    return {
      사업명: r.name,
      '비용 전년': r.costPrev,
      '비용 금년': r.costCurr,
      '자본 전년': r.capPrev,
      '자본 금년': r.capCurr,
      '합계 전년': totalPrev,
      '합계 금년': totalCurr,
      증감액: totalCurr - totalPrev,
      증감률: rate === null ? '' : Number(rate.toFixed(1)),
    };
  });
  const sumCostPrev = rows.reduce((a, r) => a + r.costPrev, 0);
  const sumCostCurr = rows.reduce((a, r) => a + r.costCurr, 0);
  const sumCapPrev = rows.reduce((a, r) => a + r.capPrev, 0);
  const sumCapCurr = rows.reduce((a, r) => a + r.capCurr, 0);
  const totalPrev = sumCostPrev + sumCapPrev;
  const totalCurr = sumCostCurr + sumCapCurr;
  const rate = calcRate(totalPrev, totalCurr);
  data.push({
    사업명: '합계',
    '비용 전년': sumCostPrev,
    '비용 금년': sumCostCurr,
    '자본 전년': sumCapPrev,
    '자본 금년': sumCapCurr,
    '합계 전년': totalPrev,
    '합계 금년': totalCurr,
    증감액: totalCurr - totalPrev,
    증감률: rate === null ? '' : Number(rate.toFixed(1)),
  });
  return data;
}

function buildBizRevenueExportRows() {
  const rows = aggregateByBiz().filter((r) => r.revPrev || r.revCurr);
  const data = rows.map((r) => {
    const rate = calcRate(r.revPrev, r.revCurr);
    return {
      사업명: r.name,
      전년: r.revPrev,
      금년: r.revCurr,
      증감액: r.revCurr - r.revPrev,
      증감률: rate === null ? '' : Number(rate.toFixed(1)),
    };
  });
  const prev = rows.reduce((a, r) => a + r.revPrev, 0);
  const curr = rows.reduce((a, r) => a + r.revCurr, 0);
  const rate = calcRate(prev, curr);
  data.push({
    사업명: '합계',
    전년: prev,
    금년: curr,
    증감액: curr - prev,
    증감률: rate === null ? '' : Number(rate.toFixed(1)),
  });
  return data;
}

/* ——— 보고서 (A4 세로 1장) ——— */

/** 보고서 Ⅱ에 개별 행으로 싣는 사업 수. 나머지는 '기타 N개 사업'으로 묶는다. */
const REPORT_MAX_GROUPS = 8;

/** A4 세로 한 장에 들어가는 Ⅱ 표의 최대 줄 수 (합계 행 제외). */
const REPORT_ROW_BUDGET = 22;

/** 천원 단위 표시. 보고서는 자릿수를 줄여야 한 장에 들어간다. */
function formatCheon(n) {
  return Math.round(n / 1000).toLocaleString('ko-KR');
}

function formatCheonDiff(n) {
  const sign = n > 0 ? '+' : '';
  return `${sign}${formatCheon(n)}`;
}

/** 사업별로 묶고 그 안의 항목을 금년 규모순으로 정렬한다. (지출: 비용+자본) */
function reportBizGroups() {
  /** @type {Map<string, { name: string, prev: number, curr: number, items: { name: string, prev: number, curr: number }[] }>} */
  const map = new Map();

  items
    .filter((i) => i.type !== '수익')
    .forEach((i) => {
      const key = bizKey(i.bizName);
      if (!map.has(key)) map.set(key, { name: key, prev: 0, curr: 0, items: [] });
      const g = map.get(key);
      const prev = getPrev(i);
      g.prev += prev;
      g.curr += i.curr;
      if (prev || i.curr) g.items.push({ name: i.name, prev, curr: i.curr });
    });

  const groups = Array.from(map.values()).filter((g) => g.prev || g.curr);
  groups.forEach((g) => g.items.sort((a, b) => b.curr - a.curr));
  groups.sort((a, b) => b.curr - a.curr);
  return groups;
}

/**
 * 한 장에 맞도록 사업별 항목 수를 배분한다.
 * 금액이 큰 항목부터 한 줄씩 나눠 주므로, 주요 항목이 사업에 관계없이 우선 실린다.
 */
function planReportBizRows(groups) {
  const shown = groups.slice(0, REPORT_MAX_GROUPS);
  const restGroups = groups.slice(REPORT_MAX_GROUPS);
  const plan = shown.map((g) => ({ group: g, take: 0 }));

  const rowsUsed = () =>
    plan.length +
    plan.reduce((a, p) => a + p.take + (p.take < p.group.items.length ? 1 : 0), 0) +
    (restGroups.length ? 1 : 0);

  let guard = 500;
  while (guard-- > 0) {
    const next = plan
      .filter((p) => p.take < p.group.items.length)
      .sort((a, b) => b.group.items[b.take].curr - a.group.items[a.take].curr)[0];
    if (!next) break;
    next.take += 1;
    if (rowsUsed() > REPORT_ROW_BUDGET) {
      next.take -= 1;
      break;
    }
  }

  // 항목을 하나도 못 실은 사업은 '기타 n개 항목'만 남으므로 그 줄을 없앤다.
  plan.forEach((p) => { if (p.take === 0) p.hideRest = true; });

  return { plan, restGroups };
}

function renderReportSummary() {
  const cost = items.filter((i) => i.type === '비용');
  const capital = items.filter((i) => i.type === '자본');
  const revenue = items.filter((i) => i.type === '수익');
  const lines = [
    { label: '비용', prev: sumPrev(cost), curr: sumBy(cost, 'curr') },
    { label: '자본', prev: sumPrev(capital), curr: sumBy(capital, 'curr') },
  ];
  lines.push({
    label: '소계 (비용+자본)',
    prev: lines[0].prev + lines[1].prev,
    curr: lines[0].curr + lines[1].curr,
    strong: true,
  });
  lines.push({ label: '수익', prev: sumPrev(revenue), curr: sumBy(revenue, 'curr'), gap: true });

  document.getElementById('reportSummaryBody').innerHTML = lines
    .map((l) => {
      const diff = l.curr - l.prev;
      const cls = [l.strong ? 'is-strong' : '', l.gap ? 'is-gap' : ''].filter(Boolean).join(' ');
      return `
        <tr class="${cls}">
          <td>${escapeAttr(l.label)}</td>
          <td class="col-num">${formatCheon(l.prev)}</td>
          <td class="col-num">${formatCheon(l.curr)}</td>
          <td class="col-num ${deltaClass(diff)}">${formatCheonDiff(diff)}</td>
          <td class="col-num ${deltaClass(diff)}">${formatRate(calcRate(l.prev, l.curr))}</td>
        </tr>`;
    })
    .join('');
}

function reportRow(label, prev, curr, cls = '') {
  const diff = curr - prev;
  return `
    <tr class="${cls}">
      <td>${escapeAttr(label)}</td>
      <td class="col-num">${formatCheon(prev)}</td>
      <td class="col-num">${formatCheon(curr)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatCheonDiff(diff)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatRate(calcRate(prev, curr))}</td>
    </tr>`;
}

function renderReportBiz() {
  const groups = reportBizGroups();
  const { plan, restGroups } = planReportBizRows(groups);
  const body = [];

  plan.forEach(({ group, take, hideRest }) => {
    body.push(reportRow(group.name, group.prev, group.curr, 'is-group'));

    group.items.slice(0, take).forEach((it) => {
      body.push(reportRow(it.name, it.prev, it.curr, 'is-item'));
    });

    const leftover = group.items.slice(take);
    if (leftover.length && !hideRest) {
      body.push(reportRow(
        `기타 ${leftover.length}개 항목`,
        leftover.reduce((a, i) => a + i.prev, 0),
        leftover.reduce((a, i) => a + i.curr, 0),
        'is-item is-rest'
      ));
    }
  });

  if (restGroups.length) {
    body.push(reportRow(
      `기타 ${restGroups.length}개 사업`,
      restGroups.reduce((a, g) => a + g.prev, 0),
      restGroups.reduce((a, g) => a + g.curr, 0),
      'is-group is-rest'
    ));
  }
  document.getElementById('reportBizBody').innerHTML = body.join('');

  const prev = groups.reduce((a, g) => a + g.prev, 0);
  const curr = groups.reduce((a, g) => a + g.curr, 0);
  const diff = curr - prev;
  document.getElementById('reportBizFoot').innerHTML = `
    <tr>
      <td>합계</td>
      <td class="col-num">${formatCheon(prev)}</td>
      <td class="col-num">${formatCheon(curr)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatCheonDiff(diff)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatRate(calcRate(prev, curr))}</td>
    </tr>`;
}

function renderReport() {
  const prevYear = document.getElementById('prevYear').value;
  const currYear = document.getElementById('currYear').value;
  document.getElementById('reportTitle').textContent = `${currYear}년도 예산(안) 전년 대비 비교`;
  document.getElementById('reportPrevHead').textContent = `${prevYear} 전년`;
  document.getElementById('reportCurrHead').textContent = `${currYear} 금년`;
  document.getElementById('reportMeta').textContent =
    `비교 기준: ${prevYear} ${costBaselineLabel()}  |  단위: 천원  |  작성일: ${new Date().toLocaleDateString('ko-KR')}`;

  renderReportSummary();
  renderReportBiz();
}

function setPortraitPage(on) {
  document.getElementById('pageSetup').textContent = on
    ? '@media print { @page { size: A4 portrait; margin: 15mm; } }'
    : '';
}

function openReport() {
  renderReport();
  document.getElementById('printArea').hidden = true;
  document.getElementById('increaseSheet').hidden = true;
  document.getElementById('reportSheet').hidden = false;
  setPortraitPage(true);
  window.scrollTo(0, 0);
}

function closeReport() {
  document.getElementById('reportSheet').hidden = true;
  document.getElementById('printArea').hidden = false;
  setPortraitPage(false);
}

/** 항목 하나의 전년 대비 증가분을 계산해, 증가한 것만 diff 큰 순으로 정렬한다. */
function getIncreasedRows(type) {
  return items
    .filter((i) => i.type === type)
    .map((i) => ({ item: i, prev: getPrev(i), curr: i.curr }))
    .filter((r) => r.curr > r.prev)
    .sort((a, b) => (b.curr - b.prev) - (a.curr - a.prev));
}

/** 증가 항목 표의 한 행. 사업명은 항목명 아래 작은 참고용 텍스트로만 표시한다. */
function increaseRow(item, prev, curr) {
  const diff = curr - prev;
  const rate = calcRate(prev, curr);
  const bizLine = item.bizName
    ? `<div style="font-size:12px;color:#888;margin-top:2px;">${escapeAttr(item.bizName)}</div>`
    : '';
  return `
    <tr>
      <td class="col-label">${escapeAttr(item.name)}${bizLine}</td>
      <td class="col-num">${formatWon(prev)}</td>
      <td class="col-num">${formatWon(curr)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatDiff(diff)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatRate(rate)}</td>
    </tr>`;
}

function increaseFoot(rows) {
  const prev = rows.reduce((a, r) => a + r.prev, 0);
  const curr = rows.reduce((a, r) => a + r.curr, 0);
  const diff = curr - prev;
  return `
    <tr>
      <td>소계</td>
      <td class="col-num">${formatWon(prev)}</td>
      <td class="col-num">${formatWon(curr)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatDiff(diff)}</td>
      <td class="col-num ${deltaClass(diff)}">${formatRate(calcRate(prev, curr))}</td>
    </tr>`;
}

/** 증가 항목이 하나도 없으면 표 대신 안내 문구를 보여준다. */
function renderIncreaseGroup(type, bodyId, footId, emptyId) {
  const rows = getIncreasedRows(type);
  const body = document.getElementById(bodyId);
  const foot = document.getElementById(footId);
  const empty = document.getElementById(emptyId);
  const table = body.closest('table');

  if (!rows.length) {
    body.innerHTML = '';
    foot.innerHTML = '';
    if (table) table.hidden = true;
    if (empty) empty.hidden = false;
    return;
  }

  if (table) table.hidden = false;
  if (empty) empty.hidden = true;
  body.innerHTML = rows.map((r) => increaseRow(r.item, r.prev, r.curr)).join('');
  foot.innerHTML = increaseFoot(rows);
}

function renderIncreaseSheet() {
  const prevYear = document.getElementById('prevYear').value;
  const currYear = document.getElementById('currYear').value;
  document.getElementById('increaseMeta').textContent =
    `${prevYear} → ${currYear}  |  비용 비교 기준: ${prevYear} ${costBaselineLabel()}  |  증가액 큰 순`;

  renderIncreaseGroup('비용', 'increaseCostBody', 'increaseCostFoot', 'increaseCostEmpty');
  renderIncreaseGroup('자본', 'increaseCapBody', 'increaseCapFoot', 'increaseCapEmpty');
}

function openIncreaseSheet() {
  renderIncreaseSheet();
  document.getElementById('printArea').hidden = true;
  document.getElementById('reportSheet').hidden = true;
  document.getElementById('increaseSheet').hidden = false;
  setPortraitPage(true);
  window.scrollTo(0, 0);
}

function closeIncreaseSheet() {
  document.getElementById('increaseSheet').hidden = true;
  document.getElementById('printArea').hidden = false;
  setPortraitPage(false);
}

function exportExcel() {
  if (typeof XLSX === 'undefined') {
    alert('엑셀 라이브러리를 불러오지 못했습니다. 네트워크 연결을 확인하세요.');
    return;
  }

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(buildSummaryRows()), '요약');
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(buildBizOutlayExportRows()), '사업명별_비용자본');
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(buildBizRevenueExportRows()), '사업명별_수익');
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(buildTypedRows('비용')), '비용');
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(buildTypedRows('자본')), '자본');
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(buildRevenueRows()), '수익');

  const prevYear = document.getElementById('prevYear').value;
  const currYear = document.getElementById('currYear').value;
  const filename = `예산비교_${prevYear}-${currYear}.xlsx`;
  XLSX.writeFile(wb, filename);
}

function init() {
  bindTables();
  bindConfirmTable();
  document.getElementById('exportExcelBtn').addEventListener('click', exportExcel);
  document.getElementById('printBtn').addEventListener('click', printPage);
  document.getElementById('addItemBtn').addEventListener('click', openAddDialog);
  document.getElementById('cancelAdd').addEventListener('click', closeAddDialog);
  document.getElementById('addForm').addEventListener('submit', onAddSubmit);
  document.getElementById('reportBtn').addEventListener('click', openReport);
  document.getElementById('reportCloseBtn').addEventListener('click', closeReport);
  document.getElementById('increaseBtn').addEventListener('click', openIncreaseSheet);
  document.getElementById('increaseCloseBtn').addEventListener('click', closeIncreaseSheet);
  document.getElementById('increasePrintBtn').addEventListener('click', () => window.print());
  document.getElementById('reportPrintBtn').addEventListener('click', () => window.print());
  document.getElementById('saveFileBtn').addEventListener('click', () => saveToFile(true));
  document.getElementById('saveFileAsBtn').addEventListener('click', () => saveToFile(false));
  document.getElementById('saveServerBtn')?.addEventListener('click', () => saveToServer(false));
  document.getElementById('saveServerAsBtn')?.addEventListener('click', () => saveToServer(true));
  document.getElementById('loadServerBtn')?.addEventListener('click', openServerWorks);
  document.getElementById('jsonInput').addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (file) loadFromFile(file);
    e.target.value = '';
  });
  document.getElementById('clearSaveBtn').addEventListener('click', clearSavedState);
  document.getElementById('excelInput').addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (file) importSheet(file);
    e.target.value = '';
  });
  document.querySelectorAll('input[name="costBaseline"]').forEach((el) => {
    el.addEventListener('change', (e) => {
      const target = /** @type {HTMLInputElement} */ (e.target);
      if (!target.checked) return;
      costBaseline = target.value === 'plan' ? 'plan' : 'exec';
      render();
      scheduleSave();
    });
  });
  ['prevYear', 'currYear'].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('change', () => {
      el.dataset.userEdited = '1';
      scheduleSave();
    });
  });

  window.addEventListener('beforeunload', () => {
    if (isDirty) saveState();
  });

  if (!canUseStorage()) {
    updateSaveStatus(null, true, '임시 보관 불가 — [작업 저장]으로 보관해 주세요');
  }

  const restored = loadState();
  render();
  if (!restored && canUseStorage()) {
    updateSaveStatus(null);
  }
}

init();
