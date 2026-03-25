"""V5.3 ELO 설정 상수 (MLB 포팅)."""

# 초기 ELO (리그 평균)
INITIAL_ELO = 1500.0

# ELO 하한선
MIN_ELO = 500.0

# K-factor (V5.3: K=12 for stable daily volatility)
K_FACTOR = 12.0

# Park factor RV adjustment scale
ADJUSTMENT_SCALE = 0.1

# ─── K-Modulation (Hybrid A1+C2) ───

# Layer 1 (C2): Event-type K-factor table
EVENT_K_FACTORS: dict[str, float] = {
    'HR': 15.0,
    'Triple': 14.0,
    'Double': 12.0,
    'Single': 10.0,
    'OUT': 10.0,
    'GIDP': 10.0,
    'FC': 10.0,
    'StrikeOut': 6.0,
    'BB': 6.0,
    'IBB': 3.0,
    'HBP': 3.0,
    'SAC': 3.0,
    'E': 0.0,
}

# Non-BIP event types (physics modifier = 1.0)
NON_BIP_TYPES: frozenset[str] = frozenset({
    'StrikeOut', 'BB', 'IBB', 'HBP', 'SAC', 'E',
})

# Layer 2 (A1): Physics modifier config
PHYSICS_ALPHA = 0.3             # physics layer weight (conservative start)
PHYSICS_MOD_MIN = 0.7           # minimum K modifier
PHYSICS_MOD_MAX = 1.3           # maximum K modifier
LEAGUE_AVG_XWOBA = 0.315       # 2025 season average
