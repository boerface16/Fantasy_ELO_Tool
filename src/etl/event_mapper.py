"""Statcast events → KBO ELO result_type 매핑."""

import logging

logger = logging.getLogger(__name__)

VALID_RESULT_TYPES = {
    'Single', 'Double', 'Triple', 'HR',
    'BB', 'IBB', 'HBP',
    'StrikeOut', 'OUT', 'SAC', 'FC', 'E', 'GIDP',
}

EVENT_MAP = {
    'single': 'Single',
    'double': 'Double',
    'triple': 'Triple',
    'home_run': 'HR',
    'walk': 'BB',
    'intentional_walk': 'IBB',
    'intent_walk': 'IBB',
    'hit_by_pitch': 'HBP',
    'strikeout': 'StrikeOut',
    'strikeout_double_play': 'StrikeOut',
    'field_out': 'OUT',
    'force_out': 'OUT',
    'triple_play': 'OUT',
    'grounded_into_double_play': 'GIDP',
    'double_play': 'GIDP',
    'sac_fly': 'SAC',
    'sac_bunt': 'SAC',
    'sac_fly_double_play': 'SAC',
    'fielders_choice': 'FC',
    'fielders_choice_out': 'FC',
    'field_error': 'E',
    'catcher_interf': 'HBP',
    'other_out': 'OUT',
    'truncated_pa': 'OUT',
}


def map_event(event: str) -> str:
    result = EVENT_MAP.get(event)
    if result is None:
        logger.warning(f"Unknown Statcast event: '{event}' → defaulting to 'OUT'")
        return 'OUT'
    return result
