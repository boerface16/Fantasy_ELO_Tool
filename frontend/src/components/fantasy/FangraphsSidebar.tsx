interface Props {
  stats: Record<string, string | number> | null;
}

export default function FangraphsSidebar({ stats }: Props) {
  if (!stats) {
    return (
      <div className="bg-bg-card rounded-lg border border-border-line shadow-modern p-4">
        <div className="text-xs font-semibold text-text-secondary uppercase mb-2">Fangraphs Stats</div>
        <div className="text-sm text-text-secondary">No stats available</div>
      </div>
    );
  }

  const rows = Object.entries(stats).filter(([k]) => k !== 'Name' && k !== 'Team');

  return (
    <div className="bg-bg-card rounded-lg border border-border-line shadow-modern p-4">
      <div className="text-xs font-semibold text-text-secondary uppercase mb-3">Fangraphs Stats</div>
      <div className="space-y-1.5">
        {rows.map(([key, val]) => (
          <div key={key} className="flex justify-between text-sm">
            <span className="text-text-secondary">{key}</span>
            <span className="font-medium tabular-nums">
              {typeof val === 'number' ? val.toFixed(val < 10 ? 3 : 1) : val}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
