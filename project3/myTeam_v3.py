# myTeam_v3.py
# A* Search based approach to compete with otherTeam
# Key: Smart pathfinding > Simple reflexes

from captureAgents import CaptureAgent
import random
from game import Directions
from util import PriorityQueue
import util

def createTeam(firstIndex, secondIndex, isRed,
               first='OffensiveAgent', second='DefensiveAgent'):
    return [eval(first)(firstIndex), eval(second)(secondIndex)]

def aStarSearch(startPos, goalPositions, walls, distancer, dangerZone=None):
    """A* pathfinding with danger zone avoidance"""
    if not goalPositions:
        return None

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
        for dx, dy, action in [(0,1,Directions.NORTH), (0,-1,Directions.SOUTH),
                                (1,0,Directions.EAST), (-1,0,Directions.WEST)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < walls.width and 0 <= ny < walls.height and not walls[nx][ny]:
                newPos = (nx, ny)
                # Danger zones cost more
                stepCost = 20 if newPos in dangerZone else 1
                newCost = cost + stepCost

                if newPos not in visited or visited.get(newPos, float('inf')) > newCost:
                    frontier.push((newPos, path + [action], newCost),
                                newCost + heuristic(newPos))

    return None

def getBoundaryPositions(gameState, isRed):
    """Get boundary positions"""
    walls = gameState.getWalls()
    width, height = walls.width, walls.height
    x = width // 2 - 1 if isRed else width // 2
    return [(x, y) for y in range(1, height - 1) if not walls[x][y]]

class BaseAgent(CaptureAgent):
    """Base agent with A* pathfinding"""

    def registerInitialState(self, gameState):
        CaptureAgent.registerInitialState(self, gameState)
        self.start = gameState.getAgentPosition(self.index)
        self.walls = gameState.getWalls()
        self.boundaryPositions = getBoundaryPositions(gameState, self.red)
        self.carrying = 0
        self.lastFoodCount = len(self.getFood(gameState).asList())
        self.posHistory = []

    def getEnemyGhosts(self, gameState):
        """Get non-scared enemy ghosts"""
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        return [e for e in enemies
                if not e.isPacman and e.getPosition() is not None
                and e.scaredTimer <= 0]

    def getScaredGhosts(self, gameState):
        """Get scared enemy ghosts"""
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        return [e for e in enemies
                if not e.isPacman and e.getPosition() is not None
                and e.scaredTimer > 0]

    def buildDangerZone(self, ghosts, radius=2):
        """Build danger zone around ghosts"""
        zone = set()
        for g in ghosts:
            gpos = g.getPosition()
            if gpos:
                gx, gy = int(gpos[0]), int(gpos[1])
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        nx, ny = gx + dx, gy + dy
                        if (0 <= nx < self.walls.width
                                and 0 <= ny < self.walls.height
                                and not self.walls[nx][ny]):
                            zone.add((nx, ny))
        return zone

    def isStuck(self, myPos, window=8):
        """Detect stuck state"""
        self.posHistory.append(myPos)
        if len(self.posHistory) > window * 2:
            self.posHistory = self.posHistory[-window * 2:]

        if len(self.posHistory) >= window:
            recent = self.posHistory[-window:]
            if recent.count(myPos) >= window // 2:
                return True
        return False

class OffensiveAgent(BaseAgent):
    """A* based offensive agent"""

    CARRY_LIMIT = 5
    GHOST_FLEE_DIST = 5

    def chooseAction(self, gameState):
        myState = gameState.getAgentState(self.index)
        myPos = myState.getPosition()
        walls = gameState.getWalls()

        # Track carrying
        foodList = self.getFood(gameState).asList()
        currentCount = len(foodList)
        if currentCount < self.lastFoodCount:
            self.carrying += self.lastFoodCount - currentCount
        self.lastFoodCount = currentCount
        if not myState.isPacman:
            self.carrying = 0

        # Get threats
        ghosts = self.getEnemyGhosts(gameState)
        scaredGhosts = self.getScaredGhosts(gameState)
        capsules = self.getCapsules(gameState)
        dangerZone = self.buildDangerZone(ghosts, radius=2)

        # Stuck escape
        stuck = self.isStuck(myPos)
        if stuck and not myState.isPacman:
            # Try alternate boundary
            if len(self.boundaryPositions) > 1:
                far_boundary = max(self.boundaryPositions,
                                  key=lambda b: self.getMazeDistance(myPos, b))
                act = aStarSearch(myPos, {far_boundary}, walls, self.distancer)
                if act and act != Directions.STOP:
                    return act

        # Priority 0: Time pressure
        timeLeft = gameState.data.timeleft
        if myState.isPacman and self.carrying > 0 and timeLeft < 80:
            act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
            if act:
                return act

        # Priority 1: Chase scared ghosts (high value)
        if scaredGhosts and myState.isPacman and self.carrying < self.CARRY_LIMIT:
            closest = min(scaredGhosts,
                         key=lambda g: self.getMazeDistance(myPos, g.getPosition()))
            if self.getMazeDistance(myPos, closest.getPosition()) <= 8:
                act = aStarSearch(myPos, {closest.getPosition()}, walls, self.distancer)
                if act:
                    return act

        # Priority 2: Emergency flee (ghost within 3)
        if myState.isPacman and ghosts:
            danger = [g for g in ghosts
                     if self.getMazeDistance(myPos, g.getPosition()) <= 3]
            if danger:
                # Try capsule first
                if capsules:
                    cap = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                    capDist = self.getMazeDistance(myPos, cap)
                    ghostDist = min(self.getMazeDistance(myPos, g.getPosition()) for g in danger)
                    if capDist < ghostDist:
                        act = aStarSearch(myPos, {cap}, walls, self.distancer)
                        if act:
                            return act

                # Flee to boundary
                act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer, dangerZone)
                if act:
                    return act

                # Last resort: run away
                actions = gameState.getLegalActions(self.index)
                actions = [a for a in actions if a != Directions.STOP]
                if actions:
                    # Pick action that maximizes distance from nearest ghost
                    best_act = max(actions,
                                  key=lambda a: min(
                                      self.getMazeDistance(
                                          self.getSuccessor(gameState, a).getAgentState(self.index).getPosition(),
                                          g.getPosition()
                                      ) for g in danger
                                  ))
                    return best_act

        # Priority 3: Carrying flee logic
        if myState.isPacman and self.carrying >= 1 and ghosts:
            closest_ghost = min(ghosts,
                               key=lambda g: self.getMazeDistance(myPos, g.getPosition()))
            ghost_dist = self.getMazeDistance(myPos, closest_ghost.getPosition())
            closest_boundary = min(self.boundaryPositions,
                                  key=lambda b: self.getMazeDistance(myPos, b))
            escape_dist = self.getMazeDistance(myPos, closest_boundary)

            # Flee if ghost is close
            should_flee = (ghost_dist <= self.GHOST_FLEE_DIST) or \
                         (self.carrying >= self.CARRY_LIMIT)

            if should_flee:
                act = aStarSearch(myPos, set(self.boundaryPositions),
                                walls, self.distancer, dangerZone)
                if act:
                    return act

        # Priority 4: Carry limit reached
        if self.carrying >= self.CARRY_LIMIT and myState.isPacman:
            act = aStarSearch(myPos, set(self.boundaryPositions),
                            walls, self.distancer, dangerZone)
            if act:
                return act

        # Priority 5: Get capsule if ghost nearby
        if capsules and myState.isPacman and ghosts:
            nearGhost = any(self.getMazeDistance(myPos, g.getPosition()) <= 6
                           for g in ghosts)
            if nearGhost:
                cap = min(capsules, key=lambda c: self.getMazeDistance(myPos, c))
                act = aStarSearch(myPos, {cap}, walls, self.distancer, dangerZone)
                if act:
                    return act

        # Priority 6: Collect food
        if foodList:
            # Filter safe food (avoid danger zones)
            if ghosts and dangerZone:
                safe_food = [f for f in foodList if f not in dangerZone]
                targets = safe_food if safe_food else foodList
            else:
                targets = foodList

            act = aStarSearch(myPos, set(targets), walls, self.distancer, dangerZone)
            if act:
                return act

        # Priority 7: Enter enemy territory
        if not myState.isPacman:
            # Find safe entry
            if ghosts:
                safe_entries = [b for b in self.boundaryPositions
                               if all(self.getMazeDistance(b, g.getPosition()) >= 4
                                     for g in ghosts)]
                if safe_entries:
                    target = min(safe_entries,
                               key=lambda b: self.getMazeDistance(myPos, b))
                    act = aStarSearch(myPos, {target}, walls, self.distancer)
                    if act and act != Directions.STOP:
                        return act

            # Try any boundary
            act = aStarSearch(myPos, set(self.boundaryPositions), walls, self.distancer)
            if act and act != Directions.STOP:
                return act

        # Fallback
        actions = [a for a in gameState.getLegalActions(self.index)
                  if a != Directions.STOP]
        return random.choice(actions) if actions else Directions.STOP

    def getSuccessor(self, gameState, action):
        successor = gameState.generateSuccessor(self.index, action)
        return successor

class DefensiveAgent(BaseAgent):
    """A* based defensive agent"""

    def chooseAction(self, gameState):
        myState = gameState.getAgentState(self.index)
        myPos = myState.getPosition()
        walls = gameState.getWalls()

        # Get invaders
        enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
        invaders = [e for e in enemies if e.isPacman and e.getPosition() is not None]

        # Priority 1: Chase invaders
        if invaders:
            target = min(invaders, key=lambda i: self.getMazeDistance(myPos, i.getPosition()))
            act = aStarSearch(myPos, {target.getPosition()}, walls, self.distancer)
            if act:
                return act

        # Priority 2: Patrol exposed food
        foodList = self.getFoodYouAreDefending(gameState).asList()
        if foodList and not myState.isPacman:
            # Get food closest to boundary (most exposed)
            mid_x = walls.width // 2
            exposed_food = sorted(foodList, key=lambda f: abs(f[0] - mid_x))[:5]

            target = min(exposed_food, key=lambda f: self.getMazeDistance(myPos, f))
            act = aStarSearch(myPos, {target}, walls, self.distancer)
            if act and act != Directions.STOP:
                return act

        # Priority 3: Patrol boundary
        if self.boundaryPositions:
            target = min(self.boundaryPositions,
                        key=lambda b: self.getMazeDistance(myPos, b))
            act = aStarSearch(myPos, {target}, walls, self.distancer)
            if act and act != Directions.STOP:
                return act

        # Fallback
        actions = [a for a in gameState.getLegalActions(self.index)
                  if a != Directions.STOP]
        return random.choice(actions) if actions else Directions.STOP
