const STYLES: Record<string, string> = {
  정상: "bg-green-100 text-green-700",
  폐사: "bg-gray-200 text-gray-600",
  위수탁종료: "bg-gray-200 text-gray-600",
  매각: "bg-gray-200 text-gray-600",
  위탁중: "bg-blue-100 text-blue-700",
  위탁종료: "bg-gray-200 text-gray-600",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STYLES[status] ?? "bg-orange-100 text-orange-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${style}`}>{status}</span>
  );
}
