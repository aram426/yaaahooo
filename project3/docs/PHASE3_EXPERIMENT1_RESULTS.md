# Phase 3 Experiment 1 Results

**Date**: 2026-06-01  
**Commit**: 7406e4e  
**Approach**: Fast heuristic scoring (no simulation)

---

## Experiment Summary

**Goal**: Reduce progressive widening cost while maintaining offensive bias

**Method**: Replace simulation-based scoring with O(1) directional heuristic
- Red team: East +2, North +1
- Blue team: West +2, North +1
- STOP: -5 penalty

---

## Performance Results

### Rollout Performance

| Metric | Phase 2 (Baseline) | Phase 3 Original | Experiment 1 | vs Phase 2 | vs Phase 3 |
|--------|-------------------|------------------|--------------|------------|------------|
| Normal rollouts | 12,000-13,000 | 6,500 | **7,000-7,500** | -40% ⬇️ | +15% ⬆️ |
| Complex rollouts | 5,000-7,000 | 3,500 | **4,300-4,500** | -30% ⬇️ | +25% ⬆️ |
| Time/rollout | 0.06-0.07ms | 0.12-0.23ms | **0.10-0.19ms** | +50% slower | 15% faster |
| Final score | Lost by 18 | Lost by 18 | **Lost by 18** | ❌ No change | ❌ No change |

### Detailed Analysis

**Normal state (early/late game):**
- Rollouts: 7,000-7,500 (improved from 6,500)
- Time: 0.10-0.11ms (faster than 0.12ms)
- Still 40% slower than Phase 2

**Complex state (mid-game):**
- Rollouts: 4,300-4,500 (improved from 3,500)
- Time: 0.18-0.19ms (faster than 0.23ms)
- Still 30% slower than Phase 2

**Warnings:**
- 4 illegal action warnings (similar to Phase 2-3)

---

## Conclusion: PARTIAL SUCCESS

### ✅ Improvements
- 15-25% faster than Phase 3 original
- No simulation overhead per action
- Simpler code (O(1) vs O(n) per action)

### ❌ Still Problems
- **Still 30-40% slower than Phase 2**
- **No win rate improvement** (still lost by 18 points)
- Rollout count still below Phase 2 baseline

### 🔍 Why Still Slow?

Even without simulation, progressive widening has overhead:
1. **Sorting 25 actions**: O(n log n) per expansion
2. **Action scoring loop**: O(n) per expansion
3. **List operations**: Sorting + list comprehension

Phase 2 has ZERO overhead:
- Just `pop(0)` from unsorted list
- O(1) per expansion

### 🔍 Why No Win Rate Improvement?

Possible reasons:
1. **Direction heuristic too simplistic**
   - "East" doesn't mean offensive if agent is already in enemy territory
   - Doesn't account for food location, ghost positions, etc.
   - Might prioritize wrong actions

2. **Reward shaping not strong enough**
   - +3 per pacman might not be enough
   - Tree still doesn't explore offensive plays sufficiently

3. **Insufficient rollouts**
   - 7,000 rollouts vs 12,000 in Phase 2
   - 40% fewer rollouts → less accurate evaluation
   - Quality of action selection < quantity of exploration

---

## Decision: PROCEED TO EXPERIMENT 2 (Option A)

### Rationale

1. **Experiment 1 failed to restore Phase 2 performance**
   - Still 30-40% slower
   - No win rate improvement
   - Fast heuristic is not enough

2. **Progressive widening overhead not worth it**
   - Even O(1) scoring has sorting overhead
   - Direction heuristic is too simplistic to be useful
   - Better to rely on MCTS exploration with reward shaping

3. **Reward shaping alone might work**
   - Need to test with full Phase 2 rollout count (12K)
   - Reward shaping biases evaluation, not action selection
   - MCTS exploration + reward shaping might be sufficient

### Next Step: Experiment 2 (Option A)

**Changes:**
- Remove progressive widening entirely
- Keep reward shaping in `_evaluate_state()`
- Restore Phase 2 expansion (simple `pop(0)`)

**Expected:**
- Rollouts: 7K → 12K (back to Phase 2)
- Time: 0.10-0.19ms → 0.06-0.07ms (Phase 2 level)
- Win rate: **Should improve if reward shaping works**

**If successful:**
- Reward shaping alone is sufficient
- Progressive widening was unnecessary complexity

**If failed:**
- Reward shaping doesn't work
- Need different approach (Phase 4 optimization, or rethink strategy)

---

## Performance Table

| Version | Rollouts | Time/rollout | Win Rate | Notes |
|---------|----------|--------------|----------|-------|
| Phase 2 | 12,000 | 0.06ms | 0% | Baseline (heuristic rollout) |
| Phase 3 original | 6,500 | 0.12ms | 0% | Simulation-based scoring |
| Experiment 1 | 7,000 | 0.10ms | 0% | Direction heuristic |
| **Experiment 2** (next) | **12,000?** | **0.06ms?** | **50%+?** | Remove progressive widening |

---

## Learnings

1. **Even O(1) scoring has overhead**: Sorting + looping still costs
2. **Direction heuristic too naive**: Doesn't capture game state nuance
3. **Quantity > Quality**: More rollouts with simple eval > fewer with smart action selection
4. **Progressive widening not suitable for this problem**: Real-time constraints favor exploration quantity

---

## Status: PROCEEDING TO EXPERIMENT 2

Experiment 1 showed improvement but not enough. Proceeding with Experiment 2 (Option A): Remove progressive widening, keep reward shaping only.
