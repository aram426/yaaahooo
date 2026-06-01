# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Pacman Capture-the-Flag AI competition project based on UC Berkeley's CS188 course materials, modified to run under Python 3. The goal is to implement AI agents that compete in a two-team Pacman game where agents must balance offense (eating enemy food) and defense (protecting own food).

## Core Commands

### Running the game
```bash
# Basic game with default teams
python capture.py

# Test your team as Red
python capture.py --red=myTeam

# Test your team as Blue  
python capture.py --blue=myTeam

# Test against baseline
python capture.py --red=myTeam --blue=baselineTeam

# Quiet mode (no graphics)
python capture.py -q

# Record game replay
python capture.py --record

# Replay a recorded game
python capture.py --replay=<replay-file>

# See all options
python capture.py --help
```

### Running autograder
```bash
# Run full test suite (20 games: 10 as Red, 10 as Blue)
python autograder.py

# Quiet mode (faster, no graphics)
python autograder.py -q
```

The autograder requires >= 65% win rate (13/20 wins) against `baselineTeam` to pass.

## Architecture

### Key Files and Their Roles

**Agent Implementation (modify these):**
- `myTeam.py` - Your team implementation. Must export `createTeam(firstIndex, secondIndex, isRed, first='OffensiveAgent', second='DefensiveAgent')` that returns a list of two agent instances.

**Core Game Engine (read-only, use as reference):**
- `capture.py` - Main game logic including `GameState` class with accessor methods for querying game state
- `captureAgents.py` - `CaptureAgent` base class that your agents should inherit from
- `game.py` - Core types: `Directions`, `Configuration`, `AgentState`, `Grid`
- `util.py` - Utilities including `Counter` (dictionary with default 0), `PriorityQueue`, distance functions

**Supporting Infrastructure:**
- `baselineTeam.py` - Reference implementation with `OffensiveReflexAgent` and `DefensiveReflexAgent`
- `distanceCalculator.py` - Precomputes and caches maze distances between all position pairs
- `autograder.py` - Test harness that runs 10 games per side and computes win rate
- `layouts/` - Map files (`.lay` format): `defaultCapture`, `alleyCapture`, `bloxCapture`, `crowdedCapture`, `distantCapture`

### Agent Architecture Pattern

Agents inherit from `CaptureAgent` and implement:

```python
def registerInitialState(self, gameState):
    # One-time setup (5 second allowance)
    CaptureAgent.registerInitialState(self, gameState)
    # Initialize fields like self.start, self.walls, etc.

def chooseAction(self, gameState):
    # Called each turn (1 second limit per action)
    # Return a Direction from gameState.getLegalActions(self.index)
```

**Available agent state:**
- `self.index` - Agent's index (0-3)
- `self.red` - Boolean: True if on red team
- `self.distancer` - Distance calculator with `getDistance(p1, p2)` method
- `self.observationHistory` - List of previous `GameState` objects
- `self.getTeam(gameState)` - Indices of teammates
- `self.getOpponents(gameState)` - Indices of opponents

### Game Mechanics

**Map structure:** Symmetric map split into red (left) and blue (right) territories. Agents are ghosts on their own side, become Pacman when crossing into enemy territory.

**Scoring:**
- +1 point per food pellet eaten
- +3 points for eating an opponent Pacman
- Red scores are positive, blue scores are negative

**Observation model:** 
- Full observability within 5 squares (Manhattan distance) for you or teammates
- Noisy distance readings for all agents (distance ± random noise from SONAR_NOISE_VALUES)

**Win condition:** Game ends when one team eats all but 2 opponent dots, or after 3000 total moves (750 per agent). Higher score wins; ties recorded as draws.

**Power capsules:** Eating a capsule makes enemy ghosts "scared" for 40 moves. Scared ghosts can be eaten by Pacman for 3 points.

**Timing constraints:**
- 5 seconds for `registerInitialState`
- 1 second per `chooseAction` call
- 3 warnings for timeout, then forfeit
- Single move > 3 seconds = instant forfeit

### Common Implementation Patterns

**Distance calculation:** Always use `self.distancer.getDistance(pos1, pos2)` for maze distances (cached, fast). Don't use Manhattan distance for pathfinding.

**Debugging:** Use `self.debugDraw(positions, color, clear=False)` or `CaptureAgent.displayDistributionsOverPositions(distributions)` to visualize debug info on the game map.

**State queries:**
- `gameState.getAgentState(index)` - Get `AgentState` for any agent
- `gameState.getAgentPosition(index)` - Get position tuple or None if not observable
- `gameState.getFood()` / `gameState.getFoodYouAreDefending(gameState)` - Food grids
- `gameState.getCapsules()` / `gameState.getCapsulesYouAreDefending(gameState)` - Power capsule positions
- `gameState.getLegalActions(index)` - Valid moves for an agent
- `gameState.generateSuccessor(index, action)` - Simulate taking an action

**Agent role:** `agentState.isPacman` tells if agent is currently in Pacman form (on enemy territory) vs ghost form (on own territory).

### Typical Agent Structure

The codebase uses a two-agent pattern:
1. **Offensive agent** - Focuses on crossing into enemy territory to eat food
2. **Defensive agent** - Patrols home territory to intercept invading enemy Pacmen

Common implementation in `myTeam.py`:
- Shared utilities: `aStarSearch`, `getBoundaryPositions`  
- `BaseAgent` class with common methods
- `OffensiveAgent(BaseAgent)` - Implements food collection strategy
- `DefensiveAgent(BaseAgent)` - Implements patrol and interception strategy

## Development Notes

**Do not modify:**
- Game constants (`KILL_POINTS`, `SIGHT_RANGE`, `SCARED_TIME`, etc.) - changes don't affect server
- The `createTeam` function signature in your team file - required format for the competition framework

**Performance considerations:**
- Pre-compute expensive calculations in `registerInitialState` (you have 5 seconds)
- Cache maze distances using `self.distancer` instead of recalculating
- Avoid deep search trees in `chooseAction` (1 second limit is strict)

**Common pitfalls:**
- Forgetting that observation is limited to 5 squares
- Using Euclidean/Manhattan distance instead of maze distance for pathfinding
- Ignoring scared ghost states when planning paths
- Not handling the case when an agent's position is None (unobserved)
- Timeout from excessive computation in `chooseAction`
