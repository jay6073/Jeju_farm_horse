export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex w-full flex-col items-center gap-2 rounded-lg bg-gray-50 py-8 text-sm text-gray-400">
      {message}
    </div>
  );
}
