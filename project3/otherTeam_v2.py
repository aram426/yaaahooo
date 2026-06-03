# myTeam.py
# ---------
# Licensing Information:  You are free to use or extend these projects for
# educational purposes provided that (1) you do not distribute or publish
# solutions, (2) you retain this notice, and (3) you provide clear
# attribution to UC Berkeley, including a link to http://ai.berkeley.edu.
#
# Attribution Information: The Pacman AI projects were developed at UC Berkeley.
# The core projects and autograders were primarily created by John DeNero
# (denero@cs.berkeley.edu) and Dan Klein (klein@cs.berkeley.edu).
# Student side autograding was added by Brad Miller, Nick Hay, and
# Pieter Abbeel (pabbeel@cs.berkeley.edu).

from captureAgents import CaptureAgent
import random, time, util
from game import Directions
import game

# ── 디버그 로거 ───────────────────────────────────────────────────────────────
from bug.debug_logger import DebugLogger

#################
# Team creation #
#################

def createTeam(firstIndex, secondIndex, isRed,
               first='OffensiveAgent', second='DefensiveAgent'):
    return [eval(first)(firstIndex), eval(second)(secondIndex)]

####################
# Shared utilities #
####################

def aStarSearch(startPos, goalPositions, walls, distancer,
                dangerZone=None, dangerCost=20):
    if not goalPositions:
        return None
    from util import PriorityQueue

    goalSet    = set(goalPositions)
    dangerZone = dangerZone or set()

    def heuristic(pos):
        return min(distancer.getDistance(pos, g) for g in goalSet)

    frontier = PriorityQueue()
    frontier.push((startPos, [], 0), heuristic(startPos))
    visited = {}

    while not frontier.isEmpty():
        pos, path, cost = frontier.pop()
        if pos in visited and visited[pos] <= cost:
            continue
        visited[pos] = cost

        if pos in goalSet:
            return path[0] if path else Directions.STOP

        x, y = int(pos[0]), int(pos[1])
        for dx, dy, action in [(0,1,Directions.NORTH),(0,-1,Directions.SOUTH),
                                (1,0,Directions.EAST),(-1,0,Directions.WEST)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < walls.width and 0 <= ny < walls.height and not walls[nx][ny]:
                newPos    = (nx, ny)
                stepCost  = dangerCost if newPos in dangerZone else 1
                newCost   = cost + stepCost
                if newPos not in visited or visited.get(newPos, float('inf')) > newCost:
                    frontier.push((newPos, path+[action], newCost),
                                  newCost + heuristic(newPos))
    return None


def getBoundaryPositions(gameState, isRed):
    layout = gameState.data.layout
    width, height = layout.width, layout.height
    walls = gameState.getWalls()
    x = width // 2 - 1 if isRed else width // 2
    return [(x, y) for y in range(1, height-1) if not walls[x][y]]


def getDeadEnds(walls):
    """막힌 통로(dead-end) 셀 집합. 이웃이 1개뿐인 셀을 BFS로 전파."""
    width, height = walls.width, walls.height

    def neighbors(x, y):
        return [(x+dx, y+dy) for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]
                if 0 <= x+dx < width and 0 <= y+dy < height
                and not walls[x+dx][y+dy]]

    dead  = set()
    queue = []
    for x in range(width):
        for y in range(height):
            if not walls[x][y] and len(neighbors(x, y)) == 1:
                dead.add((x, y))
                queue.append((x, y))

    i = 0
    while i < len(queue):
        cx, cy = queue[i]; i += 1
        for nx, ny in neighbors(cx, cy):
            if (nx, ny) not in dead:
                live = [p for p in neighbors(nx, ny) if p not in dead]
                if len(live) == 1:
                    dead.add((nx, ny))
                    queue.append((nx, ny))
    return dead


####################
# Base Agent Class #
####################

class BaseAgent(CaptureAgent):

    def registerInitialState(self, gameState):
        CaptureAgent.registerInitialState(self, gameState)
        self.start             = gameState.getAgentPosition(self.index)
        self.walls             = gameState.getWalls()
        self.width             = gameState.data.layout.width
        self.height            = gameState.data.layout.height
        self.boundaryPositions = getBoundaryPositions(gameState, self.red)
        self.posHistory        = []
        self.deadEnds          = getDeadEnds(gameState.getWalls())
        self._distance_cache   = {}  # 거리 캐싱

    def getSuccessor(self, gameState, action):
        successor = gameState.generateSuccessor(self.index, action)
        pos = successor.getAgentState(self.index).getPosition()
        from util import nearestPoint
        if pos != nearestPoint(pos):
            return successor.generateSuccessor(self.index, action)
        return successor

    def getEnemyGhosts(self, gameState):
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        # 최적화: None 체크 먼저 (early return)
        ghosts = []
        for e in enemies:
            pos = e.getPosition()
            if pos and not e.isPacman and e.scaredTimer <= 0:
                ghosts.append(e)
        return ghosts

    def getScaredGhosts(self, gameState):
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        return [e for e in enemies
                if not e.isPacman and e.getPosition() is not None
                and e.scaredTimer > 0]

    def getInvaders(self, gameState):
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        return [e for e in enemies
                if e.isPacman and e.getPosition() is not None]

    def buildDangerZone(self, ghosts, radius=2):
        zone = set()
        for g in ghosts:
            gpos = g.getPosition()
            if gpos:
                gx, gy = int(gpos[0]), int(gpos[1])
                r = radius * 2 if (gx, gy) in self.deadEnds else radius
                for dx in range(-r, r+1):
                    for dy in range(-r, r+1):
                        nx, ny = gx+dx, gy+dy
                        if (0 <= nx < self.walls.width
                                and 0 <= ny < self.walls.height
                                and not self.walls[nx][ny]):
                            zone.add((nx, ny))
        return zone

    def safeAction(self, gameState):
        actions = [a for a in gameState.getLegalActions(self.index)
                   if a != Directions.STOP]
        ghosts = self.getEnemyGhosts(gameState)
        if not ghosts or not actions:
            return random.choice(actions) if actions else Directions.STOP
        bestAction, bestDist = None, -1
        for action in actions:
            newPos = self.getSuccessor(gameState, action).getAgentState(self.index).getPosition()
            d = min(self.getMazeDistance(newPos, g.getPosition()) for g in ghosts)
            if d > bestDist:
                bestDist, bestAction = d, action
        return bestAction or random.choice(actions)

    # ── [BUG FIX 1] isStuck: window 6→10, 임계값 강화 (2/3 이상일 때만 stuck)
    # 이전: window=6, count >= 3 (50%) → 경계 근처 정상 왕복도 stuck 판정
    # 수정: window=10, count >= 7 (70%) → 실제 교착 상태만 탐지
    def isStuck(self, myPos, window=10):
        self.posHistory.append(myPos)
        if len(self.posHistory) > window * 2:
            self.posHistory = self.posHistory[-window * 2:]
        if len(self.posHistory) >= window:
            recent = self.posHistory[-window:]
            if recent.count(myPos) > window // 2:
                return True
        return False

    def getScore(self, gameState):
        return gameState.getScore() if self.red else -gameState.getScore()

    def getRemainingMoves(self, gameState):
        return gameState.data.timeleft

    # ── [BUG FIX 2] getSafeEntries: 현재 위치 제외
    # 이전: safe_entries에 현재 위치가 포함 → A*가 STOP 반환 → 반복 정지
    # 수정: 현재 위치(myPos)를 safe_entries에서 제거
    def getSafeEntries(self, ghosts, safeRadius=3, myPos=None):
        safe = [b for b in self.boundaryPositions
                if all(self.getMazeDistance(b, g.getPosition()) >= safeRadius
                       for g in ghosts)]
        # 현재 위치가 safe_entries에 포함되면 제거
        if myPos is not None:
            myPosInt = (int(myPos[0]), int(myPos[1]))
            safe = [b for b in safe if b != myPosInt]

        if safe:
            return safe

        # fallback: 고스트와 가장 먼 경계 하나 (현재 위치 제외)
        sorted_bp = sorted(self.boundaryPositions,
                           key=lambda b: min(self.getMazeDistance(b, g.getPosition())
                                             for g in ghosts),
                           reverse=True)
        if myPos is not None:
            myPosInt = (int(myPos[0]), int(myPos[1]))
            for b in sorted_bp:
                if b != myPosInt:
                    return [b]
        return [sorted_bp[0]] if sorted_bp else self.boundaryPositions[:1]


####################
# Offensive Agent  #
####################

class OffensiveAgent(BaseAgent):

    CARRY_LIMIT       = 5
    CARRY_FLEE_MIN    = 1
    GHOST_FLEE_DIST   = 6

    def registerInitialState(self, gameState):
        BaseAgent.registerInitialState(self, gameState)
        self.carrying       = 0
        self.lastFoodCount  = len(self.getFood(gameState).asList())
        self.stuckEscapeIdx = 0  # [BUG FIX 3] stuck_escape 목표 순환용 인덱스
        # ── 로거 초기화 ──────────────────────────────────────────────────────
        self.logger = DebugLogger(f"OffensiveAgent_{self.index}", echo=False)
        self.logger.info("INIT", "OffensiveAgent registered",
                         index=self.index, start=self.start,
                         boundary_count=len(self.boundaryPositions),
                         dead_end_count=len(self.deadEnds))

    def chooseAction(self, gameState):
        self.logger.step()

        myState   = gameState.getAgentState(self.index)
        myPos     = myState.getPosition()
        walls     = gameState.getWalls()
        timeLeft  = self.getRemainingMoves(gameState)

        # 음식 수집량 추적
        foodList = self.getFood(gameState).asList()
        cnt = len(foodList)
        if cnt < self.lastFoodCount:
            self.carrying += self.lastFoodCount - cnt
        self.lastFoodCount = cnt
        if not myState.isPacman:
            self.carrying = 0

        ghosts       = self.getEnemyGhosts(gameState)
        scaredGhosts = self.getScaredGhosts(gameState)
        capsules     = self.getCapsules(gameState)
        dangerZone   = self.buildDangerZone(ghosts, radius=2)
        stuck        = self.isStuck(myPos)

        # 상태 요약 로그
        self.logger.log("STATE",
                        pos=myPos,
                        isPacman=myState.isPacman,
                        carrying=self.carrying,
                        timeLeft=timeLeft,
                        food_remaining=cnt,
                        ghosts=[(g.getPosition(), g.scaredTimer) for g in ghosts + scaredGhosts],
                        capsules=capsules,
                        in_deadEnd=(myPos in self.deadEnds),
                        stuck=stuck)

        # ── 교착 탈출 ──────────────────────────────────────────────────────
        # [BUG FIX 3] stuck_escape 목표를 순환식으로 변경
        # 이전: max(entries, getMazeDistance) → 항상 같은 목표 → 핑퐁
        # 수정: stuckEscapeIdx로 entries를 순환하여 매번 다른 목표 선택
        if stuck and not myState.isPacman:
            myPosInt = (int(myPos[0]), int(myPos[1]))
            entries = self.getSafeEntries(ghosts, myPos=myPos) if ghosts else [
                b for b in self.boundaryPositions if b != myPosInt
            ]
            if not entries:
                entries = [b for b in self.boundaryPositions if b != myPosInt]
            if not entries:
                entries = self.boundaryPositions

            # 거리 기준 내림차순 정렬 후 인덱스 순환
            entries_sorted = sorted(entries,
                                    key=lambda p: self.getMazeDistance(myPos, p),
                                    reverse=True)
            self.stuckEscapeIdx = (self.stuckEscapeIdx + 1) % len(entries_sorted)
            alt = entries_sorted[self.stuckEscapeIdx]

            act = aStarSearch(myPos, {alt}, walls, self.distancer)
            if act and act != Directions.STOP:
                self.logger.action(act, "stuck_escape")
                return act

        # ── 0) 시간 부족 → 귀환 ───────────────────────────────────────────
        if myState.isPacman and self.carrying > 0 and timeLeft < 80:
            self.logger.warn("TIME_LOW", "Returning home - time critical",
                             timeLeft=timeLeft, carrying=self.carrying)
            act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
            if act:
                self.logger.action(act, "time_low_return")
                return act

        # ── 1) 겁먹은 고스트 추격 ─────────────────────────────────────────
        # [BUG FIX 4] carrying < CARRY_LIMIT일 때만 scared ghost 추격
        # 이전: 캐리 중이어도 scared ghost 추격 → 귀환 지연
        # 수정: carrying < CARRY_LIMIT일 때만 추격 허용
        if scaredGhosts and myState.isPacman and self.carrying < self.CARRY_LIMIT:
            closest = min(scaredGhosts,
                          key=lambda g: self.getMazeDistance(myPos, g.getPosition()))
            dist_to_scared = self.getMazeDistance(myPos, closest.getPosition())
            self.logger.log("SCARED_GHOST",
                            closest_pos=closest.getPosition(),
                            dist=dist_to_scared,
                            scaredTimer=closest.scaredTimer)
            if dist_to_scared <= 8:
                act = aStarSearch(myPos, {closest.getPosition()}, walls, self.distancer)
                if act:
                    self.logger.action(act, "chase_scared_ghost")
                    return act

        # ── 2) 긴급: 고스트 3칸 이내 ──────────────────────────────────────
        if myState.isPacman and ghosts:
            danger = [g for g in ghosts
                      if self.getMazeDistance(myPos, g.getPosition()) <= 3]
            if danger:
                self.logger.warn("DANGER",
                                 "Ghost within 3 cells!",
                                 ghost_positions=[g.getPosition() for g in danger],
                                 capsules_available=bool(capsules))
                if capsules:
                    cap      = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                    capDist  = self.getMazeDistance(myPos, cap)
                    gDist    = min(self.getMazeDistance(myPos, g.getPosition()) for g in danger)
                    self.logger.log("CAPSULE_CHECK",
                                    cap=cap, capDist=capDist, ghostDist=gDist)
                    if capDist < gDist:
                        act = aStarSearch(myPos, {cap}, walls, self.distancer)
                        if act:
                            self.logger.action(act, "emergency_capsule")
                            return act
                act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
                if act:
                    self.logger.action(act, "emergency_flee_boundary")
                    return act
                self.logger.warn("DANGER", "Falling back to safeAction")
                return self.safeAction(gameState)

        # ── 3) 캐리 중 + 고스트 접근 → 즉시 귀환 ─────────────────────────
        # [BUG FIX 5] FLEE_EVAL 조건 수정
        # 이전: escape_dist <= ghost_dist + 2 만 체크
        #   → escape_dist=18, ghost_dist=4일 때 should_flee=False (버그)
        # 수정: 탈출 거리가 고스트 거리의 2배 이상이면 추가로 도주 조건 발동
        if myState.isPacman and self.carrying >= self.CARRY_FLEE_MIN and ghosts:
            closest_ghost = min(ghosts,
                                key=lambda g: self.getMazeDistance(myPos, g.getPosition()))
            ghost_dist    = self.getMazeDistance(myPos, closest_ghost.getPosition())
            closest_boundary = min(self.boundaryPositions,
                                   key=lambda b: self.getMazeDistance(myPos, b))
            escape_dist   = self.getMazeDistance(myPos, closest_boundary)

            should_flee = (
                (ghost_dist <= self.GHOST_FLEE_DIST and escape_dist <= ghost_dist + 2)
                or (ghost_dist <= self.GHOST_FLEE_DIST and escape_dist >= ghost_dist * 2)
            )
            self.logger.log("FLEE_EVAL",
                            ghost_dist=ghost_dist,
                            escape_dist=escape_dist,
                            should_flee=should_flee,
                            carrying=self.carrying)
            if should_flee:
                act = aStarSearch(myPos, set(self.boundaryPositions),
                                  walls, self.distancer, dangerZone)
                if act:
                    self.logger.action(act, "carrying_flee")
                    return act

        # ── 4) 캐리 한도 달성 → 귀환 ──────────────────────────────────────
        if self.carrying >= self.CARRY_LIMIT and myState.isPacman:
            self.logger.info("CARRY_LIMIT",
                             f"Carry limit reached ({self.carrying}), returning")
            act = aStarSearch(myPos, set(self.boundaryPositions),
                              walls, self.distancer, dangerZone)
            if act:
                self.logger.action(act, "carry_limit_return")
                return act

        # ── 5) dead-end에 갇혀있고 고스트 있으면 즉시 탈출 ───────────────
        if myState.isPacman and ghosts and myPos in self.deadEnds:
            self.logger.warn("DEAD_END", "Trapped in dead-end with ghost nearby", pos=myPos)
            act = aStarSearch(myPos, set(self.boundaryPositions),
                              walls, self.distancer, dangerZone)
            if act:
                self.logger.action(act, "dead_end_escape")
                return act

        # ── 6) 고스트가 경계를 막고 있으면 안전한 진입점 탐색 ─────────────
        if not myState.isPacman and ghosts:
            blocking = [g for g in ghosts
                        if any(self.getMazeDistance(g.getPosition(), b) <= 3
                               for b in self.boundaryPositions)]
            if blocking:
                # [BUG FIX 2 적용] myPos 전달로 현재 위치 제외
                safe_entries = self.getSafeEntries(ghosts, safeRadius=3, myPos=myPos)
                self.logger.warn("BOUNDARY_BLOCKED",
                                 blocking=[g.getPosition() for g in blocking],
                                 safe_entries=safe_entries)
                if capsules:
                    cap     = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                    capDist = self.getMazeDistance(myPos, cap)
                    entDist = min(self.getMazeDistance(myPos, e) for e in safe_entries)
                    if capDist <= entDist:
                        act = aStarSearch(myPos, {cap}, walls, self.distancer, dangerZone)
                        if act:
                            self.logger.action(act, "blocked_use_capsule")
                            return act
                target = min(safe_entries, key=lambda p: self.getMazeDistance(myPos, p))
                act = aStarSearch(myPos, {target}, walls, self.distancer)
                if act and act != Directions.STOP:
                    self.logger.action(act, "safe_boundary_entry")
                    return act

        # ── 7) 고스트 근처면 캡슐 먼저 ────────────────────────────────────
        if capsules and myState.isPacman and ghosts:
            nearGhost = any(self.getMazeDistance(myPos, g.getPosition()) <= 6
                            for g in ghosts)
            if nearGhost:
                cap = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                self.logger.log("CAPSULE_PRIORITY", cap=cap)
                act = aStarSearch(myPos, {cap}, walls, self.distancer, dangerZone)
                if act:
                    self.logger.action(act, "ghost_nearby_capsule")
                    return act

        # ── 8) 음식 먹으러 가기 ───────────────────────────────────────────
        if foodList:
            if ghosts:
                safe_food = [f for f in foodList if f not in self.deadEnds]
                targets   = safe_food if safe_food else foodList
            else:
                targets = foodList
            self.logger.log("FOOD_TARGET",
                            total_food=len(foodList),
                            safe_food=len(targets),
                            ghost_present=bool(ghosts))
            act = aStarSearch(myPos, set(targets), walls, self.distancer, dangerZone)
            if act:
                self.logger.action(act, "eat_food")
                return act

        # ── 9) fallback: 경계로 이동 ──────────────────────────────────────
        self.logger.warn("FALLBACK", "No primary target found, heading to boundary")
        act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
        if act:
            self.logger.action(act, "fallback_boundary")
            return act

        actions = [a for a in gameState.getLegalActions(self.index)
                   if a != Directions.STOP]
        chosen = random.choice(actions) if actions else Directions.STOP
        self.logger.action(chosen, "random_fallback")
        return chosen

    def _getAlternateBoundary(self, gameState, myPos):
        if not self.boundaryPositions:
            return self.start
        return max(self.boundaryPositions,
                   key=lambda p: self.getMazeDistance(myPos, p))

    def _getUnblockedEntry(self, gameState, blockingGhosts):
        myPos = gameState.getAgentState(self.index).getPosition()
        freeEntries = [b for b in self.boundaryPositions
                       if not any(self.getMazeDistance(b, g.getPosition()) <= 2
                                  for g in blockingGhosts)]
        if freeEntries:
            return min(freeEntries, key=lambda p: self.getMazeDistance(myPos, p))
        return None


####################
# Defensive Agent  #
####################

class DefensiveAgent(BaseAgent):

    def registerInitialState(self, gameState):
        BaseAgent.registerInitialState(self, gameState)
        self.prevFoodDefending = set(self.getFoodYouAreDefending(gameState).asList())
        self.lastEatenPos = None
        bp = self.boundaryPositions
        n  = len(bp)

        # alleyCapture 맵 감지: boundary 포지션이 매우 적으면 deadEnd에서 갇혀있을 가능성
        # 이 경우 중앙 boundary 집중 (patrol 효율성 증가)
        if n >= 8:
            # 일반 맵: 1/4, 1/2, 3/4 지점
            self.patrolPoints = [bp[n//4], bp[n//2], bp[3*n//4]]
        elif n >= 4:
            # 좁은 맵 (alleyCapture): 중앙 2개 + 끝점
            self.patrolPoints = [bp[n//3], bp[2*n//3]]
        elif n > 0:
            # 매우 좁은 맵: 중앙 1개
            self.patrolPoints = [bp[n//2]]
        else:
            self.patrolPoints = [self.start]

        self.patrolIdx = 0
        # ── 로거 초기화 ──────────────────────────────────────────────────────
        self.logger = DebugLogger(f"DefensiveAgent_{self.index}", echo=False)
        self.logger.info("INIT", "DefensiveAgent registered",
                         index=self.index, start=self.start,
                         patrol_points=self.patrolPoints)

    def chooseAction(self, gameState):
        self.logger.step()

        myState  = gameState.getAgentState(self.index)
        myPos    = myState.getPosition()
        walls    = gameState.getWalls()
        isScared = myState.scaredTimer > 0
        score    = self.getScore(gameState)
        timeLeft = self.getRemainingMoves(gameState)
        stuck    = self.isStuck(myPos)

        currentFood = set(self.getFoodYouAreDefending(gameState).asList())
        eaten       = self.prevFoodDefending - currentFood
        if eaten:
            self.lastEatenPos = list(eaten)[0]
            self.logger.warn("FOOD_EATEN",
                             "Defending food was eaten!",
                             pos=self.lastEatenPos)
        self.prevFoodDefending = currentFood

        invaders = self.getInvaders(gameState)

        # 상태 요약 로그
        self.logger.log("STATE",
                        pos=myPos,
                        isScared=isScared,
                        scaredTimer=myState.scaredTimer,
                        score=score,
                        timeLeft=timeLeft,
                        invaders=[i.getPosition() for i in invaders],
                        stuck=stuck,
                        patrolIdx=self.patrolIdx,
                        lastEatenPos=self.lastEatenPos)

        if stuck:
            self.patrolIdx = (self.patrolIdx + 1) % len(self.patrolPoints)
            self.logger.log("STUCK", "Advancing patrol index", new_idx=self.patrolIdx)

        # 1) 침입자 추격
        if invaders:
            closest = min(invaders,
                          key=lambda e: self.getMazeDistance(myPos, e.getPosition()))
            target  = closest.getPosition()
            dist    = self.getMazeDistance(myPos, target)
            self.logger.info("INVADER",
                             f"Chasing invader at {target}",
                             dist=dist, isScared=isScared)

            if isScared:
                if dist <= 3:
                    self.logger.warn("SCARED_FLEE",
                                     "Scared and invader is close - fleeing",
                                     invader=target)
                    return self.safeFleeFrom(gameState, target)
                bp_target = min(self.boundaryPositions,
                                key=lambda p: self.getMazeDistance(p, target))
                act = aStarSearch(myPos, {bp_target}, walls, self.distancer)
                if act:
                    self.logger.action(act, "scared_boundary_intercept")
                    return act
            else:
                act = aStarSearch(myPos, {target}, walls, self.distancer)
                if act:
                    self.logger.action(act, "chase_invader")
                    return act

        # 2) 음식 먹힌 위치로 이동
        if self.lastEatenPos and not invaders:
            dist_to_eaten = self.getMazeDistance(myPos, self.lastEatenPos)
            self.logger.log("GOTO_EATEN",
                            target=self.lastEatenPos,
                            dist=dist_to_eaten)
            if dist_to_eaten > 1:
                act = aStarSearch(myPos, {self.lastEatenPos}, walls, self.distancer)
                if act:
                    self.logger.action(act, "goto_eaten_food")
                    return act
            else:
                self.lastEatenPos = None
                self.logger.log("EATEN_POS_CLEARED", "Reached last eaten position")

        # 3) 우세 + 시간 부족 → 수비 고정
        if score >= 5 and timeLeft < 200:
            target = self._getBestPatrolTarget(gameState, myPos)
            self.logger.info("DEFEND_MODE",
                             "Score lead + low time, holding position",
                             score=score, timeLeft=timeLeft, target=target)
            act = aStarSearch(myPos, {target}, walls, self.distancer)
            if act:
                self.logger.action(act, "defend_hold")
                return act

        # 4) 순찰
        target = self._getBestPatrolTarget(gameState, myPos)
        dist_to_target = self.getMazeDistance(myPos, target)
        self.logger.log("PATROL",
                        target=target,
                        dist=dist_to_target,
                        patrolIdx=self.patrolIdx)
        if dist_to_target <= 1:
            self.patrolIdx = (self.patrolIdx + 1) % len(self.patrolPoints)
            target = self._getBestPatrolTarget(gameState, myPos)
            self.logger.log("PATROL_ADVANCE",
                            new_idx=self.patrolIdx, new_target=target)

        act = aStarSearch(myPos, {target}, walls, self.distancer)
        if act:
            self.logger.action(act, "patrol")
            return act

        actions = [a for a in gameState.getLegalActions(self.index)
                   if a != Directions.STOP]
        chosen = random.choice(actions) if actions else Directions.STOP
        self.logger.action(chosen, "random_fallback")
        return chosen

    def _getBestPatrolTarget(self, gameState, myPos):
        """
        [BUG FIX 6] _getBestPatrolTarget 핑퐁 수정
        이전:
            if getMazeDistance(myPos, boundaryTarget) <= 3: return patrolTarget
            return boundaryTarget
        문제: 거리 3~4 경계 근처에서 true/false 교대 → 무한 진동
              (20,8)→dist=3→patrolTarget반환→North→(20,9)→dist=4→boundaryTarget반환→South
        수정:
            dist <= 1일 때만 patrolTarget 전환 (이미 경계에 도달한 경우만)
            그 외에는 항상 boundaryTarget 반환 → 단일 명확한 목표
        """
        foodList = self.getFoodYouAreDefending(gameState).asList()

        if foodList:
            avgY           = sum(f[1] for f in foodList) / len(foodList)
            boundaryTarget = min(self.boundaryPositions, key=lambda p: abs(p[1] - avgY))
        else:
            boundaryTarget = self.patrolPoints[self.patrolIdx % len(self.patrolPoints)]

        patrolTarget = self.patrolPoints[self.patrolIdx % len(self.patrolPoints)]

        # 핵심 수정: 거리 1 이하일 때만 patrolTarget으로 전환
        dist_to_boundary = self.getMazeDistance(myPos, boundaryTarget)
        if dist_to_boundary <= 1:
            return patrolTarget

        return boundaryTarget

    def safeFleeFrom(self, gameState, threatPos):
        actions = [a for a in gameState.getLegalActions(self.index)
                   if a != Directions.STOP]
        if not actions:
            return Directions.STOP
        best, bestDist = None, -1
        for action in actions:
            newPos = self.getSuccessor(gameState, action).getAgentState(self.index).getPosition()
            d = self.getMazeDistance(newPos, threatPos)
            if d > bestDist:
                bestDist, best = d, action
        best_action = best or random.choice(actions)
        self.logger.action(best_action, "safe_flee")
        return best_action
