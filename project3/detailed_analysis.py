#!/usr/bin/env python3
"""
Detailed analysis of game dynamics
"""
import subprocess
import re

def analyze_game():
    result = subprocess.run(
        ['python3', 'capture.py', '-q', '--red=myTeam', '--blue=otherTeam'],
        capture_output=True,
        text=True,
        timeout=90
    )

    output = result.stdout + result.stderr
    lines = output.split('\n')

    # Count food eaten by each team
    red_food_eaten = 0
    blue_food_eaten = 0

    # Track score progression
    scores = []

    for line in lines:
        # Parse score updates
        if 'Score' in line and ':' in line:
            # Try to extract score
            match = re.search(r'Score:\s*([-+]?\d+)', line)
            if match:
                scores.append(int(match.group(1)))

        # Count deaths
        if 'Red agent' in line and 'returned' in line:
            # Red died, lost food
            pass
        if 'Blue agent' in line and 'returned' in line:
            # Blue died, lost food
            pass

    # Final result
    winner = None
    final_score = 0

    if 'Red team wins' in output:
        match = re.search(r'Red team wins by (\d+)', output)
        winner = 'RED'
        final_score = int(match.group(1)) if match else 0
    elif 'Blue team wins' in output:
        match = re.search(r'Blue team wins by (\d+)', output)
        winner = 'BLUE'
        final_score = -int(match.group(1)) if match else 0
    elif 'Tie game' in output:
        winner = 'TIE'
        final_score = 0

    # Count food remaining
    red_food_remaining = output.count('Red food')
    blue_food_remaining = output.count('Blue food')

    print(f"Winner: {winner}, Score: {final_score:+d}")
    print(f"Score progression: {scores[:10] if len(scores) > 10 else scores}")
    print(f"Total score changes: {len(scores)}")

    # Check if game is too defensive
    if len(scores) < 5:
        print("⚠️ Very few score changes - game too defensive!")

    print("\n" + "="*60)

for i in range(3):
    print(f"\n=== Game {i+1} ===")
    try:
        analyze_game()
    except Exception as e:
        print(f"Error: {e}")
