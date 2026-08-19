import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listCareers, listEntrustment, listHorses } from "../lib/api";
import { HORSE_SPECIES, RECHECK_INTERVAL_DAYS, STATUS_ENDED } from "../lib/constants";
import { fmtDate } from "../lib/format";
import type { CareerRow, EntrustmentRow, HorseRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";

type Filter = { type: "species" | "entrustment" | null; value: string | null };

function CountCard({
  label,
  count,
  highlight,
  onClick,
}: {
  label: string;
  count: number;
  highlight: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`min-w-[90px] rounded-lg border p-4 text-left ${
        highlight ? "border-primary/20 bg-primary/10" : "border-gray-200 bg-gray-50 hover:bg-gray-100"
      }`}
    >
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-2xl font-medium ${highlight ? "text-primary" : ""}`}>{count}</div>
    </button>
  );
}

export function DashboardPage() {
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [entrust, setEntrust] = useState<EntrustmentRow[]>([]);
  const [careers, setCareers] = useState<CareerRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>({ type: null, value: null });

  useEffect(() => {
    Promise.all([listHorses(), listEntrustment(), listCareers()])
      .then(([h, e, c]) => {
        setHorses(h);
        setEntrust(e);
        setCareers(c);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "불러오기 실패"))
      .finally(() => setLoading(false));
  }, []);

  const statusMap = useMemo(
    () => Object.fromEntries(entrust.map((row) => [row.horse_id, row.status])),
    [entrust],
  );
  const counts = useMemo(() => {
    const next: Record<string, number> = Object.fromEntries(HORSE_SPECIES.map((s) => [s, 0]));
    for (const h of horses) {
      if (h.상태 === "정상") next[h.마종] = (next[h.마종] ?? 0) + 1;
    }
    next["위수탁마"] = entrust.length;
    return next;
  }, [horses, entrust]);
  const total = HORSE_SPECIES.reduce((sum, s) => sum + (counts[s] ?? 0), 0);
  const unverified = useMemo(() => {
    const cutoff = Date.now() - RECHECK_INTERVAL_DAYS * 24 * 60 * 60 * 1000;
    const map = Object.fromEntries(careers.map((c) => [c.horse_id, c]));
    const ids = new Set<string>();
    for (const row of entrust) {
      if (row.status !== STATUS_ENDED) continue;
      const summary = map[row.horse_id];
      if (!summary?.last_scraped_at) {
        ids.add(row.horse_id);
        continue;
      }
      if (new Date(summary.last_scraped_at).getTime() < cutoff) ids.add(row.horse_id);
    }
    return ids;
  }, [entrust, careers]);

  const filtered = useMemo(() => {
    let rows = horses;
    if (q.trim()) rows = rows.filter((h) => h.마명.includes(q.trim()));
    if (filter.type === "species") rows = rows.filter((h) => h.마종 === filter.value);
    if (filter.type === "entrustment") {
      if (filter.value === "미확인") rows = rows.filter((h) => h.마번 && unverified.has(h.마번));
      else rows = rows.filter((h) => h.마번 && statusMap[h.마번] === filter.value);
    }
    return rows;
  }, [horses, q, filter, statusMap, unverified]);

  const raceStats = useMemo(() => {
    const ids = new Set(filtered.map((h) => h.마번).filter(Boolean) as string[]);
    const subset = careers.filter((c) => ids.has(c.horse_id));
    return {
      wins: subset.reduce((s, c) => s + (c.total_wins || 0), 0),
      prize: subset.reduce((s, c) => s + (c.total_prize_money || 0), 0),
    };
  }, [filtered, careers]);

  if (loading) return <p className="text-sm text-gray-500">불러오는 중...</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-medium">보유두수 대시보드</h1>
      <div className="flex flex-wrap gap-3">
        <CountCard
          label="합계"
          count={total}
          highlight={filter.type === null}
          onClick={() => setFilter({ type: null, value: null })}
        />
        {HORSE_SPECIES.map((species) => (
          <CountCard
            key={species}
            label={species}
            count={counts[species] ?? 0}
            highlight={filter.type === "species" && filter.value === species}
            onClick={() => setFilter({ type: "species", value: species })}
          />
        ))}
      </div>
      <hr className="border-gray-200" />
      <div className="flex flex-wrap gap-3">
        <CountCard
          label="위탁중"
          count={entrust.filter((e) => e.status === "위탁중").length}
          highlight={filter.type === "entrustment" && filter.value === "위탁중"}
          onClick={() => setFilter({ type: "entrustment", value: "위탁중" })}
        />
        <CountCard
          label="위탁종료"
          count={entrust.filter((e) => e.status === "위탁종료").length}
          highlight={filter.type === "entrustment" && filter.value === "위탁종료"}
          onClick={() => setFilter({ type: "entrustment", value: "위탁종료" })}
        />
        <CountCard
          label="경주기록확인필요"
          count={unverified.size}
          highlight={filter.type === "entrustment" && filter.value === "미확인"}
          onClick={() => setFilter({ type: "entrustment", value: "미확인" })}
        />
      </div>
      <hr className="border-gray-200" />
      <div className="flex flex-wrap gap-3">
        <div className="min-w-[120px] rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="text-xs text-gray-500">1위 두수 합계</div>
          <div className="text-2xl font-medium text-amber-700">{raceStats.wins}두</div>
        </div>
        <div className="min-w-[120px] rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="text-xs text-gray-500">전체 상금 합계</div>
          <div className="text-2xl font-medium text-amber-700">{raceStats.prize.toLocaleString("ko-KR")}원</div>
        </div>
      </div>
      <input
        className="w-full max-w-xs rounded-md border border-gray-200 px-3 py-2 text-sm"
        placeholder="마명 검색"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {filtered.length === 0 ? (
        <EmptyState message="조건에 맞는 보유마가 없습니다" />
      ) : (
        <Card className="overflow-x-auto p-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-medium text-gray-400">
                <th className="px-2 py-1">마번</th>
                <th className="px-2 py-1">마명</th>
                <th className="px-2 py-1">마종</th>
                <th className="px-2 py-1">상태</th>
                <th className="px-2 py-1">위탁상태</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((h) => (
                <tr key={h.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-2 py-1.5 text-gray-500">{h.마번 || "-"}</td>
                  <td className="px-2 py-1.5">
                    <Link className="text-primary no-underline" to={`/main?horse_id=${h.id}`}>
                      {h.마명}
                    </Link>
                  </td>
                  <td className="px-2 py-1.5">{h.마종}</td>
                  <td className="px-2 py-1.5">
                    <span className="inline-flex items-center gap-2">
                      <StatusBadge status={h.상태} />
                      {h.상태 !== "정상" && h.상태발생일자 ? (
                        <span className="text-xs text-gray-400">{fmtDate(h.상태발생일자)}</span>
                      ) : null}
                    </span>
                  </td>
                  <td className="px-2 py-1.5">
                    {h.마번 && statusMap[h.마번] ? <StatusBadge status={statusMap[h.마번]} /> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
