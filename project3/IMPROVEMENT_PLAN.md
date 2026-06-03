# Phase 2 개선 계획

## 현재 Phase 2 구조 분석

### 강점:
1. **Joint Action MCTS** - 두 에이전트가 협력하여 의사결정
2. **Simple Evaluation** - Score만 사용 (빠르고 효과적)
3. **Fast Rollout Policy** - 우선순위 기반 휴리스틱
4. **0.8초 Time Budget** - 충분한 탐색 시간

### 잠재적 약점 (로그 분석 대기 중):

#### 1. **평가 함수가 너무 단순함** (Line 239-251)
```python
def _evaluate_state(self, state):
    score = state.getScore()
    if not self.red:
        score = -score
    return score
```

**문제점:**
- Score만 고려 → 중간 상태의 뉘앙스를 놓침
- 음식 수집 중이지만 아직 점수에 반영 안된 상태 평가 불가
- 위험한 상황(적 근처)과 안전한 상황 구분 안됨

**개선 방안:**
```python
def _evaluate_state(self, state):
    score = state.getScore() * 100  # 실제 점수가 가장 중요
    
    # 보조 휴리스틱 추가
    for agent_idx in self.getTeam(state):
        agent_state = state.getAgentState(agent_idx)
        pos = state.getAgentPosition(agent_idx)
        
        if pos:
            # 음식 운반 중 = 잠재적 점수
            if agent_state.isPacman:
                score += agent_state.numCarrying * 10
                
                # 위험 페널티 (적 근처에서 음식 들고 있으면)
                enemies = self._get_enemy_ghosts(state, agent_idx)
                if enemies:
                    closest_dist = min(self._manhattan(pos, e.getPosition()) for e in enemies)
                    if closest_dist < 5:
                        score -= (5 - closest_dist) * 20  # 가까울수록 큰 페널티
```

#### 2. **상대 모델링이 단순함** (Line 412-452)
```python
def _opponent_policy(self, state, agent_idx):
    # 단순히 우리 팩맨 쫓아가거나 음식 먹으러 감
```

**문제점:**
- Baseline 팀의 실제 전략을 제대로 모델링 못함
- Defensive agent의 패턴 예측 불가

**개선 방안:**
- Baseline 팀 행동 패턴 학습
- 수비수가 어느 위치를 선호하는지 추적
- 공격적/수비적 성향 파악

#### 3. **Rollout Policy의 우선순위 문제** (Line 349-410)

현재 우선순위:
1. 긴급 탈출 (적 3칸 이내)
2. 침입자 쫓기
3. 음식 먹기
4. 집으로 귀환 (8개 이상 들고 있을 때)
5. 적 영역으로 진입

**문제점:**
- 우선순위 4 (귀환)가 너무 늦음 → 8개 모으다가 죽을 수 있음
- 우선순위 1의 거리(3칸)가 너무 가까움 → 이미 늦을 수 있음

**개선 방안:**
```python
# Priority 1: 위험 감지 범위 증가
if myState.isPacman:
    ghosts = self._get_enemy_ghosts(state, agent_idx)
    if ghosts:
        closest_ghost_pos = min([g.getPosition() for g in ghosts],
                               key=lambda p: self._manhattan(myPos, p))
        ghost_dist = self._manhattan(myPos, closest_ghost_pos)
        
        # 5칸 이내면 경계, 3칸 이내면 즉시 도망
        if ghost_dist <= 5 and myState.numCarrying > 0:
            # 음식 들고 있으면 더 조심
            action = self._safe_path_to_boundary(myPos, state, agent_idx, avoid=[closest_ghost_pos])
            if action in legal:
                return action

# Priority 2: 동적 귀환 threshold
carrying_threshold = 8
if ghosts and min(self._manhattan(myPos, g.getPosition()) for g in ghosts) < 8:
    carrying_threshold = 3  # 위험하면 3개만 모으고 귀환
    
if myState.numCarrying >= carrying_threshold:
    # 귀환
```

#### 4. **Tree Reuse가 효과적이지 않음** (Line 319-334)
```python
def _reuse_tree(self, gameState):
    current_score = gameState.getScore()
    for child in self.tree_root.children:
        if child.state.getScore() == current_score:
            child.parent = None
            return child
    return MCTSNode(gameState)
```

**문제점:**
- Score만으로 매칭 → 정확도 낮음
- 여러 child가 같은 score 가질 수 있음

**개선 방안:**
```python
def _reuse_tree(self, gameState):
    # 더 정확한 매칭: position + score
    current_score = gameState.getScore()
    our_positions = tuple(sorted([
        gameState.getAgentPosition(i) for i in self.getTeam(gameState)
        if gameState.getAgentPosition(i) is not None
    ]))
    
    for child in self.tree_root.children:
        if child.state.getScore() == current_score:
            child_positions = tuple(sorted([
                child.state.getAgentPosition(i) for i in self.getTeam(child.state)
                if child.state.getAgentPosition(i) is not None
            ]))
            if our_positions == child_positions:
                child.parent = None
                return child
    
    return MCTSNode(gameState)
```

#### 5. **Joint Action Space가 너무 큼** (Line 253-270)
```python
def _get_legal_joint_actions(self, state):
    actions0 = state.getLegalActions(agent0)
    actions2 = state.getLegalActions(agent2)
    
    # Generate all combinations
    joint_actions = []
    for a0 in actions0:
        for a2 in actions2:
            joint_actions.append((a0, a2))
```

**문제점:**
- 각 에이전트가 평균 4개 액션 → 4x4 = 16개 joint actions
- Branching factor가 크면 탐색 깊이 제한

**개선 방안:**
```python
def _get_legal_joint_actions(self, state):
    actions0 = state.getLegalActions(agent0)
    actions2 = state.getLegalActions(agent2)
    
    # 1. Stop action 제거 (defensive 제외)
    if len(actions0) > 1:
        actions0 = [a for a in actions0 if a != Directions.STOP]
    if len(actions2) > 1:
        actions2 = [a for a in actions2 if a != Directions.STOP]
    
    # 2. 휴리스틱으로 우선순위 정렬
    actions0 = self._prioritize_actions(state, agent0, actions0)
    actions2 = self._prioritize_actions(state, agent2, actions2)
    
    # 3. Top-K만 고려 (예: 각각 상위 3개)
    actions0 = actions0[:3]
    actions2 = actions2[:3]
    
    # Generate combinations
    joint_actions = []
    for a0 in actions0:
        for a2 in actions2:
            joint_actions.append((a0, a2))
    
    return joint_actions
```

---

## 테스트 결과 분석 대기 중...

로그에서 찾아볼 패턴:
1. **어디서 죽는가?**
   - 경계 근처? → 진입 전략 문제
   - 깊숙이 들어가서? → 탈출 타이밍 문제
   
2. **얼마나 음식을 모으는가?**
   - 0-2개만 모으고 귀환? → 너무 소심
   - 6-8개 모으다 죽음? → 너무 욕심
   
3. **수비가 제대로 되는가?**
   - 침입자를 잡는가?
   - 침입자가 쉽게 음식을 가져가는가?

4. **롤아웃 수는?**
   - 0.8초에 몇 개? (Phase 2는 ~12K)
   - 시간 내에 충분히 탐색하는가?

---

## 우선순위 개선 계획

### Phase 2.1 (Quick Wins):
1. **평가 함수 개선** - numCarrying 고려
2. **위험 감지 범위 증가** - 3칸 → 5칸
3. **동적 귀환 threshold** - 위험도에 따라 3-8개
4. **Stop action 제거** - 공격 시 불필요

### Phase 2.2 (Medium):
5. **Tree reuse 개선** - position 기반 매칭
6. **Joint action pruning** - Top-K만 탐색
7. **더 나은 상대 모델링** - 실제 패턴 학습

### Phase 2.3 (Advanced):
8. **Adaptive MCTS** - 상황에 따라 exploration constant 조정
9. **Progressive widening** - 깊이에 따라 branching factor 조정
10. **RAVE (Rapid Action Value Estimation)** - 액션 수준 통계

---

## A/B 테스트 프로토콜

각 개선사항마다:
1. Baseline 대비 10 게임 실행
2. Win rate 변화 측정
3. 평균 점수 변화 측정
4. 개선되면 채택, 아니면 롤백

**목표:**
- Phase 2: ~100% win rate (검증 필요)
- Phase 2.1: >= 100% win rate + 더 큰 점수차
- Phase 2.2: >= 100% win rate + 더 강한 상대에 대응
- Phase 2.3: >= 100% win rate + 최적 플레이
