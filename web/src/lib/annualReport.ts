import { STATUS_ENDED, STATUS_ENTRUSTED } from "./constants";
import { classifyAuction, hammerPriceFromResult } from "./format";
import { normalizeApplicantName } from "./horseNumber";
import type { CareerRow, EntrustmentRow, HorseRow } from "./types";

export type ReportLayout = "status" | "racing";

export type ReportKpi = { label: string; value: string; unit?: string };

export type ReportPreview = {
  layout: ReportLayout;
  title: string;
  subtitle: string;
  kpis: ReportKpi[];
  applicantTitle: string;
  applicantHint: string;
  applicantHeaders: string[];
  applicantRows: Record<string, string>[];
  winRows: Array<{
    마명: string;
    경주마명: string;
    신청인: string;
    "출전(회)": string;
    "1착(회)": string;
    "상금(원)": string;
  }>;
  notes: string[];
};

function toInt(value: unknown): number {
  if (value == null || value === "") return 0;
  const n = Number(value);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function fmtNum(n: number): string {
  return n.toLocaleString("ko-KR");
}

function fmtWon(n: number): string {
  return n.toLocaleString("ko-KR");
}

function winRate(wins: number, starts: number): string {
  if (starts <= 0) return "—";
  return ((wins / starts) * 100).toFixed(1);
}

function uniqueByHorse(rows: EntrustmentRow[]): EntrustmentRow[] {
  const seen = new Set<string>();
  const out: EntrustmentRow[] = [];
  for (const row of rows) {
    if (!row.horse_id || seen.has(row.horse_id)) continue;
    seen.add(row.horse_id);
    out.push(row);
  }
  return out;
}

export function buildAnnualReport(
  scope: "year" | "all",
  year: number,
  contracts: EntrustmentRow[],
  horses: HorseRow[],
  careers: CareerRow[],
): ReportPreview {
  const subset =
    scope === "all" ? contracts : contracts.filter((r) => r.application_year === year);
  const nameById = Object.fromEntries(horses.map((h) => [h.마번 ?? "", h.마명]));
  const careerMap = Object.fromEntries(careers.map((c) => [c.horse_id, c]));
  const entrustedN = subset.filter((r) => r.status === STATUS_ENTRUSTED).length;
  const layout: ReportLayout = scope === "all" || entrustedN === 0 ? "racing" : "status";
  const scopeLabel =
    scope === "all" ? "전체 기간 위탁 계약 (마번 중복 제거 후 성적 합산)" : `사업연도 ${year} 계약`;
  const notes = [
    "단위: 두수=두, 금액=원(천 단위 콤마), 승률=%.",
    `위탁 모집단: ${scopeLabel}.`,
    "경주 지표는 해당 연도 출주에 한정하지 않으며, 작성 시점 career_summary(통산)를 마번으로 조인해 집계합니다.",
  ];

  if (layout === "status") {
    const total = subset.length;
    const nIn = entrustedN;
    const nEnd = subset.filter((r) => r.status === STATUS_ENDED).length;
    const feeSum = subset.reduce((s, r) => s + toInt(r.entrustment_fee), 0);
    const buckets = new Map<string, EntrustmentRow[]>();
    for (const row of subset) {
      const key = normalizeApplicantName(row.applicant_name);
      const list = buckets.get(key) ?? [];
      list.push(row);
      buckets.set(key, list);
    }
    const headers = ["신청인", "두수(두)", "위탁중(두)", "종료(두)", "위탁비(원)", "낙찰(두)", "낙찰가(원)"];
    const applicantRows = [...buckets.entries()]
      .sort((a, b) => b[1].length - a[1].length)
      .map(([name, items]) => {
        const won = items.filter((r) => classifyAuction(r.first_result, r.final_result) === "낙찰");
        const price = items.reduce(
          (s, r) => s + hammerPriceFromResult(r.first_result, r.final_result),
          0,
        );
        return {
          신청인: name,
          "두수(두)": fmtNum(items.length),
          "위탁중(두)": fmtNum(items.filter((r) => r.status === STATUS_ENTRUSTED).length),
          "종료(두)": fmtNum(items.filter((r) => r.status === STATUS_ENDED).length),
          "위탁비(원)": fmtWon(items.reduce((s, r) => s + toInt(r.entrustment_fee), 0)),
          "낙찰(두)": fmtNum(won.length),
          "낙찰가(원)": fmtWon(price),
        };
      });

    return {
      layout,
      title: `${year} 사업연도 위수탁 통계`,
      subtitle: "진행 연도 · 위탁 상태 중심",
      kpis: [
        { label: "위탁 두수", value: fmtNum(total), unit: "두" },
        { label: "위탁중", value: fmtNum(nIn), unit: "두" },
        { label: "위탁종료", value: fmtNum(nEnd), unit: "두" },
        { label: "위탁비 합계", value: fmtWon(feeSum), unit: "원" },
        { label: "신청인 수", value: fmtNum(buckets.size), unit: "명" },
        { label: "평균 위탁비", value: total ? fmtWon(Math.round(feeSum / total)) : "0", unit: "원" },
      ],
      applicantTitle: "신청인별 위탁 집계",
      applicantHint: "두수·위탁중·종료·위탁비·낙찰 현황입니다.",
      applicantHeaders: headers,
      applicantRows,
      winRows: [],
      notes: [
        ...notes,
        "당해(상태) 요약의 경주 성적은 위탁종료 연도·전체 기간 리포트에서 통산 기준으로 봅니다.",
      ],
    };
  }

  const raceHorses = uniqueByHorse(subset);
  const byContracts = new Map<string, EntrustmentRow[]>();
  for (const row of subset) {
    const key = normalizeApplicantName(row.applicant_name);
    const list = byContracts.get(key) ?? [];
    list.push(row);
    byContracts.set(key, list);
  }
  const byUnique = new Map<string, EntrustmentRow[]>();
  const seenPair = new Set<string>();
  for (const row of raceHorses) {
    const key = normalizeApplicantName(row.applicant_name);
    const pair = `${key}|${row.horse_id}`;
    if (seenPair.has(pair)) continue;
    seenPair.add(pair);
    const list = byUnique.get(key) ?? [];
    list.push(row);
    byUnique.set(key, list);
  }

  let startsT = 0;
  let winsT = 0;
  let prizeT = 0;
  for (const row of raceHorses) {
    const cs = careerMap[row.horse_id];
    startsT += toInt(cs?.total_starts);
    winsT += toInt(cs?.total_wins);
    prizeT += toInt(cs?.total_prize_money);
  }
  const feeSum = subset.reduce((s, r) => s + toInt(r.entrustment_fee), 0);
  const nIn = subset.filter((r) => r.status === STATUS_ENTRUSTED).length;
  const nEnd = subset.filter((r) => r.status === STATUS_ENDED).length;
  const headCol = scope === "all" ? "누적위탁(두)" : "위탁두수(두)";
  const headers = ["신청인", headCol, "총출전(회)", "1착(회)", "승률(%)", "경주상금(원)", "1착 대표마"];

  const applicantRows = [...byUnique.keys()]
    .sort((a, b) => (byUnique.get(b)?.length ?? 0) - (byUnique.get(a)?.length ?? 0))
    .map((name) => {
      const items = byUnique.get(name) ?? [];
      const contractsFor = byContracts.get(name) ?? [];
      const headCount =
        scope === "all"
          ? new Set(contractsFor.map((r) => r.horse_id).filter(Boolean)).size
          : contractsFor.length;
      let starts = 0;
      let wins = 0;
      let prize = 0;
      const winners: Array<[string, number]> = [];
      for (const row of items) {
        const cs = careerMap[row.horse_id];
        const s = toInt(cs?.total_starts);
        const w = toInt(cs?.total_wins);
        const p = toInt(cs?.total_prize_money);
        starts += s;
        wins += w;
        prize += p;
        if (w > 0) winners.push([nameById[row.horse_id] || row.horse_id, w]);
      }
      winners.sort((a, b) => b[1] - a[1]);
      return {
        신청인: name,
        [headCol]: fmtNum(headCount),
        "총출전(회)": fmtNum(starts),
        "1착(회)": fmtNum(wins),
        "승률(%)": winRate(wins, starts),
        "경주상금(원)": fmtWon(prize),
        "1착 대표마": winners.length ? winners.slice(0, 3).map(([n]) => n).join(", ") : "—",
      };
    });

  const winRows = raceHorses
    .map((row) => {
      const cs = careerMap[row.horse_id];
      const w = toInt(cs?.total_wins);
      if (w <= 0) return null;
      return {
        sortWins: w,
        sortPrize: toInt(cs?.total_prize_money),
        마명: nameById[row.horse_id] || row.horse_id,
        경주마명: cs?.registered_name || "-",
        신청인: normalizeApplicantName(row.applicant_name),
        "출전(회)": fmtNum(toInt(cs?.total_starts)),
        "1착(회)": fmtNum(w),
        "상금(원)": fmtWon(toInt(cs?.total_prize_money)),
      };
    })
    .filter((row): row is NonNullable<typeof row> => row != null)
    .sort((a, b) => b.sortWins - a.sortWins || b.sortPrize - a.sortPrize)
    .slice(0, 30)
    .map(({ sortWins: _w, sortPrize: _p, ...rest }) => rest);

  const withCareer = raceHorses.filter((r) => toInt(careerMap[r.horse_id]?.total_starts) > 0).length;

  if (scope === "all") {
    return {
      layout,
      title: "위탁사업 전체 기간 누적 통계",
      subtitle: "누적 · 신청인·통산 성적 중심",
      kpis: [
        { label: "누적 위탁 두수", value: fmtNum(raceHorses.length), unit: "두" },
        { label: "현재 위탁중", value: fmtNum(nIn), unit: "두" },
        { label: "누적 종료", value: fmtNum(nEnd), unit: "두" },
        { label: "위탁비 합계", value: fmtWon(feeSum), unit: "원" },
        { label: "누적 출전", value: fmtNum(startsT), unit: "회" },
        { label: "누적 1착", value: fmtNum(winsT), unit: "회" },
        { label: "승률 (1착÷출전)", value: winRate(winsT, startsT), unit: "%" },
        { label: "경주상금 합계", value: fmtWon(prizeT), unit: "원" },
      ],
      applicantTitle: "신청인별 경주 성과",
      applicantHint:
        "출전·1착·상금은 해당 연도 출주에 한정하지 않고 작성 시점 통산 성적(career_summary) 합산 기준입니다.",
      applicantHeaders: headers,
      applicantRows,
      winRows,
      notes,
    };
  }

  return {
    layout,
    title: `${year} 사업연도 위수탁 통계`,
    subtitle: "종료 연도 · 경주 성과 중심",
    kpis: [
      { label: "위탁 두수", value: fmtNum(subset.length), unit: "두" },
      { label: "위탁종료", value: fmtNum(nEnd), unit: "두" },
      { label: "위탁비 합계", value: fmtWon(feeSum), unit: "원" },
      { label: "총 출전 수", value: fmtNum(startsT), unit: "회" },
      { label: "1착 합계", value: fmtNum(winsT), unit: "회" },
      { label: "승률 (1착÷출전)", value: winRate(winsT, startsT), unit: "%" },
      { label: "경주상금 합계", value: fmtWon(prizeT), unit: "원" },
      { label: "성적 보유", value: fmtNum(withCareer), unit: "두" },
    ],
    applicantTitle: "신청인별 경주 성과",
    applicantHint:
      "출전·1착·상금은 해당 연도 출주에 한정하지 않고 작성 시점 통산 성적(career_summary) 합산 기준입니다.",
    applicantHeaders: headers,
    applicantRows,
    winRows,
    notes,
  };
}
