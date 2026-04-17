"""Statcast events → KBO ELO result_type 매핑."""

import logging

logger = logging.getLogger(__name__)

VALID_RESULT_TYPES = {
    'Single', 'Double', 'Triple', 'HR',
    'BB', 'IBB', 'HBP',
    'StrikeOut', 'OUT', 'SAC', 'FC', 'E', 'GIDP',
    'POPUP', 'GROUNDOUT',
    'SB', 'CS', 'PKO',
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
    # Baserunning events — runner_id must be extracted separately
    'stolen_base_2b': 'SB',
    'stolen_base_3b': 'SB',
    'stolen_base_home': 'SB',
    'caught_stealing_2b': 'CS',
    'caught_stealing_3b': 'CS',
    'caught_stealing_home': 'CS',
    'pickoff_caught_stealing_2b': 'PKO',
    'pickoff_caught_stealing_3b': 'PKO',
    'pickoff_caught_stealing_home': 'PKO',
    'pickoff_1b': 'PKO',
    'pickoff_2b': 'PKO',
    'pickoff_3b': 'PKO',
}


def map_event(event: str) -> str:
    result = EVENT_MAP.get(event)
    if result is None:
        logger.warning(f"Unknown Statcast event: '{event}' → defaulting to 'OUT'")
        return 'OUT'
    return result
