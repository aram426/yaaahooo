# MCTS Quick Reference

빠르게 찾아볼 수 있는 핵심 코드 스니펫과 공식 모음

---

## Core Formulas

### UCB1 Score
```
UCB1(node) = Q(node) / N(node) + c * sqrt(ln(N(parent)) / N(node))

where:
  Q(node) = total reward accumulated
  N(node) = visit count
  c = exploration constant (default: 1.41)
```

### Reward Shaping (Aggressive Bias)
```
reward = base_score 
       + num_pacmen * 3.0 
       + carrying_total * 0.8 
       - (8.0 if num_pacmen == 0 else 0)
       + food_eaten * 1.5
```

### Manhattan Distance
```python
def manhattan(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
```

---

## Essential GameState API

```python
# Agent state
state.getAgentState(index)               # AgentState object
state.getAgentPosition(index)            # (x, y) or None
agentState.isPacman                      # True if in enemy territory
agentState.numCarrying                   # Food carried but not scored
agentState.scaredTimer                   # Scared time remaining

# Food & capsules
self.getFood(state).asList()             # List of food positions we can eat
self.getFoodYouAreDefending(state)       # Food we're defending
self.getCapsules(state)                  # Power capsules we can eat
self.getCapsulesYouAreDefending(state)   # Capsules we're defending

# Actions & successors
state.getLegalActions(index)             # [Directions.NORTH, ...]
state.generateSuccessor(index, action)   # New GameState after action

# Team & opponents
self.getTeam(state)                      # [0, 2] or [1, 3]
self.getOpponents(state)                 # [1, 3] or [0, 2]

# Score & time
state.getScore()                         # Current score (red perspective)
state.data.timeleft                      # Remaining moves
state.isOver()                           # True if game ended
```

---

## MCTS Structure Template

```python
class MCTSNode:
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action  # (action0, action2) joint action
        self.children = []
        self.visits = 0
        self.total_reward = 0.0

class MCTSAgent(CaptureAgent):
    def registerInitialState(self, gameState):
        CaptureAgent.registerInitialState(self, gameState)
        self.tree_root = None
        team = self.getTeam(gameState)
        self.teammate_index = [i for i in team if i != self.index][0]
    
    def chooseAction(self, gameState):
        # 1. Initialize/reuse tree
        if self.tree_root is None:
            self.tree_root = MCTSNode(gameState)
        
        # 2. MCTS loop (0.8s budget)
        start_time = time.time()
        num_rollouts = 0
        while time.time() - start_time < 0.8:
            node = self._select(self.tree_root)
            if not node.is_terminal() and node.visits > 0:
                node = self._expand(node)
            reward = self._simulate(node.state)
            self._backpropagate(node, reward)
            num_rollouts += 1
        
        # 3. Select best child
        best_child = max(self.tree_root.children, key=lambda c: c.visits)
        my_action = self._extract_my_action(best_child.action)
        return my_action
```

---

## Rollout Policy Template

```python
def _rollout_policy(self, state, agent_idx):
    """Priority-based heuristic"""
    myPos = state.getAgentPosition(agent_idx)
    myState = state.getAgentState(agent_idx)
    
    # 1. Emergency: ghost within 3
    if myState.isPacman:
        ghosts = self._get_enemy_ghosts(state, agent_idx)
        if ghosts and min(manhattan(myPos, g.getPosition()) for g in ghosts) <= 3:
            return self._move_away(myPos, closest_ghost_pos, state, agent_idx)
    
    # 2. Chase invader (if ghost)
    if not myState.isPacman:
        invaders = self._get_invaders(state, agent_idx)
        if invaders:
            return self._move_towards(myPos, closest_invader_pos, state, agent_idx)
    
    # 3. Go to food (if pacman)
    if myState.isPacman:
        food = self.getFood(state).asList()
        if food:
            return self._move_towards(myPos, closest_food, state, agent_idx)
    
    # 4. Return if carrying 8+
    if myState.numCarrying >= 8:
        return self._move_towards(myPos, closest_boundary, state, agent_idx)
    
    # 5. Default: enter enemy territory
    return self._move_towards(myPos, closest_boundary, state, agent_idx)
```

---

## Helper Functions

### Move Towards
```python
def _move_towards(self, fromPos, toPos, state, agent_idx):
    dx = toPos[0] - fromPos[0]
    dy = toPos[1] - fromPos[1]
    
    if abs(dx) > abs(dy):
        primary = Directions.EAST if dx > 0 else Directions.WEST
    else:
        primary = Directions.NORTH if dy > 0 else Directions.SOUTH
    
    if primary in state.getLegalActions(agent_idx):
        return primary
    
    # Try secondary direction
    if abs(dx) > abs(dy):
        secondary = Directions.NORTH if dy > 0 else Directions.SOUTH
    else:
        secondary = Directions.EAST if dx > 0 else Directions.WEST
    
    if secondary in state.getLegalActions(agent_idx):
        return secondary
    
    # Fallback: any legal except STOP
    legal = [a for a in state.getLegalActions(agent_idx) if a != Directions.STOP]
    return random.choice(legal) if legal else Directions.STOP
```

### Get Enemy Ghosts
```python
def _get_enemy_ghosts(self, state, agent_idx):
    """Enemy agents that are ghosts (not scared)"""
    opponents = self.getOpponents(state)
    ghosts = []
    for opp in opponents:
        opp_state = state.getAgentState(opp)
        if not opp_state.isPacman and opp_state.getPosition() is not None:
            if opp_state.scaredTimer <= 0:
                ghosts.append(opp_state)
    return ghosts
```

### Get Invaders
```python
def _get_invaders(self, state, agent_idx):
    """Enemy agents in our territory"""
    opponents = self.getOpponents(state)
    invaders = []
    for opp in opponents:
        opp_state = state.getAgentState(opp)
        if opp_state.isPacman and opp_state.getPosition() is not None:
            invaders.append(opp_state)
    return invaders
```

### Get Boundary Positions
```python
def _get_boundary(self, state, agent_idx):
    """Boundary positions between territories"""
    walls = state.getWalls()
    width, height = walls.width, walls.height
    mid_x = width // 2
    
    # Red team: x = mid_x - 1, Blue team: x = mid_x
    if agent_idx in self.getTeam(state):
        if self.red:
            x = mid_x - 1
        else:
            x = mid_x
    
    boundary = []
    for y in range(1, height - 1):
        if not walls[x][y]:
            boundary.append((x, y))
    
    return boundary
```

---

## Debugging Snippets

### Print MCTS Stats
```python
def chooseAction(self, gameState):
    # ... MCTS loop ...
    
    print(f"Agent {self.index}: {num_rollouts} rollouts in {elapsed:.3f}s")
    print(f"Root visits: {self.tree_root.visits}, children: {len(self.tree_root.children)}")
    
    # Print top 3 actions
    top_children = sorted(self.tree_root.children, key=lambda c: c.visits, reverse=True)[:3]
    for i, child in enumerate(top_children):
        avg_reward = child.total_reward / child.visits if child.visits > 0 else 0
        print(f"  {i+1}. Action {child.action}: visits={child.visits}, avg_reward={avg_reward:.2f}")
```

### Visualize Tree Depth
```python
def tree_depth(node):
    if not node.children:
        return 0
    return 1 + max(tree_depth(child) for child in node.children)

print(f"Tree depth: {tree_depth(self.tree_root)}")
```

### Profile Rollout Speed
```python
# Before MCTS loop
rollout_times = []

# Inside loop, after simulate
rollout_start = time.time()
reward = self._simulate(node.state)
rollout_times.append(time.time() - rollout_start)

# After loop
avg_rollout = sum(rollout_times) / len(rollout_times)
max_rollout = max(rollout_times)
print(f"Rollout: avg={avg_rollout*1000:.2f}ms, max={max_rollout*1000:.2f}ms")
```

---

## Common Bugs & Fixes

### Bug: Agent timeout
**Fix**: Reduce time_budget to 0.5s or reduce rollout depth to 5

### Bug: Agent moves into wall
**Fix**: Check `state.getLegalActions()` before returning action

### Bug: "list index out of range"
**Fix**: Check `if node.children:` before `max(node.children, ...)`

### Bug: Agent stands still
**Fix**: Filter out `Directions.STOP` from rollout policy

### Bug: Reward always 0
**Fix**: Check team perspective in `_evaluate_state` (red vs blue)

### Bug: Opponent actions not applied
**Fix**: Apply all 4 agents' actions in order in `_simulate`

---

## Performance Checklist

- [ ] Time budget < 0.9s (leave 0.1s margin)
- [ ] Rollout depth <= 10
- [ ] No `getMazeDistance` in rollout
- [ ] No `print` in tight loops (slows down)
- [ ] Legal actions checked before returning
- [ ] Tree reuse implemented (optional but +30% speedup)
- [ ] Exploration constant tuned (try 1.0-2.0 range)

---

## Useful Commands

```bash
# Single game with graphics
python3 capture.py -r myTeam

# 10 games quiet mode
python3 capture.py -r myTeam -q -n 10

# Different layout
python3 capture.py -r myTeam -l alleyCapture -q

# As Blue team
python3 capture.py -b myTeam -q

# Full autograder
python3 autograder.py -q

# Profile slow functions
python3 -m cProfile -o profile.stats capture.py -r myTeam -q -n 1
python3 -c "import pstats; p=pstats.Stats('profile.stats'); p.sort_stats('cumtime'); p.print_stats(20)"
```

---

## Reference: MCTS Algorithm Pseudocode

```
function MCTS(root_state, time_budget):
    root = Node(root_state)
    
    while time_remaining():
        # 1. Selection: traverse tree using UCB1
        node = root
        while node.fully_expanded() and not node.terminal():
            node = best_child(node, UCB1)
        
        # 2. Expansion: add one child
        if not node.terminal():
            node = expand(node)
        
        # 3. Simulation: rollout to depth limit
        reward = simulate(node.state, depth=10)
        
        # 4. Backpropagation: update ancestors
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            node = node.parent
    
    # Return action of most-visited child
    return argmax(root.children, key=lambda c: c.visits)
```

---

## Tournament Optimization Tips

1. **Reduce print statements**: 매 turn마다 print하면 느려짐. 10턴마다 한 번만.
2. **Cache boundary positions**: `registerInitialState`에서 계산, 매 turn 재사용.
3. **Vectorize if possible**: NumPy array operations는 loop보다 빠름.
4. **Prune bad actions early**: `Directions.STOP` 같은 명백히 나쁜 action은 explore 안 함.
5. **Profile before optimizing**: 추측하지 말고 cProfile로 측정.

---

## Further Reading

- UC Berkeley CS188 MCTS lecture: https://ai.berkeley.edu
- "A Survey of Monte Carlo Tree Search Methods" (Browne et al., 2012)
- AlphaGo paper (Silver et al., 2016) - MCTS + neural nets
- Past Pacman contest winners: https://ai.berkeley.edu/contest.html
