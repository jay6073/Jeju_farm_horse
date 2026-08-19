import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  deleteAuction,
  insertAuction,
  listAuctions,
  listEntrustment,
  listHorses,
  unsetFinalExcept,
  updateAuction,
} from "../lib/api";
import { AUCTION_RESULTS, STATUS_ENDED } from "../lib/constants";
import { classifyAuction, fmtDate, fmtText, hammerPriceFromResult } from "../lib/format";
import { normalizeHorseNumber } from "../lib/horseNumber";
import type { AuctionRow, EntrustmentRow, HorseRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useNotify } from "../components/Toast";

export function AuctionPage() {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState<"register" | "list">("register");
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [entrust, setEntrust] = useState<EntrustmentRow[]>([]);
  const [auctions, setAuctions] = useState<AuctionRow[]>([]);

  async function reload() {
    const [h, e, a] = await Promise.all([listHorses(), listEntrustment(), listAuctions()]);
    setHorses(h);
    setEntrust(e);
    setAuctions(a);
  }

  useEffect(() => {
    void reload();
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-medium">경매관리</h1>
      <div className="flex border-b border-gray-200">
        <button type="button" className={`flex-1 py-2 text-sm ${tab === "register" ? "border-b-2 border-primary text-primary" : "text-gray-500"}`} onClick={() => setTab("register")}>
          경매기록 등록
        </button>
        <button type="button" className={`flex-1 py-2 text-sm ${tab === "list" ? "border-b-2 border-primary text-primary" : "text-gray-500"}`} onClick={() => setTab("list")}>
          전체 경매기록
        </button>
      </div>
      {tab === "register" ? (
        <Register horses={horses} entrust={entrust} disabled={!isAdmin} onDone={reload} />
      ) : (
        <List horses={horses} entrust={entrust} auctions={auctions} disabled={!isAdmin} onDone={reload} />
      )}
    </div>
  );
}

function Register({
  horses,
  entrust,
  disabled,
  onDone,
}: {
  horses: HorseRow[];
  entrust: EntrustmentRow[];
  disabled: boolean;
  onDone: () => Promise<void>;
}) {
  const notify = useNotify();
  const [horseId, setHorseId] = useState("");
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [price, setPrice] = useState("");
  const [buyer, setBuyer] = useState("");
  const [isFinal, setIsFinal] = useState(false);

  async function onSave() {
    const id = normalizeHorseNumber(horseId);
    if (!id) return notify("마번은 필수입니다.", "warn");
    if (!name) return notify("경매 결과를 선택하세요.", "warn");
    if (!horses.some((h) => h.마번 === id)) {
      notify(`마번 ${id}는 전체 말 관리(A)에 먼저 등록되어야 합니다.`, "err");
      return;
    }
    if (!entrust.some((e) => e.horse_id === id)) {
      notify(`마번 ${id}는 위탁 계약이 등록된 후에 경매기록을 추가할 수 있습니다.`, "err");
      return;
    }
    try {
      const created = await insertAuction({
        horse_id: id,
        auction_date: date || null,
        auction_name: name,
        hammer_price: price ? Number(price) : null,
        buyer_name: buyer || null,
        is_final: isFinal,
      });
      if (isFinal) await unsetFinalExcept(id, created.id);
      notify("경매기록 등록 완료");
      setHorseId(""); setName(""); setDate(""); setPrice(""); setBuyer(""); setIsFinal(false);
      await onDone();
    } catch (err) {
      notify(err instanceof Error ? err.message : "등록 실패", "err");
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="마번 (7자리)" value={horseId} onChange={(e) => setHorseId(e.target.value)} />
      <select className="rounded-md border border-gray-200 px-3 py-2" value={name} onChange={(e) => setName(e.target.value)}>
        <option value="">경매 결과</option>
        {AUCTION_RESULTS.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
      <input className="rounded-md border border-gray-200 px-3 py-2" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" type="number" placeholder="낙찰가 (선택)" value={price} onChange={(e) => setPrice(e.target.value)} />
      <input className="rounded-md border border-gray-200 px-3 py-2" placeholder="매수인 (선택)" value={buyer} onChange={(e) => setBuyer(e.target.value)} />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={isFinal} onChange={(e) => setIsFinal(e.target.checked)} />
        최종 낙찰 건으로 지정
      </label>
      <button type="button" disabled={disabled} className="w-fit rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" onClick={onSave}>
        + 등록
      </button>
    </div>
  );
}

function List({
  horses,
  entrust,
  auctions,
  disabled,
  onDone,
}: {
  horses: HorseRow[];
  entrust: EntrustmentRow[];
  auctions: AuctionRow[];
  disabled: boolean;
  onDone: () => Promise<void>;
}) {
  const notify = useNotify();
  const [editing, setEditing] = useState<AuctionRow | null>(null);
  const ended = new Set(entrust.filter((e) => e.status === STATUS_ENDED).map((e) => e.horse_id));
  const nameById = Object.fromEntries(horses.map((h) => [h.마번, h.마명]));
  const eById = Object.fromEntries(entrust.map((e) => [e.horse_id, e]));

  const list = useMemo(() => {
    const byHorse = new Map<string, AuctionRow>();
    const sorted = [...auctions].sort((a, b) => {
      if (a.horse_id !== b.horse_id) return a.horse_id.localeCompare(b.horse_id);
      if (Number(b.is_final) !== Number(a.is_final)) return Number(b.is_final) - Number(a.is_final);
      const rank = (n: string | null) => (n === "낙찰" ? 0 : n === "유찰" ? 1 : 2);
      if (rank(a.auction_name) !== rank(b.auction_name)) return rank(a.auction_name) - rank(b.auction_name);
      return String(b.auction_date ?? "").localeCompare(String(a.auction_date ?? ""));
    });
    for (const row of sorted) {
      if (!ended.has(row.horse_id)) continue;
      if (!byHorse.has(row.horse_id)) byHorse.set(row.horse_id, row);
    }
    return [...byHorse.values()].sort((a, b) => (nameById[a.horse_id] ?? "").localeCompare(nameById[b.horse_id] ?? "", "ko"));
  }, [auctions, ended, nameById]);

  const summary = useMemo(() => {
    let won = 0, lost = 0, unlisted = 0, totalPrice = 0;
    for (const row of list) {
      const e = eById[row.horse_id];
      const cat = classifyAuction(e?.first_result, e?.final_result);
      if (cat === "낙찰") {
        won += 1;
        totalPrice += hammerPriceFromResult(e?.first_result, e?.final_result);
      } else if (cat === "유찰") lost += 1;
      else unlisted += 1;
    }
    return { total: list.length, won, lost, unlisted, totalPrice };
  }, [list, eById]);

  async function onSave() {
    if (!editing) return;
    try {
      await updateAuction(editing.id, {
        auction_name: editing.auction_name,
        hammer_price: editing.hammer_price,
        buyer_name: editing.buyer_name,
        is_final: editing.is_final,
      });
      if (editing.is_final) await unsetFinalExcept(editing.horse_id, editing.id);
      notify("수정 완료");
      setEditing(null);
      await onDone();
    } catch (err) {
      notify(err instanceof Error ? err.message : "수정 실패", "err");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <SummaryCard label="위탁종료 두수" value={`${summary.total}두`} />
        <SummaryCard label="낙찰" value={`${summary.won}두`} />
        <SummaryCard label="유찰" value={`${summary.lost}두`} />
        <SummaryCard label="미상장" value={`${summary.unlisted}두`} />
        <SummaryCard label="낙찰가 합계" value={`${summary.totalPrice.toLocaleString("ko-KR")}원`} />
      </div>
      {list.length === 0 ? (
        <EmptyState message="등록된 경매기록이 없습니다" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="min-w-[720px] w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-400">
                <th className="px-2 py-1">마번</th>
                <th className="px-2 py-1">마명</th>
                <th className="bg-blue-50 px-2 py-1">최초상장일</th>
                <th className="bg-blue-50 px-2 py-1">최초결과</th>
                <th className="bg-blue-50 px-2 py-1">최종상장일</th>
                <th className="bg-blue-50 px-2 py-1">최종결과</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.map((r) => {
                const e = eById[r.horse_id];
                return (
                  <tr key={r.horse_id} className="border-b border-gray-100">
                    <td className="px-2 py-1.5 text-gray-500">{r.horse_id}</td>
                    <td className="px-2 py-1.5">{nameById[r.horse_id] ?? "-"}</td>
                    <td className="px-2 py-1.5">{fmtDate(e?.first_listed_date)}</td>
                    <td className="px-2 py-1.5">{fmtText(e?.first_result)}</td>
                    <td className="px-2 py-1.5">{fmtDate(e?.final_listed_date)}</td>
                    <td className="px-2 py-1.5">{fmtText(e?.final_result)}</td>
                    <td className="px-2 py-1.5">
                      {disabled ? null : (
                        <span className="flex gap-2">
                          <button type="button" className="text-primary" onClick={() => setEditing(r)}>수정</button>
                          <button
                            type="button"
                            className="text-red-600"
                            onClick={async () => {
                              if (!window.confirm(`마번 ${r.horse_id}의 대표 경매기록을 삭제할까요?`)) return;
                              await deleteAuction(r.id);
                              notify("삭제 완료");
                              await onDone();
                            }}
                          >
                            삭제
                          </button>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
      {editing ? (
        <Card className="max-w-md">
          <div className="mb-2 text-sm font-medium">경매기록 수정 (마번 {editing.horse_id})</div>
          <select className="mb-2 w-full rounded-md border border-gray-200 px-3 py-2" value={editing.auction_name ?? ""} onChange={(e) => setEditing({ ...editing, auction_name: e.target.value })}>
            {AUCTION_RESULTS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <input className="mb-2 w-full rounded-md border border-gray-200 px-3 py-2" type="number" value={editing.hammer_price ?? ""} onChange={(e) => setEditing({ ...editing, hammer_price: e.target.value ? Number(e.target.value) : null })} />
          <input className="mb-2 w-full rounded-md border border-gray-200 px-3 py-2" value={editing.buyer_name ?? ""} onChange={(e) => setEditing({ ...editing, buyer_name: e.target.value })} />
          <label className="mb-3 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={editing.is_final} onChange={(e) => setEditing({ ...editing, is_final: e.target.checked })} />
            최종 낙찰 건으로 지정
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setEditing(null)}>취소</button>
            <button type="button" className="rounded-md bg-primary px-3 py-1.5 text-white" onClick={onSave}>저장</button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="text-center">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
    </Card>
  );
}
