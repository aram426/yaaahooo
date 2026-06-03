#!/usr/bin/env python3
"""
Detailed game analysis script
"""
import subprocess
import re

def run_detailed_game():
    """Run one game with detailed output"""
    result = subprocess.run(
        ['python3', 'capture.py', '-q', '--red=myTeam', '--blue=otherTeam'],
        capture_output=True,
        text=True,
        timeout=90
    )

    output = result.stdout + result.stderr

    # Parse results
    analysis = {
        'winner': None,
        'score': 0,
        'red_foods_eaten': 0,
        'blue_foods_eaten': 0,
        'red_deaths': 0,
        'blue_deaths': 0,
        'game_length': 0
    }

    # Winner
    if 'Red team wins' in output:
        match = re.search(r'Red team wins by (\d+)', output)
        analysis['winner'] = 'RED'
        analysis['score'] = int(match.group(1)) if match else 0
    elif 'Blue team wins' in output:
        match = re.search(r'Blue team wins by (\d+)', output)
        analysis['winner'] = 'BLUE'
        analysis['score'] = -int(match.group(1)) if match else 0
    else:
        analysis['winner'] = 'TIE'

    # Count events
    lines = output.split('\n')
    for line in lines:
        if 'Red agent' in line and 'Pacman' in line and 'eaten' in line:
            analysis['red_deaths'] += 1
        if 'Blue agent' in line and 'Pacman' in line and 'eaten' in line:
            analysis['blue_deaths'] += 1

    # Game length
    if 'Time is up' in output:
        analysis['game_length'] = 'TIMEOUT'

    return analysis

def main():
    print("Analyzing otherTeam gameplay...\n")

    results = []
    for i in range(5):
        print(f"Game {i+1}/5...", end=" ", flush=True)
        try:
            analysis = run_detailed_game()
            results.append(analysis)
            print(f"{analysis['winner']} ({analysis['score']:+d}), Deaths: Red={analysis['red_deaths']}, Blue={analysis['blue_deaths']}")
        except Exception as e:
            print(f"ERROR: {e}")

    # Summary
    print("\n" + "="*60)
    wins = sum(1 for r in results if r['winner'] == 'RED')
    avg_score = sum(r['score'] for r in results) / len(results) if results else 0
    avg_red_deaths = sum(r['red_deaths'] for r in results) / len(results) if results else 0
    avg_blue_deaths = sum(r['blue_deaths'] for r in results) / len(results) if results else 0

    print(f"Win Rate: {wins}/5 ({wins/5*100:.1f}%)")
    print(f"Avg Score: {avg_score:+.1f}")
    print(f"Avg Red Deaths: {avg_red_deaths:.1f}")
    print(f"Avg Blue Deaths: {avg_blue_deaths:.1f}")

    # Key insights
    print("\n=== KEY INSIGHTS ===")
    if avg_red_deaths > avg_blue_deaths * 2:
        print("⚠️ RED is dying TOO OFTEN - need better escape/safety")
    if abs(avg_score) > 50:
        print("⚠️ Large score difference - fundamental strategy issue")
    if avg_blue_deaths < 1:
        print("⚠️ BLUE rarely dies - RED not aggressive enough")

if __name__ == '__main__':
    main()
