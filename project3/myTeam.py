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
 
#################
# Team creation #
#################
 
def createTeam(firstIndex, secondIndex, isRed,
               first='OffensiveAgent', second='DefensiveAgent'):
    return [eval(first)(firstIndex), eval(second)(secondIndex)]
 
####################
# Shared utilities #
####################
 
def aStarSearch(startPos, goalPositions, walls, distancer, dangerZone=None, dangerCost=20):
    if not goalPositions:
        return None
    from util import PriorityQueue
 
    goalSet = set(goalPositions)
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
                newPos = (nx, ny)
                stepCost = dangerCost if newPos in dangerZone else 1
                newCost = cost + stepCost
                if newPos not in visited or visited.get(newPos, float('inf')) > newCost:
                    frontier.push((newPos, path+[action], newCost), newCost + heuristic(newPos))
    return None
 
 
def getBoundaryPositions(gameState, isRed):
    layout = gameState.data.layout
    width, height = layout.width, layout.height
    walls = gameState.getWalls()
    x = width // 2 - 1 if isRed else width // 2
    return [(x, y) for y in range(1, height-1) if not walls[x][y]]
 
 
####################
# Base Agent Class #
####################
 
class BaseAgent(CaptureAgent):
 
    def registerInitialState(self, gameState):
        CaptureAgent.registerInitialState(self, gameState)
        self.start = gameState.getAgentPosition(self.index)
        self.walls = gameState.getWalls()
        self.width = gameState.data.layout.width
        self.height = gameState.data.layout.height
        self.boundaryPositions = getBoundaryPositions(gameState, self.red)
        self.posHistory = []  # 교착 감지용
 
    def getSuccessor(self, gameState, action):
        successor = gameState.generateSuccessor(self.index, action)
        pos = successor.getAgentState(self.index).getPosition()
        from util import nearestPoint
        if pos != nearestPoint(pos):
            return successor.generateSuccessor(self.index, action)
        return successor
 
    def getEnemyGhosts(self, gameState):
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        return [e for e in enemies if not e.isPacman and e.getPosition() is not None and e.scaredTimer <= 0]
 
    def getScaredGhosts(self, gameState):
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        return [e for e in enemies if not e.isPacman and e.getPosition() is not None and e.scaredTimer > 0]
 
    def getInvaders(self, gameState):
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        return [e for e in enemies if e.isPacman and e.getPosition() is not None]
 
    def buildDangerZone(self, ghosts, radius=2):
        zone = set()
        for g in ghosts:
            gpos = g.getPosition()
            if gpos:
                gx, gy = int(gpos[0]), int(gpos[1])
                for dx in range(-radius, radius+1):
                    for dy in range(-radius, radius+1):
                        nx, ny = gx+dx, gy+dy
                        if 0 <= nx < self.walls.width and 0 <= ny < self.walls.height:
                            if not self.walls[nx][ny]:
                                zone.add((nx, ny))
        return zone
 
    def safeAction(self, gameState):
        actions = [a for a in gameState.getLegalActions(self.index) if a != Directions.STOP]
        myPos = gameState.getAgentState(self.index).getPosition()
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
 
    def isStuck(self, myPos, window=6):
        """최근 window 턴 내에 같은 자리를 반복하면 교착으로 판단."""
        self.posHistory.append(myPos)
        if len(self.posHistory) > window * 2:
            self.posHistory = self.posHistory[-window * 2:]
        if len(self.posHistory) >= window:
            recent = self.posHistory[-window:]
            if recent.count(myPos) >= window // 2:
                return True
        return False
 
    def getScore(self, gameState):
        """팀 관점 점수 (양수=우리가 앞섬)."""
        if self.red:
            return gameState.getScore()
        return -gameState.getScore()
 
    def getRemainingMoves(self, gameState):
        return gameState.data.timeleft
 
 
####################
# Offensive Agent  #
####################
 
class OffensiveAgent(BaseAgent):
 
    CARRY_LIMIT = 5
 
    def registerInitialState(self, gameState):
        BaseAgent.registerInitialState(self, gameState)
        self.carrying = 0
        self.lastFoodCount = len(self.getFood(gameState).asList())
 
    def chooseAction(self, gameState):
        myState = gameState.getAgentState(self.index)
        myPos = myState.getPosition()
        walls = gameState.getWalls()
 
        foodList = self.getFood(gameState).asList()
        currentFoodCount = len(foodList)
        if currentFoodCount < self.lastFoodCount:
            self.carrying += self.lastFoodCount - currentFoodCount
        self.lastFoodCount = currentFoodCount
        if not myState.isPacman:
            self.carrying = 0
 
        ghosts = self.getEnemyGhosts(gameState)
        scaredGhosts = self.getScaredGhosts(gameState)
        capsules = self.getCapsules(gameState)
        dangerZone = self.buildDangerZone(ghosts, radius=2)
        score = self.getScore(gameState)
        timeLeft = self.getRemainingMoves(gameState)
        stuck = self.isStuck(myPos)
 
        # 교착 탈출: 갇혀있으면 캡슐이나 반대쪽 경계로 우회
        if stuck and not myState.isPacman:
            altBoundary = self._getAlternateBoundary(gameState, myPos)
            act = aStarSearch(myPos, {altBoundary}, walls, self.distancer)
            if act: return act
 
        # 0) 시간 부족 + 우리가 앞서면 귀환해서 점수 확정
        if myState.isPacman and self.carrying > 0:
            if timeLeft < 80:
                act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
                if act: return act
 
        # 1) 겁먹은 고스트 추격 (+3점)
        if scaredGhosts and myState.isPacman:
            closest = min(scaredGhosts, key=lambda g: self.getMazeDistance(myPos, g.getPosition()))
            if self.getMazeDistance(myPos, closest.getPosition()) <= 8:
                act = aStarSearch(myPos, {closest.getPosition()}, walls, self.distancer)
                if act: return act
 
        # 2) 긴급: 고스트 3칸 이내
        if myState.isPacman and ghosts:
            danger = [g for g in ghosts if self.getMazeDistance(myPos, g.getPosition()) <= 3]
            if danger:
                if capsules:
                    cap = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                    capDist = self.getMazeDistance(myPos, cap)
                    ghostDist = min(self.getMazeDistance(myPos, g.getPosition()) for g in danger)
                    if capDist < ghostDist:
                        act = aStarSearch(myPos, {cap}, walls, self.distancer)
                        if act: return act
                act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
                if act: return act
                return self.safeAction(gameState)
 
        # 3) 충분히 먹었으면 귀환
        if self.carrying >= self.CARRY_LIMIT and myState.isPacman:
            act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer, dangerZone)
            if act: return act
 
        # 4) 고스트가 경계를 막고 있으면 → 캡슐 먹으러 가거나 다른 진입점 탐색
        if not myState.isPacman and ghosts:
            nearBoundaryGhost = [g for g in ghosts
                                  if any(self.getMazeDistance(g.getPosition(), b) <= 2
                                         for b in self.boundaryPositions)]
            if nearBoundaryGhost:
                if capsules:
                    # 캡슐로 가는 경로가 덜 막힌 진입점 찾기
                    cap = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                    act = aStarSearch(myPos, {cap}, walls, self.distancer, dangerZone)
                    if act: return act
                # 막힌 고스트 위/아래로 우회 진입
                altEntry = self._getUnblockedEntry(gameState, nearBoundaryGhost)
                if altEntry:
                    act = aStarSearch(myPos, {altEntry}, walls, self.distancer)
                    if act: return act
 
        # 5) 고스트 근처면 캡슐 먼저
        if capsules and myState.isPacman and ghosts:
            nearGhost = any(self.getMazeDistance(myPos, g.getPosition()) <= 6 for g in ghosts)
            if nearGhost:
                cap = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                act = aStarSearch(myPos, {cap}, walls, self.distancer, dangerZone)
                if act: return act
 
        # 6) 음식 먹으러 가기
        if foodList:
            targets = capsules + foodList if capsules else foodList
            act = aStarSearch(myPos, set(targets), walls, self.distancer, dangerZone)
            if act: return act
 
        # 7) 최종 fallback
        act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
        if act: return act
 
        actions = [a for a in gameState.getLegalActions(self.index) if a != Directions.STOP]
        return random.choice(actions) if actions else Directions.STOP
 
    def _getAlternateBoundary(self, gameState, myPos):
        """교착 시 현재 위치와 가장 먼 경계 지점 반환."""
        if not self.boundaryPositions:
            return self.start
        return max(self.boundaryPositions, key=lambda p: self.getMazeDistance(myPos, p))
 
    def _getUnblockedEntry(self, gameState, blockingGhosts):
        """고스트가 막지 않는 경계 진입점 중 가장 가까운 것 반환."""
        myPos = gameState.getAgentState(self.index).getPosition()
        freeEntries = []
        for b in self.boundaryPositions:
            blocked = any(self.getMazeDistance(b, g.getPosition()) <= 2 for g in blockingGhosts)
            if not blocked:
                freeEntries.append(b)
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
        n = len(bp)
        if n >= 3:
            self.patrolPoints = [bp[n//4], bp[n//2], bp[3*n//4]]
        elif n > 0:
            self.patrolPoints = bp[:]
        else:
            self.patrolPoints = [self.start]
        self.patrolIdx = 0
 
    def chooseAction(self, gameState):
        myState = gameState.getAgentState(self.index)
        myPos = myState.getPosition()
        walls = gameState.getWalls()
        isScared = myState.scaredTimer > 0
        score = self.getScore(gameState)
        timeLeft = self.getRemainingMoves(gameState)
        stuck = self.isStuck(myPos)
 
        # 음식 변화 감지
        currentFood = set(self.getFoodYouAreDefending(gameState).asList())
        eaten = self.prevFoodDefending - currentFood
        if eaten:
            self.lastEatenPos = list(eaten)[0]
        self.prevFoodDefending = currentFood
 
        invaders = self.getInvaders(gameState)
 
        # 교착 탈출: 같은 경계 지점에 갇히면 다른 패트롤 포인트로
        if stuck:
            self.patrolIdx = (self.patrolIdx + 1) % len(self.patrolPoints)
 
        # ── 1) 침입자 추격 ──────────────────────────────────────
        if invaders:
            closest = min(invaders, key=lambda e: self.getMazeDistance(myPos, e.getPosition()))
            target = closest.getPosition()
 
            if isScared:
                # 겁먹음: 도망가면서 경계 선점
                if self.getMazeDistance(myPos, target) <= 3:
                    return self.safeFleeFrom(gameState, target)
                bp_target = min(self.boundaryPositions,
                                key=lambda p: self.getMazeDistance(p, target))
                act = aStarSearch(myPos, {bp_target}, walls, self.distancer)
                if act: return act
            else:
                # 정상: 추격. 단 경계 너머까지 깊이 들어가지 않도록 제한
                act = aStarSearch(myPos, {target}, walls, self.distancer)
                if act: return act
 
        # ── 2) 음식 사라진 위치로 이동 ──────────────────────────
        if self.lastEatenPos and not invaders:
            if self.getMazeDistance(myPos, self.lastEatenPos) > 1:
                act = aStarSearch(myPos, {self.lastEatenPos}, walls, self.distancer)
                if act: return act
            else:
                self.lastEatenPos = None
 
        # ── 3) 우리가 크게 앞서고 시간 얼마 안남으면 수비 집중 ──
        if score >= 5 and timeLeft < 200:
            # 음식 무게중심 경계 지점에서 완전 수비
            target = self._getBestPatrolTarget(gameState, myPos)
            act = aStarSearch(myPos, {target}, walls, self.distancer)
            if act: return act
 
        # ── 4) 순찰 ─────────────────────────────────────────────
        # 교착 방지: 경계선에서 살짝 안쪽(우리 영역)으로 들어와서 대기
        target = self._getBestPatrolTarget(gameState, myPos)
 
        # 현재 목표에 도달했으면 다음 순찰 포인트
        if self.getMazeDistance(myPos, target) <= 1:
            self.patrolIdx = (self.patrolIdx + 1) % len(self.patrolPoints)
            target = self._getBestPatrolTarget(gameState, myPos)
 
        act = aStarSearch(myPos, {target}, walls, self.distancer)
        if act: return act
 
        actions = [a for a in gameState.getLegalActions(self.index) if a != Directions.STOP]
        return random.choice(actions) if actions else Directions.STOP
 
    def _getBestPatrolTarget(self, gameState, myPos):
        """
        우리 음식 무게중심 y좌표 + 경계 안쪽 1칸 지점.
        교착 방지: 순찰 포인트를 순환.
        """
        foodList = self.getFoodYouAreDefending(gameState).asList()
 
        # 음식 무게중심 기반 경계 지점
        if foodList:
            avgY = sum(f[1] for f in foodList) / len(foodList)
            boundaryTarget = min(self.boundaryPositions, key=lambda p: abs(p[1] - avgY))
        else:
            boundaryTarget = self.patrolPoints[self.patrolIdx % len(self.patrolPoints)]
 
        # 순찰 포인트와 무게중심 지점을 번갈아 사용해서 교착 방지
        patrolTarget = self.patrolPoints[self.patrolIdx % len(self.patrolPoints)]
 
        # 거리가 가까우면 순찰 포인트, 아니면 무게중심
        if self.getMazeDistance(myPos, boundaryTarget) <= 3:
            return patrolTarget
        return boundaryTarget
 
    def safeFleeFrom(self, gameState, threatPos):
        actions = [a for a in gameState.getLegalActions(self.index) if a != Directions.STOP]
        if not actions:
            return Directions.STOP
        best, bestDist = None, -1
        for action in actions:
            newPos = self.getSuccessor(gameState, action).getAgentState(self.index).getPosition()
            d = self.getMazeDistance(newPos, threatPos)
            if d > bestDist:
                bestDist, best = d, action
        return best or random.choice(actions)
 