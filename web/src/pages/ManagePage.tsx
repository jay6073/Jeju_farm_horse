import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  insertHorse,
  insertHorses,
  listHorses,
  updateHorseSpecies,
  updateHorseStatus,
} from "../lib/api";
import {
  MANAGEABLE_SPECIES,
  MANAGEABLE_STATUSES,
  STATUS_CUSTOM_OPTION,
  STATUS_MAX_LENGTH,
  STATUS_NORMAL,
  STATUS_RESERVED,
  TRANSFERABLE_SPECIES,
} from "../lib/constants";
import { parseWorkbook } from "../lib/excel";
import { todayIso } from "../lib/format";
import { normalizeHorseNumber } from "../lib/horseNumber";
import type { HorseRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { useNotify } from "../components/Toast";

const TABS = ["개별 추가", "보유상태 변경", "용도변경", "엑셀 일괄 등록"] as const;

export function ManagePage() {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState<(typeof TABS)[number]>("개별 추가");

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-medium">보유마 관리</h1>
      <div className="flex border-b border-gray-200">
        {TABS.map((item) => (
          <button
            key={item}
            type="button"
            className={`flex-1 px-1 py-2 text-sm ${tab === item ? "border-b-2 border-primary text-primary" : "text-gray-500"}`}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </div>
      {!isAdmin ? (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          조회만 가능합니다. 등록·변경은 관리자 로그인 후 사용할 수 있습니다.
        </p>
      ) : null}
      {tab === "개별 추가" ? <AddSection disabled={!isAdmin} /> : null}
      {tab === "보유상태 변경" ? <StatusSection disabled={!isAdmin} /> : null}
      {tab === "용도변경" ? <SpeciesSection disabled={!isAdmin} /> : null}
      {tab === "엑셀 일괄 등록" ? <ImportSection disabled={!isAdmin} /> : null}
    </div>
  );
}

function AddSection({ disabled }: { disabled: boolean }) {
  const notify = useNotify();
  const [name, setName] = useState("");
  const [species, setSpecies] = useState("");
  const [number, setNumber] = useState("");
  const [breed, setBreed] = useState("");

  async function onSave() {
    if (!name || !species) {
      notify("마명과 마종은 필수입니다.", "warn");
      return;
    }
    try {
      const 마번 = normalizeHorseNumber(number);
      const horses = await listHorses();
      const 마명 = name.trim();
      if (horses.some((h) => h.마명 === 마명 || (마번 && h.마번 === 마번))) {
        notify("이미 같은 마명 또는 마번이 등록되어 있습니다.", "err");
        return;
      }
      await insertHorse({
        마명,
        마종: species,
        마번,
        품종코드: breed.trim() || null,
      });
      notify(`'${name.trim()}' 등록 완료`);
      setName("");
      setSpecies("");
      setNumber("");
      setBreed("");
    } catch (err) {
      notify(err instanceof Error ? err.message : "등록 실패", "err");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="마명" value={name} onChange={(e) => setName(e.target.value)} />
      <select className="rounded-md border border-gray-200 px-3 py-2" value={species} onChange={(e) => setSpecies(e.target.value)}>
        <option value="">마종</option>
        {MANAGEABLE_SPECIES.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="마번 (선택)" value={number} onChange={(e) => setNumber(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="품종코드 (선택)" value={breed} onChange={(e) => setBreed(e.target.value)} />
      <p className="text-xs text-gray-400">위수탁마는 여기서 등록할 수 없습니다. 위탁 계약 등록 화면을 이용하세요.</p>
      <button type="button" disabled={disabled} className="w-fit rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" onClick={onSave}>
        + 추가
      </button>
    </div>
  );
}

function StatusSection({ disabled }: { disabled: boolean }) {
  const notify = useNotify();
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [species, setSpecies] = useState("");
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [status, setStatus] = useState("");
  const [date, setDate] = useState(todayIso());
  const [reason, setReason] = useState("");

  useEffect(() => {
    listHorses().then(setHorses).catch((err: unknown) => notify(err instanceof Error ? err.message : "실패", "err"));
  }, [notify]);

  const rows = horses.filter((h) => h.마종 === species);

  async function onChange() {
    const ids = [...checked];
    if (!ids.length) return notify("변경할 말을 선택하세요.", "warn");
    if (!status) return notify("변경할 상태를 선택하세요.", "warn");
    const isNormal = status === STATUS_NORMAL;
    const isCustom = status === STATUS_CUSTOM_OPTION;
    if (!isNormal && !date) return notify("발생일자를 입력하세요.", "warn");
    let next = status;
    if (isCustom) {
      next = reason.trim();
      if (!next) return notify("사유를 입력하세요.", "warn");
      if (STATUS_RESERVED.has(next)) return notify(`'${next}'는 직접 입력 사유로 쓸 수 없습니다.`, "warn");
      if (next.length > STATUS_MAX_LENGTH) return notify("상태는 30자 이하여야 합니다.", "warn");
    }
    if (!window.confirm(`${ids.length}마리를 [${next}]로 변경할까요?`)) return;
    try {
      await updateHorseStatus(ids, next, isNormal ? null : date);
      notify(`${ids.length}마리 상태 변경 완료`);
      const fresh = await listHorses();
      setHorses(fresh);
      setChecked(new Set());
    } catch (err) {
      notify(err instanceof Error ? err.message : "변경 실패", "err");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <select className="rounded-md border border-gray-200 px-3 py-2" value={species} onChange={(e) => { setSpecies(e.target.value); setChecked(new Set()); }}>
        <option value="">마종</option>
        {MANAGEABLE_SPECIES.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
      {!species ? null : rows.length === 0 ? (
        <EmptyState message={`${species}에 해당하는 보유마가 없습니다`} />
      ) : (
        <Card>
          {rows.map((h) => (
            <label key={h.id} className="flex items-center gap-3 py-1 text-sm">
              <input
                type="checkbox"
                checked={checked.has(h.id)}
                onChange={(e) => {
                  const next = new Set(checked);
                  if (e.target.checked) next.add(h.id);
                  else next.delete(h.id);
                  setChecked(next);
                }}
              />
              <span className="flex-1">{h.마명}</span>
              <StatusBadge status={h.상태} />
            </label>
          ))}
        </Card>
      )}
      <Card>
        <div className="mb-2 text-sm text-gray-500">선택한 말들의 보유상태 변경</div>
        <div className="flex gap-3">
          <select className="flex-1 rounded-md border border-gray-200 px-3 py-2" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">상태</option>
            {MANAGEABLE_STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          {status && status !== STATUS_NORMAL ? (
            <input className="flex-1 rounded-md border border-gray-200 px-3 py-2" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          ) : null}
        </div>
        {status === STATUS_CUSTOM_OPTION ? (
          <input className="mt-2 w-full rounded-md border border-gray-200 px-3 py-2" placeholder="사유" maxLength={STATUS_MAX_LENGTH} value={reason} onChange={(e) => setReason(e.target.value)} />
        ) : null}
        <button type="button" disabled={disabled} className="mt-3 rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" onClick={onChange}>
          상태 변경
        </button>
      </Card>
    </div>
  );
}

function SpeciesSection({ disabled }: { disabled: boolean }) {
  const notify = useNotify();
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [species, setSpecies] = useState("");
  const [target, setTarget] = useState("");
  const [checked, setChecked] = useState<Set<number>>(new Set());

  useEffect(() => {
    listHorses().then(setHorses).catch((err: unknown) => notify(err instanceof Error ? err.message : "실패", "err"));
  }, [notify]);

  const rows = horses.filter((h) => h.마종 === species);
  const targets = TRANSFERABLE_SPECIES.filter((s) => s !== species);

  async function onChange() {
    const ids = [...checked];
    if (!ids.length) return notify("변경할 말을 선택하세요.", "warn");
    if (!target) return notify("변경할 마종을 선택하세요.", "warn");
    if (!window.confirm(`${ids.length}마리를 [${species}]에서 [${target}](으)로 변경할까요?`)) return;
    try {
      await updateHorseSpecies(ids, target);
      notify(`${ids.length}마리 용도변경 완료`);
      setHorses(await listHorses());
      setChecked(new Set());
    } catch (err) {
      notify(err instanceof Error ? err.message : "변경 실패", "err");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <p className="text-xs text-gray-400">위수탁마는 이 화면에서 변경할 수 없습니다.</p>
      <select className="rounded-md border border-gray-200 px-3 py-2" value={species} onChange={(e) => { setSpecies(e.target.value); setTarget(""); setChecked(new Set()); }}>
        <option value="">현재 마종</option>
        {TRANSFERABLE_SPECIES.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
      {rows.length ? (
        <Card>
          {rows.map((h) => (
            <label key={h.id} className="flex items-center gap-3 py-1 text-sm">
              <input
                type="checkbox"
                checked={checked.has(h.id)}
                onChange={(e) => {
                  const next = new Set(checked);
                  if (e.target.checked) next.add(h.id);
                  else next.delete(h.id);
                  setChecked(next);
                }}
              />
              <span className="flex-1">{h.마명}</span>
              <StatusBadge status={h.상태} />
            </label>
          ))}
        </Card>
      ) : species ? (
        <EmptyState message={`${species}에 해당하는 보유마가 없습니다`} />
      ) : null}
      {targets.length ? (
        <Card>
          <select className="w-full rounded-md border border-gray-200 px-3 py-2" value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">변경할 마종</option>
            {targets.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <button type="button" disabled={disabled} className="mt-3 rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" onClick={onChange}>
            용도 변경
          </button>
        </Card>
      ) : null}
    </div>
  );
}

function ImportSection({ disabled }: { disabled: boolean }) {
  const notify = useNotify();
  const [preview, setPreview] = useState<
    { row_no: number; 마명: string; 마종: string; 마번: string | null; 품종코드: string | null; error?: string; dup?: boolean }[]
  >([]);

  const validCount = useMemo(() => preview.filter((r) => !r.error && !r.dup).length, [preview]);

  async function onFile(file: File) {
    try {
      const buf = await file.arrayBuffer();
      const records = parseWorkbook(buf);
      const horses = await listHorses();
      const names = new Set(horses.map((h) => h.마명));
      const numbers = new Set(horses.map((h) => h.마번).filter(Boolean));
      if (!records.length) throw new Error("엑셀에 데이터가 없습니다.");
      const cols = Object.keys(records[0]);
      for (const required of ["마명", "마종", "등록번호"]) {
        if (!cols.includes(required)) throw new Error(`필수 컬럼이 없습니다: ${required}`);
      }
      setPreview(
        records.map((record, i) => {
          const 마명 = String(record["마명"] ?? "").trim();
          const 마종 = String(record["마종"] ?? "").trim();
          const 마번 = normalizeHorseNumber(String(record["등록번호"] ?? ""));
          const 품종코드 = String(record["품종코드"] ?? "").trim() || null;
          let error: string | undefined;
          if (!마명) error = "마명이 비어 있습니다.";
          else if (!MANAGEABLE_SPECIES.includes(마종 as (typeof MANAGEABLE_SPECIES)[number]) && 마종 !== "위수탁마")
            error = `유효하지 않은 마종입니다: ${마종}`;
          else if (마종 === "위수탁마") error = "위수탁마는 엑셀 일괄 등록으로 추가할 수 없습니다.";
          const dup = !error && (names.has(마명) || (!!마번 && numbers.has(마번)));
          return { row_no: i + 2, 마명, 마종, 마번, 품종코드, error, dup };
        }),
      );
    } catch (err) {
      notify(err instanceof Error ? err.message : "엑셀 읽기 실패", "err");
    }
  }

  async function onCommit() {
    const rows = preview.filter((r) => !r.error && !r.dup);
    try {
      await insertHorses(rows.map((r) => ({ 마명: r.마명, 마종: r.마종, 마번: r.마번, 품종코드: r.품종코드 })));
      notify(`${rows.length}마리 일괄 등록 완료`);
      setPreview([]);
    } catch (err) {
      notify(err instanceof Error ? err.message : "등록 실패", "err");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <p className="text-xs text-gray-400">필수 컬럼: 마명, 마종, 등록번호</p>
      <input type="file" accept=".xlsx,.xls,.xlsm" disabled={disabled} onChange={(e) => { const f = e.target.files?.[0]; if (f) void onFile(f); }} />
      {preview.length ? (
        <Card>
          {preview.map((r) => (
            <div key={r.row_no} className="flex gap-3 border-b border-gray-100 py-1 text-sm">
              <span className="w-12 text-gray-400">{r.row_no}행</span>
              <span className="flex-1">{r.마명 || "-"}</span>
              <span className="flex-1">{r.마종 || "-"}</span>
              <span className={r.error ? "text-red-600" : r.dup ? "text-orange-500" : "text-green-600"}>
                {r.error ?? (r.dup ? "중복 (건너뜀)" : "등록 예정")}
              </span>
            </div>
          ))}
        </Card>
      ) : null}
      <button type="button" disabled={disabled || validCount === 0} className="rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" onClick={onCommit}>
        일괄 등록 ({validCount}건)
      </button>
    </div>
  );
}
