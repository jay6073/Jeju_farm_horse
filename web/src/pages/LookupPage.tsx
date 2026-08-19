import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getHorseById, listHorses } from "../lib/api";
import { HORSE_SPECIES } from "../lib/constants";
import { downloadWorkbook } from "../lib/excel";
import { fmtDate, fmtText, getBreedLabel } from "../lib/format";
import type { HorseRow } from "../lib/types";
import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { useNotify } from "../components/Toast";

export function LookupPage() {
  const notify = useNotify();
  const [params] = useSearchParams();
  const [horses, setHorses] = useState<HorseRow[]>([]);
  const [species, setSpecies] = useState("");
  const [horseId, setHorseId] = useState("");
  const [selected, setSelected] = useState<HorseRow | null>(null);

  useEffect(() => {
    listHorses()
      .then(setHorses)
      .catch((err: unknown) => notify(err instanceof Error ? err.message : "불러오기 실패", "err"));
  }, [notify]);

  useEffect(() => {
    const raw = params.get("horse_id");
    if (!raw) return;
    const id = Number(raw);
    if (!id) return;
    getHorseById(id).then((horse) => {
      if (!horse) return;
      setSpecies(horse.마종);
      setHorseId(String(horse.id));
      setSelected(horse);
    });
  }, [params]);

  const options = useMemo(
    () => horses.filter((h) => h.마종 === species && h.상태 === "정상"),
    [horses, species],
  );

  function onSelectHorse(id: string) {
    setHorseId(id);
    const horse = horses.find((h) => String(h.id) === id) ?? null;
    setSelected(horse);
  }

  const fields = selected
    ? [
        ["마번", fmtText(selected.마번)],
        ["출생일", fmtDate(selected.출생일)],
        ["성별", fmtText(selected.성별)],
        ["부마명", fmtText(selected.부마명)],
        ["모마명", fmtText(selected.모마명)],
        ["품종", getBreedLabel(selected.품종코드)],
      ]
    : [];

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h1 className="text-xl font-medium">보유마 조회</h1>
      <div className="flex gap-3">
        <select
          className="flex-1 rounded-md border border-gray-200 px-3 py-2"
          value={species}
          onChange={(e) => {
            setSpecies(e.target.value);
            setHorseId("");
            setSelected(null);
          }}
        >
          <option value="">마종</option>
          {HORSE_SPECIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className="flex-1 rounded-md border border-gray-200 px-3 py-2"
          value={horseId}
          disabled={!species}
          onChange={(e) => onSelectHorse(e.target.value)}
        >
          <option value="">마명</option>
          {options.map((h) => (
            <option key={h.id} value={h.id}>
              {h.마명}
            </option>
          ))}
        </select>
      </div>
      {!species ? (
        <EmptyState message="마종을 먼저 선택하세요" />
      ) : !selected ? (
        <EmptyState message="마명을 선택하면 마적사항이 표시됩니다" />
      ) : (
        <Card>
          <div className="mb-2 flex items-center gap-2">
            <span className="text-lg font-medium">{selected.마명}</span>
            <span className="ml-auto rounded bg-gray-100 px-2 py-0.5 text-xs">{selected.마종}</span>
          </div>
          {fields.map(([label, value]) => (
            <div key={label} className="flex justify-between border-b border-gray-100 py-1 text-sm">
              <span className="text-gray-500">{label}</span>
              <span>{value}</span>
            </div>
          ))}
          <p className="mt-3 text-xs text-gray-400">
            horsepia 실시간 조회는 파이썬 앱에서 실행합니다. 여기에는 DB에 저장된 마적만 표시됩니다.
          </p>
          <button
            type="button"
            className="mt-3 rounded-md border border-primary px-3 py-1.5 text-sm text-primary"
            onClick={() =>
              downloadWorkbook(
                [Object.fromEntries(fields)],
                "마적사항",
                `${selected.마명}_마적사항.xlsx`,
              )
            }
          >
            엑셀로 저장
          </button>
        </Card>
      )}
    </div>
  );
}
