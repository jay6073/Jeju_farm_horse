import { useEffect, useMemo, useState } from "react";
import { getCareer, listCareers, listEntrustment, listHorses, listRacesForHorse } from "../lib/api";
import { downloadWorkbook } from "../lib/excel";
import { fmtDate } from "../lib/format";
import { normalizeHorseNumber } from "../lib/horseNumber";
import type { CareerRow, EntrustmentRow, HorseRow, RaceRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useNotify } from "../components/Toast";

export function RacingPage() {
  const notify = useNotify();
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [entrust, setEntrust] = useState<EntrustmentRow[]>([]);
  const [careers, setCareers] = useState<CareerRow[]>([]);
  const [query, setQuery] = useState("");
  const [records, setRecords] = useState<RaceRow[] | null>(null);
  const [summary, setSummary] = useState<CareerRow | null>(null);

  useEffect(() => {
    Promise.all([listHorses(), listEntrustment(), listCareers()])
      .then(([h, e, c]) => {
        setHorses(h);
        setEntrust(e);
        setCareers(c);
      })
      .catch((err: unknown) => notify(err instanceof Error ? err.message : "실패", "err"));
  }, [notify]);

  const nameById = Object.fromEntries(horses.map((h) => [h.마번, h.마명]));
  const applicantById = Object.fromEntries(entrust.map((e) => [e.horse_id, e.applicant_name]));
  const rows = useMemo(
    () =>
      [...careers].sort((a, b) => (nameById[a.horse_id] ?? "").localeCompare(nameById[b.horse_id] ?? "", "ko")),
    [careers, nameById],
  );
  const totals = {
    horses: rows.length,
    starts: rows.reduce((s, r) => s + (r.total_starts || 0), 0),
    wins: rows.reduce((s, r) => s + (r.total_wins || 0), 0),
    prize: rows.reduce((s, r) => s + (r.total_prize_money || 0), 0),
  };

  async function onSearch() {
    const id = normalizeHorseNumber(query);
    if (!id) return notify("마번을 입력하세요.", "warn");
    const [r, s] = await Promise.all([listRacesForHorse(id), getCareer(id)]);
    setRecords(r);
    setSummary(s);
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-medium">경주성적</h1>
      <div className="rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-800">
        통산 요약은 DB에서 불러옵니다. 경주기록 전체 확인(horsepia 스크래핑)은 파이썬 앱에서 실행하세요.
      </div>
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">전체 통산성적 요약</div>
        <button
          type="button"
          className="rounded-md border border-primary px-3 py-1.5 text-sm text-primary"
          onClick={() =>
            downloadWorkbook(
              rows.map((s) => ({
                마번: s.horse_id,
                마명: nameById[s.horse_id] ?? "",
                경주마명: s.registered_name ?? "",
                위탁자: applicantById[s.horse_id] ?? "",
                출주: s.total_starts,
                "1위": s.total_wins,
                "승률(%)": s.win_rate,
                총상금: s.total_prize_money,
                최종확인일: fmtDate(s.last_scraped_at),
              })),
              "통산성적요약",
              "통산경주성적요약.xlsx",
            )
          }
        >
          엑셀 다운로드
        </button>
      </div>
      {rows.length === 0 ? (
        <EmptyState message="아직 수집된 경주성적이 없습니다" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="min-w-[760px] w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-400">
                <th className="px-2 py-1">마번</th>
                <th className="px-2 py-1">마명</th>
                <th className="px-2 py-1">경주마명</th>
                <th className="px-2 py-1">위탁자</th>
                <th className="px-2 py-1 text-right">출주</th>
                <th className="px-2 py-1 text-right">1위</th>
                <th className="px-2 py-1 text-right">승률</th>
                <th className="px-2 py-1 text-right">총상금</th>
                <th className="px-2 py-1 text-right">최종확인일</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.horse_id} className="border-b border-gray-100">
                  <td className="px-2 py-1.5 text-gray-500">{s.horse_id}</td>
                  <td className="px-2 py-1.5">{nameById[s.horse_id] ?? "-"}</td>
                  <td className="px-2 py-1.5">{s.registered_name ?? "-"}</td>
                  <td className="px-2 py-1.5 text-gray-500">{applicantById[s.horse_id] ?? "-"}</td>
                  <td className="px-2 py-1.5 text-right">{s.total_starts || 0}</td>
                  <td className="px-2 py-1.5 text-right">{s.total_wins || 0}</td>
                  <td className="px-2 py-1.5 text-right">{s.win_rate || 0}%</td>
                  <td className="px-2 py-1.5 text-right">{(s.total_prize_money || 0).toLocaleString("ko-KR")}원</td>
                  <td className="px-2 py-1.5 text-right text-xs text-gray-400">{fmtDate(s.last_scraped_at)}</td>
                </tr>
              ))}
              <tr className="bg-gray-50 font-medium">
                <td className="px-2 py-2">총 {totals.horses}두</td>
                <td /><td /><td />
                <td className="px-2 py-2 text-right">{totals.starts}</td>
                <td className="px-2 py-2 text-right">{totals.wins}</td>
                <td />
                <td className="px-2 py-2 text-right">{totals.prize.toLocaleString("ko-KR")}원</td>
                <td />
              </tr>
            </tbody>
          </table>
        </Card>
      )}
      <div className="text-sm text-gray-500">마번으로 경주기록 조회</div>
      <div className="flex max-w-xl gap-3">
        <input className="flex-1 rounded-md border border-gray-200 px-3 py-2" placeholder="마번 (7자리)" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && onSearch()} />
        <button type="button" className="rounded-md border border-primary px-3 py-2 text-sm text-primary" onClick={onSearch}>조회</button>
      </div>
      {summary ? (
        <Card>
          <div className="text-sm font-medium">경주마명 {summary.registered_name ?? "-"}</div>
          <div className="text-sm">
            {summary.total_starts}전 {summary.total_wins}승 · 승률 {summary.win_rate}% · 총상금 {(summary.total_prize_money || 0).toLocaleString("ko-KR")}원
          </div>
        </Card>
      ) : null}
      {records && records.length === 0 ? (
        <EmptyState message="경주기록이 없습니다" />
      ) : records ? (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-400">
                <th className="px-2 py-1">경주일</th>
                <th className="px-2 py-1">경주명</th>
                <th className="px-2 py-1">순위</th>
                <th className="px-2 py-1">기수</th>
                <th className="px-2 py-1">기록</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id} className="border-b border-gray-100">
                  <td className="px-2 py-1.5 text-gray-500">{fmtDate(r.race_date)}</td>
                  <td className="px-2 py-1.5">{r.race_name ?? "-"}</td>
                  <td className="px-2 py-1.5">{r.rank ?? "-"}</td>
                  <td className="px-2 py-1.5">{r.jockey ?? "-"}</td>
                  <td className="px-2 py-1.5">{r.record_time ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}
    </div>
  );
}
