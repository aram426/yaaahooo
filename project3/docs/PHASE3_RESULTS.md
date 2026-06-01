# Phase 3 Implementation Results

**Date**: 2026-06-01  
**Branch**: `feature/mcts-implementation`  
**Commit**: 12a9fd5

---

## Implementation Status

⚠️ **PARTIAL**: Phase 3 - Aggressive Bias (Performance Issue Found)

### Components Implemented

1. ✅ **Reward Shaping** (`_evaluate_state()`)
   - +3.0 bonus per pacman in enemy territory
   - +0.8 bonus per food carrying
   - -8.0 penalty if both agents defensive
   - +1.5 bonus per food eaten

2. ⚠️ **Progressive Widening** (`_expand()`)
   - Scores all joint actions by offensiveness
   - Offensiveness = num_pacmen * 2 + carrying
   - Sorts actions by offensiveness (high to low)
   - Expands offensive actions first
   - **Problem**: Too expensive (O(n²) per expansion)

3. ✅ **Initial Food Tracking**
   - Track initial food count in `registerInitialState`

---

## Performance Metrics

### Critical Performance Regression

| Metric | Phase 2 | Phase 3 | Change | Status |
|--------|---------|---------|--------|--------|
| Avg rollouts | 12,000-13,000 | **3,500-6,500** | **-50~70%** ⬇️ | ⚠️ **Major regression** |
| Time/rollout | 0.06-0.07ms | **0.12-0.23ms** | **+100~300%** | ⚠️ **2-3x slower** |
| Target (500) | 25x faster | **7-13x faster** | Still above target | ✅ Safe but concerning |
| Final score | Lost by 18 | **Lost by 18** | **No change** | ❌ **No improvement** |

### Detailed Rollout Analysis

**Normal state (early/late game):**
- Phase 2: 12,000-13,000 rollouts
- Phase 3: 6,500 rollouts
- Impact: -50% rollout count

**Complex state (mid-game, agents clustered):**
- Phase 2: 5,000-7,000 rollouts
- Phase 3: 3,500 rollouts
- Impact: -50~70% rollout count

**Time per rollout:**
- Phase 2: 0.06-0.07ms (heuristic rollout)
- Phase 3: 0.12-0.23ms (2-3x slower)
- Cause: Progressive widening overhead in `_expand()`

---

## Root Cause Analysis

### Problem: Progressive Widening is Too Expensive

**Current implementation:**
```python
def _expand(self, node):
    if node.untried_actions is None:
        joint_actions = self._get_legal_joint_actions(node.state)  # ~25 actions
        
        scored_actions = []
        for joint_action in joint_actions:
            # Problem: Simulate ALL 25 actions
            successor = self._apply_joint_action(node.state, joint_action)
            # Calculate offensiveness...
            scored_actions.append((joint_action, offensiveness))
        
        # Sort and store
        node.untried_actions = [action for action, _ in scored_actions]
```

**Cost breakdown per expansion:**
- 25 joint actions (5 actions per agent)
- 25 × `_apply_joint_action()` calls
- Each call: 4 agent turns × successor generation
- Total: **~100 successor generations per expansion**

**Phase 2 cost:**
- 0 successor generations (just pop first action)
- O(1) per expansion

**Phase 3 cost:**
- 100 successor generations per expansion
- O(n²) where n = number of actions

**Impact:**
- Expansion became 100x more expensive
- Fewer expansions per second
- Tree stays shallower
- Fewer rollouts possible

---

## Why No Win Rate Improvement?

Despite reward shaping, still lost by 18 points. Possible reasons:

1. **Insufficient exploration due to slow expansion**
   - Fewer rollouts → shallower tree
   - Less exploration of game tree
   - Reward shaping can't help if tree is too shallow

2. **Progressive widening overhead overwhelms benefit**
   - Spent too much time scoring actions
   - Not enough time for actual MCTS iterations
   - Quality vs. quantity tradeoff went wrong

3. **Reward shaping might work with faster expansion**
   - Need to test reward shaping WITHOUT progressive widening
   - Progressive widening might not be necessary

---

## Experimental Plan

### Experiment 1: Optimize Progressive Widening (Option B)

**Goal**: Reduce progressive widening cost while keeping offensive bias

**Approach 1: Fast heuristic scoring (no simulation)**
```python
# Instead of simulating, use fast heuristic
for joint_action in joint_actions:
    action0, action2 = joint_action
    
    # Fast heuristic: count "towards enemy" actions
    score = 0
    if action0 in [Directions.EAST, Directions.NORTH]:  # towards enemy (for red)
        score += 1
    if action2 in [Directions.EAST, Directions.NORTH]:
        score += 1
    
    scored_actions.append((joint_action, score))
```

**Pros:**
- O(1) per action instead of O(n)
- No successor generation
- Still prioritizes offensive actions

**Cons:**
- Less accurate than simulation
- Might miss nuanced offensive moves

**Approach 2: Sample top-k actions**
```python
# Randomly sample 10 out of 25 actions to score
sampled = random.sample(joint_actions, min(10, len(joint_actions)))

for joint_action in sampled:
    successor = self._apply_joint_action(node.state, joint_action)
    # Calculate offensiveness...
    scored_actions.append((joint_action, offensiveness))

# Add unscored actions at end
unscored = [a for a in joint_actions if a not in sampled]
node.untried_actions = [action for action, _ in scored_actions] + unscored
```

**Pros:**
- Reduces cost from 25 to 10 simulations
- Still gets some offensive bias
- Randomness adds exploration

**Cons:**
- Might miss the most offensive action
- Still has simulation overhead

**Decision**: Try Approach 1 first (fast heuristic). If no improvement, try Approach 2. If still no improvement, go to Experiment 2.

### Experiment 2: Reward Shaping Only (Option A)

**Goal**: Test if reward shaping alone can improve win rate

**Changes:**
- Remove progressive widening from `_expand()`
- Keep reward shaping in `_evaluate_state()`
- Revert to Phase 2 expansion logic

**Expected outcome:**
- Rollout count: 12,000+ (back to Phase 2 level)
- Win rate: Should improve if reward shaping works
- If win rate improves, progressive widening was unnecessary overhead

---

## Next Steps

1. ✅ Document current Phase 3 results (this file)
2. ⏳ Experiment 1: Optimize progressive widening (Approach 1)
3. ⏳ Test and measure performance
4. ⏳ If failed: Try Approach 2
5. ⏳ If failed: Experiment 2 (Option A)
6. ⏳ Document final decision

---

## Git History

```
12a9fd5 (HEAD -> feature/mcts-implementation) feat: Implement Phase 3 - Aggressive bias with reward shaping
d061536 fix: Add legal action verification in rollout policies
c766e80 feat: Implement Phase 2 - Fast rollout policy with heuristics
```

---

## Lessons Learned

1. **Progressive widening is expensive**: Simulating all actions before expansion adds O(n²) cost
2. **Quality vs. quantity tradeoff**: Smarter action selection vs. more MCTS iterations
3. **Measure before optimize**: Should have profiled first before implementing
4. **Reward shaping alone might be enough**: Progressive widening might be unnecessary complexity

---

## Performance Comparison Table

| Phase | Rollouts | Time/rollout | Win Rate | Notes |
|-------|----------|--------------|----------|-------|
| Phase 1 | 15,000 | 0.05ms | 0% | Random rollout, crashed |
| Phase 2 | 12,000 | 0.06ms | 0% | Heuristic rollout, stable |
| Phase 3 (current) | 3,500-6,500 | 0.12-0.23ms | 0% | Progressive widening too slow |
| Phase 3 (target) | 10,000+ | <0.10ms | 50%+ | Need optimization |

---

## Status: BLOCKED

Phase 3 is blocked by progressive widening performance issue. Need to either:
- Optimize progressive widening (Experiment 1)
- Remove progressive widening (Experiment 2)

Proceeding with Experiment 1 (Approach 1: Fast heuristic scoring).
