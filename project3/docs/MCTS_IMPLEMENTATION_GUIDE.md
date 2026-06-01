# MCTS Implementation Guide for Pacman Competition

**목표**: Championship-tier 성능을 위한 Joint Action MCTS 구현  
**예상 소요 시간**: 5-7일  
**난이도**: High (하지만 단계별로 나누면 관리 가능)

---

## Why MCTS?

현재 구현(100% 승률)의 문제:
- ❌ **너무 수비적**: CARRY_LIMIT=5, 경계선 camping
- ❌ **예측 가능**: 항상 같은 패턴
- ❌ **유연성 부족**: 1공-1수 고정

MCTS가 해결하는 방법:
- ✅ **Simulation-driven**: "2명 공격" vs "1명 수비"를 실제로 시뮬레이션해서 더 높은 점수를 얻는 쪽 선택
- ✅ **Adaptive**: 매 턴 상대 행동을 보고 재계산 → 상대 전략에 counter
- ✅ **Aggressive by design**: Reward shaping으로 offensive action에 bonus

---

## Implementation Roadmap

### Phase 1: Core MCTS Framework (Day 1-2)

**목표**: MCTS가 돌아가게 만들기 (성능은 나중 문제)

#### Step 1.1: Node Class 구현

```python
class MCTSNode:
    def __init__(self, state, parent=None, action=None):
        self.state = state          # GameState
        self.parent = parent        # MCTSNode or None
        self.action = action        # (action0, action2) joint action
        self.children = []          # List[MCTSNode]
        self.visits = 0             # int
        self.total_reward = 0.0     # float
    
    def is_fully_expanded(self):
        """모든 legal joint actions에 대해 child가 있는가?"""
        # TODO: 구현 필요
        pass
    
    def is_terminal(self):
        """게임이 끝났는가?"""
        return self.state.isOver()
    
    def ucb_score(self, exploration_constant=1.41):
        """UCB1 score 계산"""
        if self.visits == 0:
            return float('inf')  # unvisited → prioritize
        
        exploit = self.total_reward / self.visits
        explore = exploration_constant * (math.log(self.parent.visits) / self.visits) ** 0.5
        return exploit + explore
```

#### Step 1.2: MCTS Main Loop

```python
class MCTSAgent(CaptureAgent):
    def __init__(self, index):
        super().__init__(index)
        self.tree_root = None
        self.teammate_index = None  # 초기화 필요
    
    def registerInitialState(self, gameState):
        CaptureAgent.registerInitialState(self, gameState)
        # 팀원 index 찾기
        team = self.getTeam(gameState)
        self.teammate_index = [i for i in team if i != self.index][0]
    
    def chooseAction(self, gameState):
        """Main entry point"""
        import time
        start_time = time.time()
        
        # Tree reuse (optional for Phase 1, 나중에 추가)
        if self.tree_root is None:
            self.tree_root = MCTSNode(gameState)
        
        # MCTS search
        num_rollouts = 0
        time_budget = 0.8  # 1초 중 0.8초만 사용 (여유분 0.2초)
        
        while time.time() - start_time < time_budget:
            # 1. Selection
            node = self._select(self.tree_root)
            
            # 2. Expansion
            if not node.is_terminal() and node.visits > 0:
                node = self._expand(node)
            
            # 3. Simulation
            reward = self._simulate(node.state)
            
            # 4. Backpropagation
            self._backpropagate(node, reward)
            
            num_rollouts += 1
        
        # Select best action
        best_child = max(self.tree_root.children, key=lambda c: c.visits)
        joint_action = best_child.action
        
        # Extract my action from joint action
        my_action = joint_action[0] if self.index == min(self.getTeam(gameState)) else joint_action[1]
        
        elapsed = time.time() - start_time
        print(f"Agent {self.index}: {num_rollouts} rollouts in {elapsed:.3f}s")
        
        return my_action
    
    def _select(self, node):
        """UCB1 기반 selection"""
        while not node.is_terminal() and node.is_fully_expanded():
            node = max(node.children, key=lambda c: c.ucb_score())
        return node
    
    def _expand(self, node):
        """Add one child"""
        # Get legal joint actions
        actions0 = node.state.getLegalActions(min(self.getTeam(node.state)))
        actions2 = node.state.getLegalActions(max(self.getTeam(node.state)))
        
        # Find unexpanded action
        existing_actions = [child.action for child in node.children]
        for a0 in actions0:
            for a2 in actions2:
                if (a0, a2) not in existing_actions:
                    # Create child
                    successor = self._apply_joint_action(node.state, a0, a2)
                    child = MCTSNode(successor, parent=node, action=(a0, a2))
                    node.children.append(child)
                    return child
        
        return node  # already fully expanded
    
    def _simulate(self, state):
        """Random rollout (placeholder)"""
        current_state = state
        depth = 10  # 10-step lookahead
        
        for _ in range(depth):
            if current_state.isOver():
                break
            
            # Random actions for all 4 agents
            actions = []
            for i in range(4):
                legal = current_state.getLegalActions(i)
                actions.append(random.choice(legal) if legal else Directions.STOP)
            
            # Apply actions sequentially
            for i, action in enumerate(actions):
                current_state = current_state.generateSuccessor(i, action)
        
        # Evaluate final state
        return current_state.getScore()
    
    def _backpropagate(self, node, reward):
        """Update all ancestors"""
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            node = node.parent
    
    def _apply_joint_action(self, state, action0, action2):
        """Apply actions for both our agents"""
        team = self.getTeam(state)
        agent0 = min(team)
        agent2 = max(team)
        
        # Apply in order
        state = state.generateSuccessor(agent0, action0)
        state = state.generateSuccessor(agent2, action2)
        
        return state
```

**Phase 1 완료 조건**:
- [ ] `python3 capture.py -r myTeam -q` 실행되고 timeout 안 남
- [ ] "X rollouts in Y seconds" 메시지 출력됨
- [ ] Baseline 상대로 최소 1 game 완료 (이기든 지든 상관없음)

**예상 문제**:
- `_apply_joint_action`에서 opponent turn 건너뛰기 문제 → 4명 순서대로 적용해야 함
- Timeout → time_budget를 0.5로 줄여보기

---

### Phase 2: Fast Rollout Policy (Day 3-4)

**목표**: Random rollout → Smart heuristic rollout. 속도 0.5-1ms/rollout 달성.

#### Step 2.1: Lightweight Heuristic 구현

```python
def _simulate(self, state):
    """Smart rollout policy"""
    current_state = state
    depth = 10
    
    for step in range(depth):
        if current_state.isOver():
            break
        
        actions = []
        for agent_idx in range(4):
            if agent_idx in self.getTeam(current_state):
                # Our agent: smart heuristic
                action = self._rollout_policy(current_state, agent_idx)
            else:
                # Opponent: chase our pacmen
                action = self._opponent_policy(current_state, agent_idx)
            actions.append(action)
        
        # Apply all actions
        for i, action in enumerate(actions):
            current_state = current_state.generateSuccessor(i, action)
    
    return self._evaluate_state(current_state)

def _rollout_policy(self, state, agent_idx):
    """Fast heuristic for our agents"""
    myPos = state.getAgentPosition(agent_idx)
    myState = state.getAgentState(agent_idx)
    
    # Priority 1: Emergency escape
    ghosts = self._get_enemy_ghosts(state, agent_idx)
    if myState.isPacman and ghosts:
        closest_ghost_pos = min([g.getPosition() for g in ghosts], 
                                key=lambda p: self._manhattan(myPos, p))
        if self._manhattan(myPos, closest_ghost_pos) <= 3:
            return self._move_away(myPos, closest_ghost_pos, state, agent_idx)
    
    # Priority 2: Chase invader (if we're ghost)
    if not myState.isPacman:
        invaders = self._get_invaders(state, agent_idx)
        if invaders:
            closest_inv = min([inv.getPosition() for inv in invaders],
                            key=lambda p: self._manhattan(myPos, p))
            return self._move_towards(myPos, closest_inv, state, agent_idx)
    
    # Priority 3: Go to food (if we're pacman)
    if myState.isPacman:
        food = self.getFood(state).asList()
        if food:
            closest_food = min(food, key=lambda f: self._manhattan(myPos, f))
            return self._move_towards(myPos, closest_food, state, agent_idx)
    
    # Priority 4: Return home if carrying 8+
    if myState.isPacman and myState.numCarrying >= 8:
        boundary = self._get_boundary(state, agent_idx)
        closest_boundary = min(boundary, key=lambda b: self._manhattan(myPos, b))
        return self._move_towards(myPos, closest_boundary, state, agent_idx)
    
    # Default: move towards enemy territory
    boundary = self._get_boundary(state, agent_idx)
    closest_boundary = min(boundary, key=lambda b: self._manhattan(myPos, b))
    return self._move_towards(myPos, closest_boundary, state, agent_idx)

def _move_towards(self, fromPos, toPos, state, agent_idx):
    """Return action that moves towards target"""
    dx = toPos[0] - fromPos[0]
    dy = toPos[1] - fromPos[1]
    
    # Try primary direction
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
    
    # Fallback: any legal action except STOP
    legal = [a for a in state.getLegalActions(agent_idx) if a != Directions.STOP]
    return random.choice(legal) if legal else Directions.STOP

def _move_away(self, fromPos, threatPos, state, agent_idx):
    """Return action that moves away from threat"""
    # Opposite of _move_towards
    dx = fromPos[0] - threatPos[0]  # note: reversed
    dy = fromPos[1] - threatPos[1]
    
    if abs(dx) > abs(dy):
        primary = Directions.EAST if dx > 0 else Directions.WEST
    else:
        primary = Directions.NORTH if dy > 0 else Directions.SOUTH
    
    if primary in state.getLegalActions(agent_idx):
        return primary
    
    # Fallback
    legal = [a for a in state.getLegalActions(agent_idx) if a != Directions.STOP]
    return random.choice(legal) if legal else Directions.STOP

def _manhattan(self, pos1, pos2):
    """Manhattan distance (fast, O(1))"""
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
```

#### Step 2.2: 속도 측정

```python
def chooseAction(self, gameState):
    start_time = time.time()
    
    # ... MCTS loop ...
    
    elapsed = time.time() - start_time
    avg_rollout_time = elapsed / num_rollouts if num_rollouts > 0 else 0
    print(f"Agent {self.index}: {num_rollouts} rollouts, avg={avg_rollout_time*1000:.2f}ms/rollout")
    
    return my_action
```

**Phase 2 완료 조건**:
- [ ] Rollout이 random이 아니라 heuristic 따름 (food 방향으로 움직임)
- [ ] 평균 rollout time < 2ms (목표 1ms)
- [ ] Baseline 상대로 50%+ 승률

**속도 최적화 팁**:
- `getMazeDistance` 절대 쓰지 말기 (너무 느림)
- `manhattanDistance` 대신 직접 계산 (function call overhead 제거)
- State copy 최소화: `generateSuccessor` 여러 번 호출하면 느림

---

### Phase 3: Aggressive Bias (Day 5)

**목표**: MCTS가 offensive action을 선호하도록 만들기

#### Step 3.1: Reward Shaping

```python
def _evaluate_state(self, state):
    """Custom reward function with aggressive bias"""
    # Base score
    score = state.getScore()
    
    # Adjust for team perspective
    if not self.red:
        score = -score
    
    # Bonus: agents in enemy territory
    team = self.getTeam(state)
    num_pacmen = sum(1 for i in team if state.getAgentState(i).isPacman)
    score += num_pacmen * 3.0  # +3 per pacman
    
    # Bonus: carrying food
    carrying_total = sum(state.getAgentState(i).numCarrying for i in team)
    score += carrying_total * 0.8  # +0.8 per food carried
    
    # Penalty: no one attacking (both defensive)
    if num_pacmen == 0:
        score -= 8.0  # -8 penalty
    
    # Bonus: food eaten
    food_left = len(self.getFood(state).asList())
    initial_food = 60  # or track this
    score += (initial_food - food_left) * 1.5  # +1.5 per food eaten
    
    return score
```

#### Step 3.2: Progressive Widening

```python
def _expand(self, node):
    """Expand children, prioritizing offensive actions"""
    actions0 = node.state.getLegalActions(min(self.getTeam(node.state)))
    actions2 = node.state.getLegalActions(max(self.getTeam(node.state)))
    
    # Score joint actions by offensiveness
    scored_actions = []
    for a0 in actions0:
        for a2 in actions2:
            succ = self._apply_joint_action(node.state, a0, a2)
            # Offensiveness = num_pacmen + carrying_total
            team = self.getTeam(succ)
            num_pacmen = sum(1 for i in team if succ.getAgentState(i).isPacman)
            carrying = sum(succ.getAgentState(i).numCarrying for i in team)
            offensiveness = num_pacmen * 2 + carrying
            scored_actions.append((a0, a2, offensiveness))
    
    # Sort by offensiveness (high to low)
    scored_actions.sort(key=lambda x: x[2], reverse=True)
    
    # Find first unexpanded action
    existing_actions = [child.action for child in node.children]
    for a0, a2, _ in scored_actions:
        if (a0, a2) not in existing_actions:
            successor = self._apply_joint_action(node.state, a0, a2)
            child = MCTSNode(successor, parent=node, action=(a0, a2))
            node.children.append(child)
            return child
    
    return node  # fully expanded
```

**Phase 3 완료 조건**:
- [ ] 게임 시작 후 첫 50 moves에서 평균 1.5명+ pacmen (aggressive)
- [ ] Baseline 상대로 70%+ 승률
- [ ] 자동으로 2-0 공격 → 침입 시 1-1로 전환하는 behavior 관찰됨

**Debugging tip**: `_evaluate_state` 값을 print해서 offensive action이 더 높은 score 받는지 확인

---

### Phase 4: Optimization (Day 6)

**목표**: 800-1000 rollouts/0.8s 달성

#### Step 4.1: Tree Reuse

```python
def chooseAction(self, gameState):
    # Tree reuse
    if self.tree_root is not None:
        # Find matching child
        for child in self.tree_root.children:
            if self._states_match(child.state, gameState):
                self.tree_root = child  # shift root
                self.tree_root.parent = None  # detach from old tree
                break
        else:
            # No match, rebuild
            self.tree_root = MCTSNode(gameState)
    else:
        self.tree_root = MCTSNode(gameState)
    
    # ... MCTS loop ...

def _states_match(self, state1, state2):
    """Approximate state matching"""
    # Compare key features
    return (state1.getScore() == state2.getScore() and
            self._get_carrying(state1) == self._get_carrying(state2))

def _get_carrying(self, state):
    """Total food carried by our team"""
    team = self.getTeam(state)
    return sum(state.getAgentState(i).numCarrying for i in team)
```

#### Step 4.2: Profiling

```bash
# Run with profiling
python3 -m cProfile -o profile.stats capture.py -r myTeam -q -n 1

# Analyze
python3 -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumtime'); p.print_stats(20)"
```

**느린 함수 찾으면**:
- `getLegalActions` 많이 호출 → cache 고려
- `generateSuccessor` 느림 → 호출 횟수 줄이기
- `getFood().asList()` 느림 → 한 번만 호출하고 재사용

**Phase 4 완료 조건**:
- [ ] 700+ rollouts/0.8s (800+ stretch goal)
- [ ] Baseline 상대로 80%+ 승률
- [ ] Average computation time < 0.1s

---

### Phase 5: Testing & Edge Cases (Day 7)

#### Test Suite

```bash
# 1. Autograder (20 games)
python3 autograder.py -q

# 2. All layouts
python3 capture.py -r myTeam -l alleyCapture -q -n 5
python3 capture.py -r myTeam -l bloxCapture -q -n 5
python3 capture.py -r myTeam -l crowdedCapture -q -n 5
python3 capture.py -r myTeam -l distantCapture -q -n 5

# 3. As Blue team
python3 capture.py -b myTeam -q -n 5

# 4. Time stress test
python3 capture.py -r myTeam -q -n 10  # check for any timeouts
```

#### Edge Cases to Handle

```python
def chooseAction(self, gameState):
    try:
        # Normal MCTS logic
        # ...
    except Exception as e:
        print(f"MCTS failed: {e}, falling back to safe action")
        return self._safe_fallback(gameState)

def _safe_fallback(self, gameState):
    """Fallback if MCTS fails"""
    legal = gameState.getLegalActions(self.index)
    legal = [a for a in legal if a != Directions.STOP]
    return random.choice(legal) if legal else Directions.STOP
```

**Phase 5 완료 조건**:
- [ ] Autograder 95%+ 승률
- [ ] 모든 layouts에서 timeout 없음
- [ ] Blue/Red 양쪽 모두 80%+ 승률
- [ ] 10 consecutive games에서 0 crashes

---

## Common Pitfalls & Solutions

### Pitfall 1: Timeout
**증상**: "Time is up" 또는 forfeit
**원인**: Rollout이 너무 느림
**해결책**:
- Rollout depth 10 → 5로 줄이기
- `getMazeDistance` 제거
- Time budget 0.8 → 0.6으로 줄이기

### Pitfall 2: MCTS가 이상하게 행동
**증상**: Agent가 벽으로 가거나 제자리에서 멈춤
**원인**: Reward function 문제
**해결책**:
- `_evaluate_state` 값 print해서 확인
- Offensive action이 낮은 score 받으면 bonus 키우기

### Pitfall 3: Coordination 실패
**증상**: 둘 다 공격 또는 둘 다 수비
**원인**: Joint action space에서 coordination 안 배움
**해결책**:
- Reward shaping에 "invader 있을 때 최소 1명 수비" bonus 추가
- 이미 MCTS가 simulation으로 학습하므로 크게 문제 안 됨

### Pitfall 4: Baseline보다 못함
**증상**: 승률 50% 미만
**원인**: Rollout policy가 너무 random
**해결책**:
- Phase 2 rollout heuristic 재확인
- Food 방향으로 움직이는지 확인

---

## Performance Targets by Phase

| Phase | Target Win Rate | Rollouts/0.8s | Avg Compute Time |
|-------|----------------|---------------|------------------|
| 1     | 30-50%         | 100-200       | < 0.5s           |
| 2     | 50-70%         | 300-500       | < 0.2s           |
| 3     | 70-85%         | 400-600       | < 0.15s          |
| 4     | 80-95%         | 600-1000      | < 0.1s           |
| 5     | 95%+           | 800-1000      | < 0.08s          |

---

## Next Steps After Implementation

1. **Hyperparameter tuning**:
   - Exploration constant (1.41 → 1.2-1.6 시도)
   - Reward weights (num_pacmen bonus, carrying bonus)
   - Rollout depth (10 → 8 or 12)

2. **Advanced features (optional)**:
   - Transposition table (같은 state 중복 방지)
   - RAVE (Rapid Action Value Estimation)
   - Belief state for opponent positions (noisy distance handling)

3. **Tournament prep**:
   - 다양한 layouts에서 stress test
   - Self-play (myTeam vs myTeam) 10 games
   - Compute time 최소화 (타이브레이커 유리)

---

## FAQ

**Q: MCTS가 Q-Learning보다 정말 나은가요?**  
A: 토너먼트 맥락에서는 yes. Q-Learning은 baseline 상대로만 학습하므로 다른 전략 대응 못함. MCTS는 매 게임 adaptive.

**Q: 1주일 안에 완성 가능한가요?**  
A: Yes. Phase 1-2 (framework + rollout)에 3-4일, Phase 3-4 (optimization)에 2-3일. 하루 3-4시간 투자 가정.

**Q: 중간에 막히면 어떻게 하죠?**  
A: Phase 1 완성 후 baseline 상대로 1 game이라도 돌려보세요. 안 돌아가면 `_apply_joint_action` 버그일 확률 90%. 천천히 디버깅.

**Q: 100% 승률에서 95%로 떨어지는 게 정상인가요?**  
A: Yes. Aggressive해지면 위험 감수 → 가끔 짐. 하지만 토너먼트에서 똑똑한 상대는 오히려 더 잘 이김.

**Q: Baseline 말고 다른 팀과 테스트하려면?**  
A: `baselineTeam.py` 복사해서 수정하거나, 온라인에서 Berkeley contest 우승 코드 다운로드 (공개된 것들 있음).
