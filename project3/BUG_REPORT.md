# 발견된 버그 및 문제점

## 일자: 2026-06-03

### BUG #1: Time Budget Too Large (CRITICAL)

**증상:**
- 게임이 60초 timeout에 도달
- Quick test에서 3 게임 모두 TIMEOUT
- Autograder도 타임아웃으로 실패

**원인:**
```python
self.time_budget = 0.8  # seconds
```

**분석:**
- 각 에이전트가 매 턴마다 최대 0.8초 사용
- 4 agents × ~750 moves/agent × 0.8초 = 2400초 = 40분!
- 프레임워크의 타임아웃 (60초?)을 훨씬 초과

**해결:**
```python
self.time_budget = 0.3  # Reduced for faster gameplay
```

**영향:**
- Rollouts 감소: ~12K → ~4-5K per move
- 하지만 게임이 실제로 완료됨
- Trade-off: 탐색 깊이 vs 실행 가능성

**교훈:**
- "더 많은 시간 = 더 나은 성능" 이 아님
- 시스템 제약 (timeout) 고려 필수
- Phase 2가 100% win rate라는 주장이 의심스러움 (실제로 게임 완료 못했을 수도)

---

### ISSUE #2: Joint Action Space Size

**문제:**
- 4 legal actions per agent × 4 legal actions = 16 joint actions
- Branching factor가 크면 탐색 효율 저하

**현재 상태:**
- Phase 2: 모든 joint actions 탐색
- Phase 2.1: STOP 제거 (약간 개선)

**추가 개선 필요:**
- Action prioritization
- Progressive widening
- Top-K selection

---

### ISSUE #3: Evaluation Function

**Phase 2 문제:**
- Score만 고려
- 중간 상태의 뉘앙스 놓침
- Carrying food, danger 등 무시

**Phase 2.1 개선:**
- numCarrying 고려 (+10 per food)
- Danger penalty (enemy proximity while carrying)
- Score는 여전히 primary (×100 weight)

---

### ISSUE #4: Rollout Policy Priorities

**Phase 2 문제:**
- 위험 감지 범위 3칸 (너무 짧음)
- 귀환 threshold 8개 고정 (너무 욕심)
- Stop action 포함 (비효율)

**Phase 2.1 개선:**
- 위험 감지 5칸
- 동적 threshold (3-8, danger-based)
- Stop action 제거

---

## 테스트 현황

### Phase 2 (Original, 0.8s budget):
- **Status**: TIMEOUT (all 3 games)
- **Win Rate**: N/A (못 완료)
- **Conclusion**: 실행 불가능

### Phase 2 (Fixed, 0.3s budget):
- **Status**: Testing...
- **Expected**: 실행 가능, win rate 측정 필요

### Phase 2.1 (Improvements + 0.3s):
- **Status**: Ready to test
- **Expected**: Phase 2보다 나은 성능

---

## 다음 단계

1. ✅ Phase 2 time budget 수정 (0.8 → 0.3)
2. 🔄 Phase 2 (0.3s) 테스트 중...
3. ⏳ 결과에 따라 Phase 2.1 테스트
4. ⏳ 로그 분석하여 추가 약점 파악
5. ⏳ Phase 2.2 개발 (tree reuse, action pruning)

---

## 발견 (Discovery)

**중요한 깨달음:**
"Phase 2가 100% win rate를 달성했다"는 주장이 검증되지 않았을 수 있음.
- 타임아웃으로 게임이 완료되지 않았거나
- 다른 설정 (더 짧은 맵, 더 짧은 게임)에서 테스트했거나
- 또는 문서가 잘못되었을 수 있음

**Action:**
- 먼저 실행 가능한 버전 만들기
- 그 다음 점진적으로 개선
- 각 개선마다 A/B 테스트로 검증
