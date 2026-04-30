import type { PlayerTalentRadar } from '../../types/talent';

interface AxisConfig {
  key: string;
  label: string;
}

const BATTER_AXES: AxisConfig[] = [
  { key: 'main',       label: 'Main ELO'   },
  { key: 'contact',    label: 'Contact'    },
  { key: 'power',      label: 'Power'      },
  { key: 'discipline', label: 'Discipline' },
  { key: 'speed',      label: 'Speed'      },
  { key: 'clutch',     label: 'Clutch'     },
];

const PITCHER_AXES: AxisConfig[] = [
  { key: 'main',            label: 'Main ELO'  },
  { key: 'stuff',           label: 'Stuff'     },
  { key: 'bip_suppression', label: 'BIP Supp.' },
  { key: 'command',         label: 'Command'   },
];

function toZScore(elo: number, mean: number, std: number): number {
  if (std <= 0) return 0;
  return (elo - mean) / std;
}

function zToRadius(z: number): number {
  return Math.max(0.05, Math.min(1.0, 0.5 + z / 4.0));
}

interface DimInfo {
  elo: number;
  mean: number;
  std: number;
  rank: number | null;
  total: number | null;
}

function getDimInfo(axisKey: string, radar: PlayerTalentRadar, seasonMode: boolean): DimInfo | null {
  if (axisKey === 'main') {
    if (!radar.mainElo) return null;
    const { seasonElo, leagueMean, leagueStd } = radar.mainElo;
    return { elo: seasonElo, mean: leagueMean, std: leagueStd, rank: null, total: null };
  }
  const dim = radar.dimensions.find(d => d.talentType === axisKey);
  if (!dim) return null;
  return {
    elo: dim.seasonElo,
    mean: seasonMode ? 1500 : (dim.leagueMean ?? 1500),
    std: dim.leagueStd ?? 50,
    rank: dim.seasonRank,
    total: dim.totalPlayers,
  };
}

function getRadius(axisKey: string, radar: PlayerTalentRadar, seasonMode: boolean): number {
  const info = getDimInfo(axisKey, radar, seasonMode);
  if (!info) return 0.5;
  return zToRadius(toZScore(info.elo, info.mean, info.std));
}

const CX = 180;
const CY = 180;
const R = 118;
const LABEL_PAD = 26;

function axisAngle(i: number, n: number): number {
  return -Math.PI / 2 + (i * 2 * Math.PI) / n;
}

function polarToXY(r: number, i: number, n: number): [number, number] {
  const a = axisAngle(i, n);
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}

function buildPolygon(axes: AxisConfig[], radar: PlayerTalentRadar, seasonMode: boolean): string {
  return axes
    .map((ax, i) => {
      const p = getRadius(ax.key, radar, seasonMode);
      const [x, y] = polarToXY(R * p, i, axes.length);
      return `${x},${y}`;
    })
    .join(' ');
}

function buildRingPolygon(fraction: number, n: number): string {
  return Array.from({ length: n }, (_, i) => {
    const [x, y] = polarToXY(R * fraction, i, n);
    return `${x},${y}`;
  }).join(' ');
}

function labelAnchor(x: number): 'start' | 'middle' | 'end' {
  if (x < CX - 4) return 'end';
  if (x > CX + 4) return 'start';
  return 'middle';
}

function labelBaseline(y: number): 'auto' | 'middle' | 'hanging' {
  if (y < CY - 4) return 'auto';
  if (y > CY + 4) return 'hanging';
  return 'middle';
}

export interface RadarPlayerData {
  name: string;
  team: string;
  color: string;
  radar: PlayerTalentRadar;
}

interface EloRadarChartProps {
  role: 'batter' | 'pitcher';
  primary: RadarPlayerData;
  compared?: RadarPlayerData[];
  seasonMode?: boolean;
}

export default function EloRadarChart({ role, primary, compared = [], seasonMode = false }: EloRadarChartProps) {
  const axes = role === 'batter' ? BATTER_AXES : PITCHER_AXES;
  const n = axes.length;
  const rings = [0.25, 0.5, 0.75, 1.0];
  const allPlayers = [primary, ...compared];

  return (
    <div>
      <svg viewBox="0 0 360 360" width="100%" height="auto" className="block">
        {/* Grid rings */}
        {rings.map(frac => (
          <polygon
            key={frac}
            points={buildRingPolygon(frac, n)}
            fill="none"
            stroke={frac === 0.5 ? '#3d3d52' : '#2a2a38'}
            strokeWidth={frac === 0.5 ? 1.5 : 1}
            strokeDasharray={frac === 1.0 ? undefined : '3 3'}
          />
        ))}

        {/* Axis lines */}
        {axes.map((_, i) => {
          const [x, y] = polarToXY(R, i, n);
          return (
            <line
              key={i}
              x1={CX} y1={CY}
              x2={x} y2={y}
              stroke="#232334"
              strokeWidth={1}
            />
          );
        })}

        {/* Ring labels: AVG and Elite */}
        {(() => {
          const [ax, ay] = polarToXY(R * 0.5, 0, n);
          const [ex, ey] = polarToXY(R * 1.0, 0, n);
          return (
            <>
              <text x={ax + 4} y={ay} fill="#5a5a72" fontSize={8} dominantBaseline="middle">{seasonMode ? '1500' : 'AVG'}</text>
              <text x={ex + 4} y={ey} fill="#5a5a72" fontSize={8} dominantBaseline="middle">Elite</text>
            </>
          );
        })()}

        {/* Player polygons — compared first, primary on top */}
        {[...compared].reverse().map((player) => (
          <polygon
            key={player.name}
            points={buildPolygon(axes, player.radar, seasonMode)}
            fill={player.color}
            fillOpacity={0.12}
            stroke={player.color}
            strokeWidth={1.5}
            strokeLinejoin="round"
          />
        ))}
        <polygon
          points={buildPolygon(axes, primary.radar, seasonMode)}
          fill={primary.color}
          fillOpacity={0.22}
          stroke={primary.color}
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* Vertex dots with tooltips */}
        {allPlayers.map((player) =>
          axes.map((ax, i) => {
            const info = getDimInfo(ax.key, player.radar, seasonMode);
            if (!info) return null;
            const z = toZScore(info.elo, info.mean, info.std);
            const p = zToRadius(z);
            const [x, y] = polarToXY(R * p, i, n);
            const tooltipParts = [
              `${ax.label}: ${Math.round(info.elo)} ELO`,
              `z = ${z.toFixed(2)}`,
              info.rank != null && info.total != null ? `#${info.rank} of ${info.total}` : null,
            ].filter(Boolean).join(' · ');
            return (
              <circle key={`${player.name}-${ax.key}`} cx={x} cy={y} r={3.5} fill={player.color} opacity={0.9}>
                <title>{tooltipParts}</title>
              </circle>
            );
          })
        )}

        {/* Axis labels */}
        {axes.map((ax, i) => {
          const [lx, ly] = polarToXY(R + LABEL_PAD, i, n);
          return (
            <text
              key={ax.key}
              x={lx}
              y={ly}
              textAnchor={labelAnchor(lx)}
              dominantBaseline={labelBaseline(ly)}
              fill="#8a8d98"
              fontSize={10}
              fontFamily="inherit"
            >
              {ax.label}
            </text>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
        {allPlayers.map(p => (
          <div key={p.name} className="flex items-center gap-1.5 text-xs text-text-secondary">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.color }} />
            <span>{p.name}</span>
            {p.team && <span className="text-text-muted">({p.team})</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
