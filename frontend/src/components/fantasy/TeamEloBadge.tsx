import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface Props {
  teamCode: string;
  elo: number;
}

export default function TeamEloBadge({ teamCode, elo }: Props) {
  const isHot = elo > 1530;
  const isCold = elo < 1470;

  const colorClass = isHot
    ? 'bg-green-50 text-green-700 border-green-200'
    : isCold
      ? 'bg-red-50 text-red-700 border-red-200'
      : 'bg-gray-50 text-gray-600 border-gray-200';

  const Icon = isHot ? TrendingUp : isCold ? TrendingDown : Minus;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
      <Icon className="w-3 h-3" />
      <span>{teamCode}</span>
      <span className="tabular-nums">{Math.round(elo)}</span>
    </span>
  );
}
