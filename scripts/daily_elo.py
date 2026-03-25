"""Daily ELO Pipeline CLI.

Usage:
    python -m scripts.daily_elo                        # 어제 처리
    python -m scripts.daily_elo --date 2026-04-02      # 특정 날짜
    python -m scripts.daily_elo --date 2026-04-02 --force  # 강제 재처리
    python -m scripts.daily_elo --range 2026-04-01 2026-04-03  # 범위 처리
"""

import argparse
import logging
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

# Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pipeline.daily_pipeline import run_daily_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description='Daily ELO Pipeline')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--force', action='store_true', help='Force re-processing')
    parser.add_argument('--range', nargs=2, metavar=('START', 'END'),
                        help='Date range (YYYY-MM-DD YYYY-MM-DD, inclusive)')
    return parser.parse_args()


def main():
    args = parse_args()

    if args.range:
        # Range mode: process each date in range
        start = date.fromisoformat(args.range[0])
        end = date.fromisoformat(args.range[1])
        current = start
        results = []
        while current <= end:
            result = run_daily_pipeline(target_date=current, force=args.force)
            results.append(result)
            current += timedelta(days=1)

        # Summary
        print("\n" + "=" * 60)
        print("RANGE PROCESSING SUMMARY")
        print("=" * 60)
        for r in results:
            status = r['status']
            d = r['date']
            if status == 'success':
                print(f"  {d}: {r['pa_count']} PAs, {r['active_players']} players")
            else:
                print(f"  {d}: {status}")
    else:
        # Single date mode
        target = date.fromisoformat(args.date) if args.date else None
        result = run_daily_pipeline(target_date=target, force=args.force)

        print("\n" + "=" * 60)
        print(f"Result: {result['status']}")
        if result['status'] == 'success':
            print(f"  Date: {result['date']}")
            print(f"  PAs: {result['pa_count']}")
            print(f"  Active players: {result['active_players']}")
            print(f"  New players: {result['new_players']}")
        print("=" * 60)


if __name__ == '__main__':
    main()
