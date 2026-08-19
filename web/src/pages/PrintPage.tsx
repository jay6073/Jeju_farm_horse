import { useEffect, useState } from "react";
import { listEntrustment, listHorses } from "../lib/api";
import { HORSE_SPECIES } from "../lib/constants";
import { fmtDate, fmtText } from "../lib/format";
import type { EntrustmentRow, HorseRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useNotify } from "../components/Toast";

type PrintRow = {
  마번: string;
  마명: string;
  출생일: string;
  성별: string;
  부마명: string;
  모마명: string;
  신청인?: string;
};

export function PrintPage() {
  const notify = useNotify();
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [entrust, setEntrust] = useState<EntrustmentRow[]>([]);
  const [species, setSpecies] = useState("");
  const [year, setYear] = useState("");
  const [rows, setRows] = useState<PrintRow[] | null>(null);

  useEffect(() => {
    Promise.all([listHorses(), listEntrustment()])
      .then(([h, e]) => {
        setHorses(h);
        setEntrust(e);
      })
      .catch((err: unknown) => notify(err instanceof Error ? err.message : "실패", "err"));
  }, [notify]);

  function preview() {
    if (!species) {
      notify("마종을 선택하세요.", "warn");
      return;
    }
    if (species === "위수탁마") {
      if (!year) {
        notify("사업연도를 입력하세요.", "warn");
        return;
      }
      const y = Number(year);
      const nameById = Object.fromEntries(horses.map((h) => [h.마번, h]));
      setRows(
        entrust
          .filter((e) => e.application_year === y)
          .map((e) => {
            const h = nameById[e.horse_id];
            return {
              마번: e.horse_id,
              마명: h?.마명 ?? "-",
              출생일: fmtDate(e.birth_date ?? h?.출생일),
              성별: fmtText(e.sex ?? h?.성별),
              부마명: fmtText(e.sire_name ?? h?.부마명),
              모마명: "-",
              신청인: fmtText(e.applicant_name),
            };
          }),
      );
      return;
    }
    setRows(
      horses
        .filter((h) => h.마종 === species && h.상태 === "정상")
        .map((h) => ({
          마번: h.마번 || "-",
          마명: h.마명,
          출생일: fmtDate(h.출생일),
          성별: fmtText(h.성별),
          부마명: fmtText(h.부마명),
          모마명: fmtText(h.모마명),
        })),
    );
  }

  const isEntrust = species === "위수탁마";
  const cols = isEntrust
    ? ["마번", "마명", "출생일", "성별", "부마명", "모마명", "신청인"]
    : ["마번", "마명", "출생일", "성별", "부마명", "모마명"];

  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <div className="no-print flex items-center justify-between">
        <h1 className="text-xl font-medium">마종별 명단 출력</h1>
      </div>
      <div className="no-print flex flex-wrap items-end gap-3">
        <select className="rounded-md border border-gray-200 px-3 py-2" value={species} onChange={(e) => { setSpecies(e.target.value); setRows(null); }}>
          <option value="">마종</option>
          {HORSE_SPECIES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        {isEntrust ? (
          <input className="w-36 rounded-md border border-gray-200 px-3 py-2" type="number" placeholder="사업연도" value={year} onChange={(e) => setYear(e.target.value)} />
        ) : null}
        <button type="button" className="rounded-md bg-primary px-3 py-2 text-sm text-white" onClick={preview}>
          미리보기
        </button>
        <button
          type="button"
          className="rounded-md border border-primary px-3 py-2 text-sm text-primary disabled:opacity-40"
          disabled={!rows}
          onClick={() => window.print()}
        >
          인쇄
        </button>
      </div>
      <p className="no-print text-xs text-gray-400">
        일반 마종은 상태=정상만, DB 캐시 기준입니다. 캐시가 없는 말은 '-'로 표시됩니다. horsepia 보강은 파이썬 앱에서 합니다.
      </p>
      {rows == null ? (
        <EmptyState message="마종을 선택한 뒤 미리보기를 누르세요" />
      ) : (
        <Card className="print-area">
          <div className="mb-1 text-base font-medium">
            {isEntrust ? `${species} 명단 (${year}년)` : `${species} 보유마 명단`}
          </div>
          <div className="mb-3 text-xs text-gray-500">출력 대상 {rows.length}두</div>
          {rows.length === 0 ? (
            <EmptyState message={`${species}에 해당하는 말이 없습니다`} />
          ) : (
            <div className="overflow-x-auto">
              <table className="print-table w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-xs text-gray-400">
                    {cols.map((c) => (
                      <th key={c} className="px-2 py-1">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.마번 + r.마명} className="border-b border-gray-100">
                      {cols.map((c) => (
                        <td key={c} className="px-2 py-1.5">{r[c as keyof PrintRow] ?? "-"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
