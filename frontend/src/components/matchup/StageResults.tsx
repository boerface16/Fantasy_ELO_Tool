import type { StageBreakdown, ZScoreDiffs } from '../../types/matchup';

interface StageResultsProps {
  stages: StageBreakdown;
  zDiffs: ZScoreDiffs;
}

function MiniBar({ left, right, leftColor, rightColor }: {
  left: number; right: number; leftColor: string; rightColor: string;
}) {
  const leftPct = left * 100;
  const rightPct = right * 100;
  return (
    <div className="flex h-5 rounded overflow-hidden text-[10px] font-semibold text-white">
      <div className={`${leftColor} flex items-center justify-center`} style={{ width: `${leftPct}%` }}>
        {leftPct >= 8 ? `${leftPct.toFixed(0)}%` : ''}
      </div>
      <div className={`${rightColor} flex items-center justify-center`} style={{ width: `${rightPct}%` }}>
        {rightPct >= 8 ? `${rightPct.toFixed(0)}%` : ''}
      </div>
    </div>
  );
}

function ThreeWayBar({ a, b, c, aColor, bColor, cColor }: {
  a: number; b: number; c: number; aColor: string; bColor: string; cColor: string;
}) {
  return (
    <div className="flex h-5 rounded overflow-hidden text-[10px] font-semibold text-white">
      <div className={`${aColor} flex items-center justify-center`} style={{ width: `${a * 100}%` }}>
        {a * 100 >= 8 ? `${(a * 100).toFixed(0)}%` : ''}
      </div>
      <div className={`${bColor} flex items-center justify-center`} style={{ width: `${b * 100}%` }}>
        {b * 100 >= 8 ? `${(b * 100).toFixed(0)}%` : ''}
      </div>
      <div className={`${cColor} flex items-center justify-center`} style={{ width: `${c * 100}%` }}>
        {c * 100 >= 8 ? `${(c * 100).toFixed(0)}%` : ''}
      </div>
    </div>
  );
}

function ZLabel({ label, value }: { label: string; value: number }) {
  const sign = value >= 0 ? '+' : '';
  const color = value > 0 ? 'text-green-600' : value < 0 ? 'text-red-500' : 'text-gray-500';
  return (
    <span className={`text-xs ${color}`}>
      {label} {sign}{value.toFixed(2)}
    </span>
  );
}

export default function StageResults({ stages, zDiffs }: StageResultsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Stage 1 */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
        <div className="text-xs font-semibold text-gray-400 mb-1">STAGE 1</div>
        <div className="font-semibold text-sm mb-2">BB / K / BIP Split</div>
        <ThreeWayBar
          a={stages.stage1.pBB} b={stages.stage1.pK} c={stages.stage1.pBIP}
          aColor="bg-blue-500" bColor="bg-red-500" cColor="bg-gray-400"
        />
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-2">
          <span className="text-xs text-gray-500">BB {(stages.stage1.pBB * 100).toFixed(1)}%</span>
          <span className="text-xs text-gray-500">K {(stages.stage1.pK * 100).toFixed(1)}%</span>
          <span className="text-xs text-gray-500">BIP {(stages.stage1.pBIP * 100).toFixed(1)}%</span>
        </div>
        <div className="flex flex-wrap gap-x-3 mt-1.5">
          <ZLabel label="Disc-Cmd" value={zDiffs.zDiscCmd} />
          <ZLabel label="Stuff-Con" value={zDiffs.zStuffContact} />
        </div>
      </div>

      {/* Stage 2 */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
        <div className="text-xs font-semibold text-gray-400 mb-1">STAGE 2</div>
        <div className="font-semibold text-sm mb-2">Hit / Out given BIP</div>
        <MiniBar
          left={stages.stage2.pHitGivenBIP} right={stages.stage2.pOutGivenBIP}
          leftColor="bg-green-500" rightColor="bg-gray-400"
        />
        <div className="flex gap-3 mt-2">
          <span className="text-xs text-gray-500">Hit {(stages.stage2.pHitGivenBIP * 100).toFixed(1)}%</span>
          <span className="text-xs text-gray-500">Out {(stages.stage2.pOutGivenBIP * 100).toFixed(1)}%</span>
        </div>
        <div className="mt-1.5">
          <ZLabel label="Con-BIPSupp" value={zDiffs.zContactBip} />
        </div>
      </div>

      {/* Stage 3 */}
      <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
        <div className="text-xs font-semibold text-gray-400 mb-1">STAGE 3</div>
        <div className="font-semibold text-sm mb-2">XBH / Single given Hit</div>
        <MiniBar
          left={stages.stage3.pXBHGivenHit} right={stages.stage3.p1BGivenHit}
          leftColor="bg-green-700" rightColor="bg-green-400"
        />
        <div className="flex gap-3 mt-2">
          <span className="text-xs text-gray-500">XBH {(stages.stage3.pXBHGivenHit * 100).toFixed(1)}%</span>
          <span className="text-xs text-gray-500">1B {(stages.stage3.p1BGivenHit * 100).toFixed(1)}%</span>
        </div>
        <div className="mt-1.5">
          <ZLabel label="Power" value={zDiffs.zPower} />
        </div>
      </div>
    </div>
  );
}
