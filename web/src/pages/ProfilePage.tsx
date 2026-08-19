import { useEffect, useState } from "react";
import {
  getCareer,
  getEntrustment,
  listAuctionsForHorse,
  listEntrustment,
  listHorses,
  listRacesForHorse,
} from "../lib/api";
import { fmtDate, fmtFee, fmtText } from "../lib/format";
import { normalizeHorseNumber } from "../lib/horseNumber";
import type { AuctionRow, CareerRow, EntrustmentRow, HorseRow, RaceRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { useNotify } from "../components/Toast";

export function ProfilePage() {
  const notify = useNotify();
  const [mode, setMode] = useState("마번");
  const [query, setQuery] = useState("");
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [entrust, setEntrust] = useState<EntrustmentRow[]>([]);
  const [list, setList] = useState<EntrustmentRow[] | null>(null);
  const [detail, setDetail] = useState<{
    horse: EntrustmentRow;
    name: string;
    auctions: AuctionRow[];
    races: RaceRow[];
    career: CareerRow | null;
  } | null>(null);

  useEffect(() => {
    Promise.all([listHorses(), listEntrustment()]).then(([h, e]) => {
      setHorses(h);
      setEntrust(e);
    });
  }, []);

  const nameById = Object.fromEntries(horses.map((h) => [h.마번, h.마명]));

  async function loadDetail(horseId: string) {
    const id = normalizeHorseNumber(horseId);
    if (!id) return;
    const horse = await getEntrustment(id);
    if (!horse) {
      setDetail(null);
      notify(`마번 ${id}에 해당하는 위탁 계약이 없습니다`, "warn");
      return;
    }
    const [auctions, races, career] = await Promise.all([
      listAuctionsForHorse(id),
      listRacesForHorse(id),
      getCareer(id),
    ]);
    setDetail({
      horse,
      name: nameById[id] ?? horse.horse_id,
      auctions,
      races,
      career,
    });
  }

  async function onSearch() {
    setDetail(null);
    if (mode === "신청인") {
      if (!query.trim()) {
        notify("신청인을 입력하세요.", "warn");
        return;
      }
      const q = query.trim();
      setList(
        entrust
          .filter((e) => (e.applicant_name ?? "").includes(q))
          .sort((a, b) => (nameById[a.horse_id] ?? "").localeCompare(nameById[b.horse_id] ?? "", "ko")),
      );
      return;
    }
    setList(null);
    if (!query.trim()) {
      notify("마번을 입력하세요.", "warn");
      return;
    }
    await loadDetail(query);
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-medium">통합조회</h1>
      <div className="flex flex-wrap items-end gap-3">
        <select className="w-36 rounded-md border border-gray-200 px-3 py-2" value={mode} onChange={(e) => { setMode(e.target.value); setQuery(""); setList(null); setDetail(null); }}>
          <option>마번</option>
          <option>신청인</option>
        </select>
        <input
          className="w-56 rounded-md border border-gray-200 px-3 py-2"
          placeholder={mode === "신청인" ? "신청인" : "마번 (7자리)"}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearch()}
        />
        <button type="button" className="rounded-md bg-primary px-3 py-2 text-sm text-white" onClick={onSearch}>
          조회
        </button>
      </div>
      {list ? (
        <Card className="overflow-x-auto">
          <div className="mb-2 text-sm text-gray-500">신청인「{query}」 {list.length}두</div>
          {list.length === 0 ? (
            <EmptyState message="해당 신청인의 위수탁마가 없습니다" />
          ) : (
            <table className="min-w-[780px] w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs text-gray-400">
                  <th className="px-2 py-1">마번</th>
                  <th className="px-2 py-1">마명</th>
                  <th className="px-2 py-1">사업연도</th>
                  <th className="px-2 py-1">목장명</th>
                  <th className="px-2 py-1">상태</th>
                  <th className="px-2 py-1 text-right">위탁비</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.map((h) => (
                  <tr key={h.horse_id} className="border-b border-gray-100">
                    <td className="px-2 py-1.5 text-gray-500">{h.horse_id}</td>
                    <td className="px-2 py-1.5">{nameById[h.horse_id] ?? "-"}</td>
                    <td className="px-2 py-1.5">{fmtText(h.application_year)}</td>
                    <td className="px-2 py-1.5">{fmtText(h.farm_name)}</td>
                    <td className="px-2 py-1.5">{h.status}</td>
                    <td className="px-2 py-1.5 text-right">{fmtFee(h.entrustment_fee)}</td>
                    <td>
                      <button type="button" className="text-sm text-primary" onClick={() => loadDetail(h.horse_id)}>
                        상세
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      ) : null}
      {detail ? (
        <div className="flex flex-col gap-3">
          <Card>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-sm font-medium">위탁 정보</span>
              <StatusBadge status={detail.horse.status} />
            </div>
            <div className="grid gap-x-8 sm:grid-cols-2">
              {[
                ["마번", fmtText(detail.horse.horse_id)],
                ["마명", fmtText(detail.name)],
                ["부마명", fmtText(detail.horse.sire_name)],
                ["성별", fmtText(detail.horse.sex)],
                ["출생일", fmtDate(detail.horse.birth_date)],
                ["사업연도", fmtText(detail.horse.application_year)],
                ["신청인", fmtText(detail.horse.applicant_name)],
                ["목장명", fmtText(detail.horse.farm_name)],
                ["입사일", fmtDate(detail.horse.farm_in_date)],
                ["퇴사일", fmtDate(detail.horse.farm_out_date)],
                ["위탁비", fmtFee(detail.horse.entrustment_fee)],
                ["최초경매결과", fmtText(detail.horse.first_result)],
                ["최종경매결과", fmtText(detail.horse.final_result)],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between border-b border-gray-100 py-1 text-sm">
                  <span className="text-gray-500">{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <div className="mb-2 text-sm font-medium">경매 이력</div>
            {detail.auctions.length === 0 ? (
              <EmptyState message="경매 이력이 없습니다" />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-xs text-gray-400">
                    <th className="px-2 py-1">상장일</th>
                    <th className="px-2 py-1">결과</th>
                    <th className="px-2 py-1 text-right">낙찰가</th>
                    <th className="px-2 py-1">구매자</th>
                    <th className="px-2 py-1">최종</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.auctions.map((a) => (
                    <tr key={a.id} className="border-b border-gray-100">
                      <td className="px-2 py-1.5">{fmtDate(a.auction_date)}</td>
                      <td className="px-2 py-1.5">{fmtText(a.auction_name)}</td>
                      <td className="px-2 py-1.5 text-right">{fmtFee(a.hammer_price)}</td>
                      <td className="px-2 py-1.5">{fmtText(a.buyer_name)}</td>
                      <td className="px-2 py-1.5">{a.is_final ? "Y" : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <Card>
            <div className="mb-2 text-sm font-medium">경주성적</div>
            {detail.career ? (
              <div className="mb-3 flex flex-wrap gap-3 text-sm">
                <span className="rounded-md bg-gray-50 px-3 py-1">출주 {detail.career.total_starts}</span>
                <span className="rounded-md bg-gray-50 px-3 py-1">1위 {detail.career.total_wins}</span>
                <span className="rounded-md bg-gray-50 px-3 py-1">승률 {detail.career.win_rate}%</span>
                <span className="rounded-md bg-gray-50 px-3 py-1">총상금 {(detail.career.total_prize_money || 0).toLocaleString("ko-KR")}</span>
              </div>
            ) : null}
            {detail.races.length === 0 ? (
              <EmptyState message="경주 기록이 없습니다" />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-xs text-gray-400">
                    <th className="px-2 py-1">경주일자</th>
                    <th className="px-2 py-1">경주명</th>
                    <th className="px-2 py-1">거리</th>
                    <th className="px-2 py-1">순위</th>
                    <th className="px-2 py-1">기수</th>
                    <th className="px-2 py-1">기록</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.races.map((r) => (
                    <tr key={r.id} className="border-b border-gray-100">
                      <td className="px-2 py-1.5">{fmtDate(r.race_date)}</td>
                      <td className="px-2 py-1.5">{fmtText(r.race_name)}</td>
                      <td className="px-2 py-1.5">{r.distance ?? "-"}</td>
                      <td className="px-2 py-1.5">{fmtText(r.rank)}</td>
                      <td className="px-2 py-1.5">{fmtText(r.jockey)}</td>
                      <td className="px-2 py-1.5">{fmtText(r.record_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      ) : !list ? (
        <EmptyState message="검색 기준을 고른 뒤 조회하세요" />
      ) : (
        <EmptyState message="목록에서 「상세」를 누르면 아래에 표시됩니다" />
      )}
    </div>
  );
}
