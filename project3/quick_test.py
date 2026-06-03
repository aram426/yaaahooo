#!/usr/bin/env python3
"""
Quick test script to run multiple games and analyze results.
"""
import subprocess
import re
import sys

def run_game(opponent='baselineTeam'):
    """Run one game and return score"""
    try:
        result = subprocess.run(
            ['python3', 'capture.py', '-q', '--red=myTeam', f'--blue={opponent}'],
            timeout=60,
            capture_output=True,
            text=True
        )

        output = result.stdout + result.stderr

        # Parse result
        if 'Red team wins' in output:
            match = re.search(r'Red team wins by (\d+) points', output)
            score = int(match.group(1)) if match else 1
            return ('WIN', score)
        elif 'Blue team wins' in output:
            match = re.search(r'Blue team wins by (\d+) points', output)
            score = int(match.group(1)) if match else 1
            return ('LOSS', -score)
        elif 'Tie game' in output:
            return ('TIE', 0)
        else:
            return ('TIMEOUT', 0)

    except subprocess.TimeoutExpired:
        return ('TIMEOUT', 0)
    except Exception as e:
        return ('ERROR', 0)

def main():
    num_games = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    opponent = sys.argv[2] if len(sys.argv) > 2 else 'baselineTeam'

    results = []
    print(f"Running {num_games} games against {opponent}...")

    for i in range(num_games):
        print(f"\nGame {i+1}/{num_games}...", end=" ", flush=True)
        result, score = run_game(opponent)
        results.append((result, score))
        print(f"{result} ({score:+d})")

    # Summary
    wins = sum(1 for r, s in results if r == 'WIN')
    losses = sum(1 for r, s in results if r == 'LOSS')
    ties = sum(1 for r, s in results if r == 'TIE')
    timeouts = sum(1 for r, s in results if r == 'TIMEOUT')

    total_score = sum(s for r, s in results)
    avg_score = total_score / len(results) if results else 0

    print(f"\n{'='*50}")
    print(f"SUMMARY:")
    print(f"  Wins:     {wins}/{num_games} ({wins/num_games*100:.1f}%)")
    print(f"  Losses:   {losses}/{num_games}")
    print(f"  Ties:     {ties}/{num_games}")
    print(f"  Timeouts: {timeouts}/{num_games}")
    print(f"  Avg Score: {avg_score:+.1f}")
    print(f"{'='*50}")

    return wins >= num_games * 0.65  # Pass if >= 65% win rate

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
