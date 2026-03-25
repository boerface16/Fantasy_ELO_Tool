"""
V5.3 ELO Calculator (MLB 포팅) + K-Modulation (Hybrid A1+C2)

KBO V5.3 Zero-Sum ELO Engine의 MLB 포팅.
Phase 1: xwOBA 기반 K-Modulation 추가.

핵심 공식 (K-Modulation):
  adjusted_rv  = delta_run_exp - park_adjustment
  rv_diff      = adjusted_rv - mean_rv[state]
  K_base       = EVENT_K_FACTORS[result_type]
  modifier     = physics_modifier(result_type, xwoba)
  K_effective  = K_base × modifier
  batter_delta = K_effective × rv_diff
  pitcher_delta = -batter_delta  (Zero-Sum)

Key Features:
  - True Zero-Sum: batter_delta = -pitcher_delta
  - Layer 1 (C2): Event-type K-factor table
  - Layer 2 (A1): xwOBA-based physics modifier [0.7, 1.3]
  - State normalization: base-out state별 기대 RV 보정
  - Park factor: 구장별 scoring environment 보정
  - Field error handling: 에러 시 타자 유리한 ELO 변동 차단
  - MIN_ELO=500 (하한선)
"""

from dataclasses import dataclass
from typing import Optional

from src.engine.elo_config import (
    EVENT_K_FACTORS,
    INITIAL_ELO,
    K_FACTOR,
    LEAGUE_AVG_XWOBA,
    MIN_ELO,
    NON_BIP_TYPES,
    PHYSICS_ALPHA,
    PHYSICS_MOD_MAX,
    PHYSICS_MOD_MIN,
)


@dataclass
class PlayerEloState:
    """선수 ELO 상태 (Two-Way Player 지원: batting/pitching 분리)."""
    player_id: int
    batting_elo: float = INITIAL_ELO
    pitching_elo: float = INITIAL_ELO
    batting_pa: int = 0
    pitching_pa: int = 0
    cumulative_rv: float = 0.0

    @property
    def elo(self) -> float:
        """하위 호환용 composite ELO (가중 평균)."""
        total = self.batting_pa + self.pitching_pa
        if total == 0:
            return INITIAL_ELO
        return (self.batting_elo * self.batting_pa +
                self.pitching_elo * self.pitching_pa) / total

    @property
    def pa_count(self) -> int:
        """하위 호환용 총 PA."""
        return self.batting_pa + self.pitching_pa

    def apply_batting_delta(self, delta: float) -> None:
        """타자 ELO 변화 적용 (하한선 보장)."""
        self.batting_elo = max(MIN_ELO, self.batting_elo + delta)

    def apply_pitching_delta(self, delta: float) -> None:
        """투수 ELO 변화 적용 (하한선 보장)."""
        self.pitching_elo = max(MIN_ELO, self.pitching_elo + delta)


def calculate_physics_modifier(
    result_type: Optional[str],
    xwoba: Optional[float],
) -> float:
    """BIP 이벤트의 물리 품질에 따라 K-factor modifier 반환.

    - Non-BIP (K, BB, HBP 등): modifier = 1.0
    - BIP (hit, out, etc.): xwOBA 기반 modifier [0.7, 1.3]
    """
    if result_type is None or result_type in NON_BIP_TYPES:
        return 1.0

    if xwoba is None:
        return 1.0

    deviation = xwoba - LEAGUE_AVG_XWOBA
    modifier = 1.0 + PHYSICS_ALPHA * (deviation / LEAGUE_AVG_XWOBA)
    return max(PHYSICS_MOD_MIN, min(PHYSICS_MOD_MAX, modifier))


@dataclass
class EloUpdateResult:
    """타석 ELO 업데이트 결과."""
    batter_delta: float
    pitcher_delta: float
    batter_elo_before: float
    batter_elo_after: float
    pitcher_elo_before: float
    pitcher_elo_after: float
    k_base: float = 0.0
    physics_mod: float = 1.0
    k_effective: float = 0.0


class EloCalculator:
    """V5.3 ELO 계산기."""

    def __init__(self, k_factor: float = K_FACTOR,
                 re24_baseline=None, park_factor_obj=None):
        self.k_factor = k_factor
        self.re24_baseline = re24_baseline      # RE24Baseline or None
        self.park_factor = park_factor_obj      # ParkFactor or None

    def process_plate_appearance(
        self,
        batter: PlayerEloState,
        pitcher: PlayerEloState,
        delta_run_exp: Optional[float],
        state: int = 0,
        home_team: Optional[str] = None,
        result_type: Optional[str] = None,
        xwoba: Optional[float] = None,
    ) -> EloUpdateResult:
        """
        타석 결과 처리 (K-Modulation 적용).

        Args:
            batter: 타자 ELO 상태
            pitcher: 투수 ELO 상태
            delta_run_exp: Run Expectancy 변화량 (None이면 ELO 변화 없음)
            state: base-out state (0~23)
            home_team: 홈팀 약칭 (park factor용)
            result_type: 결과 타입 ('E' 등 field error 감지용)
            xwoba: expected wOBA (physics modifier용, None이면 modifier=1.0)

        Returns:
            EloUpdateResult
        """
        batter_elo_before = batter.batting_elo
        pitcher_elo_before = pitcher.pitching_elo

        # K-Modulation: Layer 1 (event K) × Layer 2 (physics modifier)
        k_base = EVENT_K_FACTORS.get(result_type, self.k_factor) if result_type else self.k_factor
        physics_mod = calculate_physics_modifier(result_type, xwoba)
        k_effective = k_base * physics_mod

        if delta_run_exp is not None:
            # Step 1: Park factor adjustment
            if self.park_factor and home_team:
                adjusted_rv = self.park_factor.adjust_rv(delta_run_exp, home_team)
            else:
                adjusted_rv = delta_run_exp

            # Step 2: State normalization
            if self.re24_baseline:
                expected_rv = self.re24_baseline.get_expected_rv(state)
                rv_diff = adjusted_rv - expected_rv
            else:
                rv_diff = adjusted_rv

            # Step 3: ELO delta (K-Modulation)
            batter_delta = k_effective * rv_diff
            pitcher_delta = -batter_delta

            # Step 4: Field error handling
            if result_type and result_type.upper() in ('E', 'FIELD_ERROR'):
                if batter_delta > 0:
                    batter_delta = 0.0
                if pitcher_delta < 0:
                    pitcher_delta = 0.0

            batter.apply_batting_delta(batter_delta)
            pitcher.apply_pitching_delta(pitcher_delta)

            batter.cumulative_rv += delta_run_exp
            pitcher.cumulative_rv -= delta_run_exp
        else:
            batter_delta = 0.0
            pitcher_delta = 0.0

        batter.batting_pa += 1
        pitcher.pitching_pa += 1

        return EloUpdateResult(
            batter_delta=batter_delta,
            pitcher_delta=pitcher_delta,
            batter_elo_before=batter_elo_before,
            batter_elo_after=batter.batting_elo,
            pitcher_elo_before=pitcher_elo_before,
            pitcher_elo_after=pitcher.pitching_elo,
            k_base=k_base,
            physics_mod=physics_mod,
            k_effective=k_effective,
        )
