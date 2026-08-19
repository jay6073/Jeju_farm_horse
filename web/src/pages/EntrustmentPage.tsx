import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  deleteAuction,
  deleteCareer,
  deleteEntrustment,
  deleteHorseByNumber,
  deleteRacesForHorse,
  insertAuction,
  insertEntrustment,
  insertHorse,
  listAuctionsForHorse,
  listEntrustment,
  listHorses,
  updateEntrustment,
  updateHorseStatus,
} from "../lib/api";
import { HORSE_STATUS_OPTIONS, STATUS_ENDED, STATUS_ENTRUSTED } from "../lib/constants";
import { downloadWorkbook } from "../lib/excel";
import { classifyAuction, fmtDate, fmtFee, fmtText, hammerPriceFromResult } from "../lib/format";
import { normalizeApplicantName, normalizeHorseNumber } from "../lib/horseNumber";
import type { EntrustmentRow, HorseRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useNotify } from "../components/Toast";

const TABS = ["위탁 계약 등록", "위탁 계약 목록", "명단 조회", "연간 통계"] as const;

export function EntrustmentPage() {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState<(typeof TABS)[number]>("위탁 계약 등록");
  return (
    <div className="flex flex-col gap-4">
      <h1 className="no-print text-xl font-medium">위탁관리</h1>
      <div className="no-print flex border-b border-gray-200">
        {TABS.map((item) => (
          <button key={item} type="button" className={`flex-1 py-2 text-xs sm:text-sm ${tab === item ? "border-b-2 border-primary text-primary" : "text-gray-500"}`} onClick={() => setTab(item)}>
            {item}
          </button>
        ))}
      </div>
      {tab === "위탁 계약 등록" ? <RegisterSection disabled={!isAdmin} /> : null}
      {tab === "위탁 계약 목록" ? <ListSection disabled={!isAdmin} /> : null}
      {tab === "명단 조회" ? <SearchSection /> : null}
      {tab === "연간 통계" ? <ReportSection /> : null}
    </div>
  );
}

function RegisterSection({ disabled }: { disabled: boolean }) {
  const notify = useNotify();
  const [horseId, setHorseId] = useState("");
  const [name, setName] = useState("");
  const [applicant, setApplicant] = useState("");
  const [farm, setFarm] = useState("");
  const [inDate, setInDate] = useState("");
  const [outDate, setOutDate] = useState("");
  const [fee, setFee] = useState("");
  const [year, setYear] = useState("");

  async function onSave() {
    const id = normalizeHorseNumber(horseId);
    if (!id) return notify("마번은 필수입니다.", "warn");
    if (!name.trim()) return notify("마명은 필수입니다.", "warn");
    const status = outDate ? STATUS_ENDED : STATUS_ENTRUSTED;
    let createdNewHorse = false;
    let createdEntrustment = false;
    let createdAuctionId: number | null = null;
    try {
      const horses = await listHorses();
      const existing = horses.find((h) => h.마번 === id);
      if (!existing) {
        await insertHorse({ 마명: name.trim(), 마종: "위수탁마", 마번: id });
        createdNewHorse = true;
      }
      const already = await listEntrustment();
      if (already.some((e) => e.horse_id === id)) {
        notify(`마번 ${id}는 이미 위탁 계약이 등록되어 있습니다.`, "err");
        return;
      }
      await insertEntrustment({
        horse_id: id,
        applicant_name: applicant || null,
        farm_name: farm || null,
        farm_in_date: inDate || null,
        farm_out_date: outDate || null,
        entrustment_fee: fee ? Number(fee) : null,
        application_year: year ? Number(year) : null,
        status,
      });
      createdEntrustment = true;
      const auctions = await listAuctionsForHorse(id);
      if (!auctions.length) {
        const created = await insertAuction({
          horse_id: id,
          auction_date: null,
          auction_name: "미상장",
          hammer_price: null,
          buyer_name: null,
          is_final: false,
        });
        createdAuctionId = created.id;
      }
      const latest = (await listHorses()).find((h) => h.마번 === id);
      if (latest?.마종 === "위수탁마") {
        await updateHorseStatus(
          [latest.id],
          status === STATUS_ENTRUSTED ? "정상" : "위수탁종료",
          status === STATUS_ENTRUSTED ? null : outDate || new Date().toISOString().slice(0, 10),
        );
      }
      notify(`마번 ${id} 위탁 계약 등록 완료`);
      setHorseId(""); setName(""); setApplicant(""); setFarm(""); setInDate(""); setOutDate(""); setFee(""); setYear("");
    } catch (err) {
      if (createdAuctionId != null) {
        try {
          await deleteAuction(createdAuctionId);
        } catch {
          /* 경매 롤백 실패는 원래 오류를 우선 */
        }
      }
      if (createdEntrustment) {
        try {
          await deleteEntrustment(id);
        } catch {
          /* 계약 롤백 실패는 원래 오류를 우선 */
        }
      }
      if (createdNewHorse) {
        try {
          await deleteHorseByNumber(id);
        } catch {
          /* 보유마 롤백 실패는 원래 오류를 우선 */
        }
      }
      notify(err instanceof Error ? err.message : "등록 실패", "err");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="마번 (7자리)" value={horseId} onChange={(e) => setHorseId(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="마명" value={name} onChange={(e) => setName(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="신청인" value={applicant} onChange={(e) => setApplicant(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="목장명" value={farm} onChange={(e) => setFarm(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" type="date" value={inDate} onChange={(e) => setInDate(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" type="date" value={outDate} onChange={(e) => setOutDate(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" type="number" placeholder="위탁비 (부가세포함)" value={fee} onChange={(e) => setFee(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" type="number" placeholder="사업연도" value={year} onChange={(e) => setYear(e.target.value)} />
      <button type="button" disabled={disabled} className="w-fit rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" onClick={onSave}>
        + 등록
      </button>
    </div>
  );
}

function ListSection({ disabled }: { disabled: boolean }) {
  const notify = useNotify();
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [rows, setRows] = useState<EntrustmentRow[]>([]);
  const [status, setStatus] = useState(STATUS_ENTRUSTED);
  const [editing, setEditing] = useState<EntrustmentRow | null>(null);

  async function reload() {
    const [h, e] = await Promise.all([listHorses(), listEntrustment()]);
    setHorses(h);
    setRows(e);
  }

  useEffect(() => {
    reload().catch((err: unknown) => notify(err instanceof Error ? err.message : "실패", "err"));
  }, [notify]);

  const nameById = Object.fromEntries(horses.map((h) => [h.마번, h.마명]));
  const filtered = rows.filter((r) => r.status === status).sort((a, b) => (nameById[a.horse_id] ?? "").localeCompare(nameById[b.horse_id] ?? "", "ko"));

  async function onDelete(row: EntrustmentRow) {
    if (!window.confirm(`마번 ${row.horse_id} 위탁 계약을 삭제할까요?`)) return;
    try {
      const auctions = await listAuctionsForHorse(row.horse_id);
      for (const a of auctions) await deleteAuction(a.id);
      await deleteRacesForHorse(row.horse_id);
      await deleteCareer(row.horse_id);
      await deleteEntrustment(row.horse_id);
      const horse = horses.find((h) => h.마번 === row.horse_id);
      if (horse?.마종 === "위수탁마") await deleteHorseByNumber(row.horse_id);
      notify("삭제 완료");
      await reload();
    } catch (err) {
      notify(err instanceof Error ? err.message : "삭제 실패", "err");
    }
  }

  async function onSaveEdit() {
    if (!editing) return;
    try {
      await updateEntrustment(editing.horse_id, {
        applicant_name: editing.applicant_name,
        farm_name: editing.farm_name,
        farm_out_date: editing.farm_out_date,
        entrustment_fee: editing.entrustment_fee,
        status: editing.status,
      });
      notify("수정 완료");
      setEditing(null);
      await reload();
    } catch (err) {
      notify(err instanceof Error ? err.message : "수정 실패", "err");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <select className="max-w-xs rounded-md border border-gray-200 px-3 py-2" value={status} onChange={(e) => setStatus(e.target.value)}>
        {HORSE_STATUS_OPTIONS.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
      {filtered.length === 0 ? (
        <EmptyState message="조건에 맞는 위탁 계약이 없습니다" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-400">
                <th className="px-2 py-1">마번</th>
                <th className="px-2 py-1">마명</th>
                <th className="px-2 py-1">신청인</th>
                <th className="px-2 py-1">상태</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.horse_id} className="border-b border-gray-100">
                  <td className="px-2 py-1.5 text-gray-500">{r.horse_id}</td>
                  <td className="px-2 py-1.5">{nameById[r.horse_id] ?? "-"}</td>
                  <td className="px-2 py-1.5">{r.applicant_name ?? "-"}</td>
                  <td className="px-2 py-1.5">{r.status}</td>
                  <td className="px-2 py-1.5">
                    {disabled ? null : (
                      <span className="flex gap-2">
                        <button type="button" className="text-primary" onClick={() => setEditing(r)}>수정</button>
                        <button type="button" className="text-red-600" onClick={() => onDelete(r)}>삭제</button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {editing ? (
        <Card>
          <div className="mb-2 text-sm font-medium">위탁 계약 수정 (마번 {editing.horse_id})</div>
          <div className="flex flex-col gap-2">
            <input className="rounded-md border border-gray-200 px-3 py-2" value={editing.applicant_name ?? ""} onChange={(e) => setEditing({ ...editing, applicant_name: e.target.value })} placeholder="신청인" />
            <input className="rounded-md border border-gray-200 px-3 py-2" value={editing.farm_name ?? ""} onChange={(e) => setEditing({ ...editing, farm_name: e.target.value })} placeholder="목장명" />
            <input className="rounded-md border border-gray-200 px-3 py-2" type="date" value={editing.farm_out_date ?? ""} onChange={(e) => setEditing({ ...editing, farm_out_date: e.target.value })} />
            <input className="rounded-md border border-gray-200 px-3 py-2" type="number" value={editing.entrustment_fee ?? ""} onChange={(e) => setEditing({ ...editing, entrustment_fee: e.target.value ? Number(e.target.value) : null })} />
            <select className="rounded-md border border-gray-200 px-3 py-2" value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value })}>
              {HORSE_STATUS_OPTIONS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setEditing(null)}>취소</button>
              <button type="button" className="rounded-md bg-primary px-3 py-1.5 text-white" onClick={onSaveEdit}>저장</button>
            </div>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function SearchSection() {
  const notify = useNotify();
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [rows, setRows] = useState<EntrustmentRow[]>([]);
  const [year, setYear] = useState("");
  const [status, setStatus] = useState("전체");
  const [applicant, setApplicant] = useState("");
  const [keyword, setKeyword] = useState("");
  const [result, setResult] = useState<EntrustmentRow[] | null>(null);

  useEffect(() => {
    Promise.all([listHorses(), listEntrustment()]).then(([h, e]) => {
      setHorses(h);
      setRows(e);
    });
  }, []);

  const nameById = Object.fromEntries(horses.map((h) => [h.마번, h]));

  function apply(): EntrustmentRow[] {
    let next = rows;
    if (year) next = next.filter((r) => r.application_year === Number(year));
    if (status !== "전체") next = next.filter((r) => r.status === status);
    if (applicant.trim()) {
      const target = normalizeApplicantName(applicant);
      next = next.filter((r) => r.applicant_name && normalizeApplicantName(r.applicant_name).includes(target.replace("(신청인 미상)", "")));
    }
    if (keyword.trim()) {
      const kw = keyword.trim().toLowerCase();
      next = next.filter((r) => r.horse_id.includes(kw) || (nameById[r.horse_id]?.마명 ?? "").toLowerCase().includes(kw));
    }
    return next.sort((a, b) => (nameById[a.horse_id]?.마명 ?? "").localeCompare(nameById[b.horse_id]?.마명 ?? "", "ko"));
  }

  function search() {
    if (!year && status === "전체" && !applicant.trim() && !keyword.trim()) {
      notify("필터를 하나 이상 입력하세요.", "warn");
      return;
    }
    setResult(apply());
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <input className="w-36 rounded-md border border-gray-200 px-3 py-2" type="number" placeholder="사업연도" value={year} onChange={(e) => setYear(e.target.value)} />
        <select className="w-36 rounded-md border border-gray-200 px-3 py-2" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option>전체</option>
          {HORSE_STATUS_OPTIONS.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <input className="w-44 rounded-md border border-gray-200 px-3 py-2" placeholder="신청인" value={applicant} onChange={(e) => setApplicant(e.target.value)} />
        <input className="w-44 rounded-md border border-gray-200 px-3 py-2" placeholder="마번/마명" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
        <button type="button" className="rounded-md bg-primary px-3 py-2 text-sm text-white" onClick={search}>조회</button>
        <button
          type="button"
          className="rounded-md border border-primary px-3 py-2 text-sm text-primary"
          onClick={() => {
            const data = result ?? apply();
            downloadWorkbook(
              data.map((r) => ({
                마번: r.horse_id,
                마명: nameById[r.horse_id]?.마명 ?? "",
                부마명: r.sire_name ?? "",
                성별: r.sex ?? "",
                출생일: r.birth_date ?? "",
                신청인: r.applicant_name ?? "",
                목장명: r.farm_name ?? "",
                입사일: r.farm_in_date ?? "",
                퇴사일: r.farm_out_date ?? "",
                위탁비: r.entrustment_fee ?? "",
              })),
              "위수탁마",
              `위수탁마_${year || "검색"}.xlsx`,
            );
          }}
        >
          엑셀 다운로드
        </button>
      </div>
      {result == null ? (
        <EmptyState message="필터를 하나 이상 입력한 뒤 조회하세요" />
      ) : result.length === 0 ? (
        <EmptyState message="조건에 맞는 위수탁마가 없습니다" />
      ) : (
        <Card className="overflow-x-auto">
          <div className="mb-2 text-sm text-gray-500">{result.length}두</div>
          <table className="min-w-[1100px] w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-400">
                {["마번", "마명", "부마명", "성별", "출생일", "신청인", "목장명", "입사일", "퇴사일", "위탁비"].map((c) => (
                  <th key={c} className="px-2 py-1">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.map((r) => (
                <tr key={r.horse_id} className="border-b border-gray-100">
                  <td className="px-2 py-1.5 text-gray-500">{r.horse_id}</td>
                  <td className="px-2 py-1.5">{nameById[r.horse_id]?.마명 ?? "-"}</td>
                  <td className="px-2 py-1.5">{fmtText(r.sire_name)}</td>
                  <td className="px-2 py-1.5">{fmtText(r.sex)}</td>
                  <td className="px-2 py-1.5">{fmtDate(r.birth_date)}</td>
                  <td className="px-2 py-1.5">{fmtText(r.applicant_name)}</td>
                  <td className="px-2 py-1.5">{fmtText(r.farm_name)}</td>
                  <td className="px-2 py-1.5">{fmtDate(r.farm_in_date)}</td>
                  <td className="px-2 py-1.5">{fmtDate(r.farm_out_date)}</td>
                  <td className="px-2 py-1.5 text-right">{fmtFee(r.entrustment_fee)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function ReportSection() {
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [rows, setRows] = useState<EntrustmentRow[]>([]);
  const [scope, setScope] = useState<"year" | "all">("year");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [ready, setReady] = useState(false);

  useEffect(() => {
    Promise.all([listHorses(), listEntrustment()]).then(([h, e]) => {
      setHorses(h);
      setRows(e);
    });
  }, []);

  const subset = useMemo(() => {
    if (scope === "all") return rows;
    return rows.filter((r) => r.application_year === Number(year));
  }, [rows, scope, year]);

  const kpis = useMemo(() => {
    const entrusted = subset.filter((r) => r.status === STATUS_ENTRUSTED).length;
    const ended = subset.filter((r) => r.status === STATUS_ENDED).length;
    const fee = subset.reduce((s, r) => s + (r.entrustment_fee || 0), 0);
    const won = subset.filter((r) => classifyAuction(r.first_result, r.final_result) === "낙찰").length;
    const price = subset.reduce((s, r) => s + hammerPriceFromResult(r.first_result, r.final_result), 0);
    return { total: subset.length, entrusted, ended, fee, won, price };
  }, [subset]);

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <div className="no-print flex flex-wrap items-end gap-3">
        <select className="rounded-md border border-gray-200 px-3 py-2" value={scope} onChange={(e) => setScope(e.target.value as "year" | "all")}>
          <option value="year">사업연도별</option>
          <option value="all">전체 기간</option>
        </select>
        {scope === "year" ? (
          <input className="w-36 rounded-md border border-gray-200 px-3 py-2" type="number" value={year} onChange={(e) => setYear(e.target.value)} />
        ) : null}
        <button type="button" className="rounded-md bg-primary px-3 py-2 text-sm text-white" onClick={() => setReady(true)}>미리보기</button>
        <button type="button" className="rounded-md border border-primary px-3 py-2 text-sm text-primary" disabled={!ready} onClick={() => window.print()}>인쇄</button>
      </div>
      {!ready ? (
        <EmptyState message="집계 범위와 연도를 선택한 뒤 미리보기" />
      ) : (
        <Card className="print-area">
          <div className="text-xs text-gray-500">제주목장 · 위탁 통계 보고</div>
          <div className="text-xl font-medium">{scope === "all" ? "전체 기간" : `${year}년`} 요약</div>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Kpi label="위탁 두수" value={`${kpis.total}두`} />
            <Kpi label="위탁중" value={`${kpis.entrusted}두`} />
            <Kpi label="위탁종료" value={`${kpis.ended}두`} />
            <Kpi label="위탁비 합계" value={`${kpis.fee.toLocaleString("ko-KR")}원`} />
            <Kpi label="낙찰 두수" value={`${kpis.won}두`} />
            <Kpi label="낙찰가 합계" value={`${kpis.price.toLocaleString("ko-KR")}원`} />
          </div>
          <p className="mt-3 text-xs text-gray-400">보유마 {horses.length}두 기준 위탁 계약만 집계합니다.</p>
        </Card>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm border border-gray-200 bg-gray-50 p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-medium">{value}</div>
    </div>
  );
}
