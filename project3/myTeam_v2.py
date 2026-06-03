# myTeam_v2.py
# Enhanced Reflex Agent to beat otherTeam
# Adding: Dead-end detection, Better escape logic, Scared ghost chasing

from captureAgents import CaptureAgent
import random
from game import Directions
from util import nearestPoint
import util

def createTeam(firstIndex, secondIndex, isRed,
               first='OffensiveAgent', second='DefensiveAgent'):
    return [eval(first)(firstIndex), eval(second)(secondIndex)]

class ReflexAgent(CaptureAgent):
    """Enhanced base reflex agent"""

    def registerInitialState(self, gameState):
        self.start = gameState.getAgentPosition(self.index)
        CaptureAgent.registerInitialState(self, gameState)

        # Enhanced tracking
        self.walls = gameState.getWalls()
        self.posHistory = []
        self.deadEnds = self.getDeadEnds(gameState.getWalls())
        self.lastFoodCount = len(self.getFood(gameState).asList())
        self.carrying = 0

    def getDeadEnds(self, walls):
        """Find dead-end cells (cells with only 1 neighbor)"""
        width, height = walls.width, walls.height

        def neighbors(x, y):
            result = []
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and not walls[nx][ny]:
                    result.append((nx, ny))
            return result

        deadEnds = set()
        queue = []

        # Find initial dead ends (1 neighbor)
        for x in range(width):
            for y in range(height):
                if not walls[x][y]:
                    nbrs = neighbors(x, y)
                    if len(nbrs) == 1:
                        deadEnds.add((x, y))
                        queue.append((x, y))

        # Propagate dead ends
        i = 0
        while i < len(queue):
            cx, cy = queue[i]
            i += 1
            for nx, ny in neighbors(cx, cy):
                if (nx, ny) not in deadEnds:
                    liveNeighbors = [p for p in neighbors(nx, ny) if p not in deadEnds]
                    if len(liveNeighbors) == 1:
                        deadEnds.add((nx, ny))
                        queue.append((nx, ny))

        return deadEnds

    def isStuck(self, myPos, window=8):
        """Detect if agent is stuck in a loop"""
        self.posHistory.append(myPos)
        if len(self.posHistory) > window * 2:
            self.posHistory = self.posHistory[-window * 2:]

        if len(self.posHistory) >= window:
            recent = self.posHistory[-window:]
            if recent.count(myPos) >= window // 2:  # 50% threshold
                return True
        return False

    def chooseAction(self, gameState):
        actions = gameState.getLegalActions(self.index)

        # Track carrying
        myState = gameState.getAgentState(self.index)
        foodList = self.getFood(gameState).asList()
        currentFoodCount = len(foodList)

        if currentFoodCount < self.lastFoodCount:
            self.carrying += self.lastFoodCount - currentFoodCount
        self.lastFoodCount = currentFoodCount

        if not myState.isPacman:
            self.carrying = 0

        # Check stuck
        myPos = myState.getPosition()
        stuck = self.isStuck(myPos)

        # Stuck escape - try random different action
        if stuck:
            actions = [a for a in actions if a != Directions.STOP]
            if len(actions) > 1:
                return random.choice(actions)

        values = [self.evaluate(gameState, a) for a in actions]
        maxValue = max(values)
        bestActions = [a for a, v in zip(actions, values) if v == maxValue]
        return random.choice(bestActions)

    def getSuccessor(self, gameState, action):
        successor = gameState.generateSuccessor(self.index, action)
        pos = successor.getAgentState(self.index).getPosition()
        if pos != nearestPoint(pos):
            return successor.generateSuccessor(self.index, action)
        else:
            return successor

    def evaluate(self, gameState, action):
        features = self.getFeatures(gameState, action)
        weights = self.getWeights(gameState, action)
        return features * weights

class OffensiveAgent(ReflexAgent):
    """Enhanced offensive agent"""

    def getFeatures(self, gameState, action):
        features = util.Counter()
        successor = self.getSuccessor(gameState, action)
        myState = successor.getAgentState(self.index)
        myPos = myState.getPosition()

        # Feature 1: Score
        features['successorScore'] = self.getScore(successor)

        # Feature 2: Distance to food
        foodList = self.getFood(successor).asList()
        if len(foodList) > 0:
            minDistance = min([self.getMazeDistance(myPos, food) for food in foodList])
            features['distanceToFood'] = minDistance

        # Feature 3: Carrying (dynamic)
        features['carrying'] = self.carrying

        # Feature 4: Enemy ghost proximity
        enemies = [successor.getAgentState(i) for i in self.getOpponents(successor)]
        ghosts = [a for a in enemies if not a.isPacman and a.getPosition() != None and a.scaredTimer <= 0]
        scaredGhosts = [a for a in enemies if not a.isPacman and a.getPosition() != None and a.scaredTimer > 0]

        if len(ghosts) > 0 and myState.isPacman:
            dists = [self.getMazeDistance(myPos, a.getPosition()) for a in ghosts]
            minDist = min(dists)
            features['ghostDistance'] = minDist

            # Dead-end danger multiplier
            if myPos in self.deadEnds:
                features['deadEndDanger'] = 1 if minDist < 4 else 0
        else:
            features['ghostDistance'] = 999

        # Feature 5: Return home
        if self.carrying > 0:
            walls = gameState.getWalls()
            mid_x = walls.width // 2
            boundary_x = mid_x - 1 if self.red else mid_x
            boundary_positions = [(boundary_x, y) for y in range(1, walls.height - 1)
                                 if not walls[boundary_x][y]]
            if boundary_positions:
                minBoundaryDist = min([self.getMazeDistance(myPos, b) for b in boundary_positions])
                features['returnHome'] = minBoundaryDist

        # Feature 6: Scared ghost hunting
        if len(scaredGhosts) > 0 and myState.isPacman and self.carrying < 5:
            dists = [self.getMazeDistance(myPos, a.getPosition()) for a in scaredGhosts]
            features['scaredGhostDistance'] = min(dists)

        # Feature 7: Capsule proximity
        capsules = self.getCapsules(successor)
        if capsules and myState.isPacman and ghosts:
            minCapsuleDist = min([self.getMazeDistance(myPos, c) for c in capsules])
            features['capsuleDistance'] = minCapsuleDist

        # Feature 8: Time pressure
        timeLeft = gameState.data.timeleft
        if timeLeft < 100 and self.carrying > 0:
            features['timePressure'] = 1

        return features

    def getWeights(self, gameState, action):
        successor = self.getSuccessor(gameState, action)
        myState = successor.getAgentState(self.index)
        features = self.getFeatures(gameState, action)

        weights = {
            'successorScore': 100,
            'distanceToFood': -1,
            'carrying': 15,  # Increased from 10
            'ghostDistance': 0,
            'returnHome': 0,
            'scaredGhostDistance': 0,
            'capsuleDistance': 0,
            'deadEndDanger': 0,
            'timePressure': 0
        }

        # Time pressure override
        if 'timePressure' in features and features['timePressure'] > 0:
            weights['returnHome'] = -100
            weights['distanceToFood'] = 0
            weights['carrying'] = 50

        # Carrying-based strategy
        if self.carrying >= 8:
            # High carry - must return
            weights['returnHome'] = -30
            weights['distanceToFood'] = 0
            weights['carrying'] = 30
            weights['scaredGhostDistance'] = 0
        elif self.carrying >= 5:
            # Medium carry - prioritize return
            weights['returnHome'] = -15
            weights['distanceToFood'] = -0.3
            weights['carrying'] = 20
        elif self.carrying >= 2:
            # Low carry - consider return
            weights['returnHome'] = -3
            weights['distanceToFood'] = -0.7

        # Ghost danger response
        ghost_dist = features['ghostDistance']
        if ghost_dist < 999 and myState.isPacman:
            if ghost_dist <= 2:
                # Immediate danger
                weights['ghostDistance'] = 200
                weights['distanceToFood'] = 0
                weights['returnHome'] = -100
                weights['scaredGhostDistance'] = 0
                # Capsule becomes priority
                if 'capsuleDistance' in features and features['capsuleDistance'] < ghost_dist:
                    weights['capsuleDistance'] = -150
            elif ghost_dist <= 4:
                # Close danger
                weights['ghostDistance'] = 50
                weights['distanceToFood'] = 0
                if self.carrying > 0:
                    weights['returnHome'] = -40
                if 'capsuleDistance' in features:
                    weights['capsuleDistance'] = -30
            elif ghost_dist <= 6 and self.carrying >= 1:
                # Medium danger with food
                weights['ghostDistance'] = 10
                weights['returnHome'] = -10

        # Dead-end danger
        if 'deadEndDanger' in features and features['deadEndDanger'] > 0:
            weights['deadEndDanger'] = -500  # Huge penalty

        # Scared ghost hunting
        if 'scaredGhostDistance' in features and features['scaredGhostDistance'] < 999:
            if self.carrying < 5 and features['scaredGhostDistance'] < 8:
                weights['scaredGhostDistance'] = -20
                weights['distanceToFood'] = -0.5

        return weights

class DefensiveAgent(ReflexAgent):
    """Enhanced defensive agent"""

    def getFeatures(self, gameState, action):
        features = util.Counter()
        successor = self.getSuccessor(gameState, action)
        myState = successor.getAgentState(self.index)
        myPos = myState.getPosition()

        # Feature 1: Stay on defense
        features['onDefense'] = 1
        if myState.isPacman:
            features['onDefense'] = 0

        # Feature 2: Invaders
        enemies = [successor.getAgentState(i) for i in self.getOpponents(successor)]
        invaders = [a for a in enemies if a.isPacman and a.getPosition() != None]
        features['numInvaders'] = len(invaders)

        # Feature 3: Distance to invaders
        if len(invaders) > 0:
            dists = [self.getMazeDistance(myPos, a.getPosition()) for a in invaders]
            features['invaderDistance'] = min(dists)
        else:
            # Patrol food
            foodList = self.getFoodYouAreDefending(successor).asList()
            if len(foodList) > 0:
                # Get most exposed food (closest to boundary)
                walls = gameState.getWalls()
                mid_x = walls.width // 2

                exposedFood = sorted(foodList,
                                    key=lambda f: abs(f[0] - mid_x))[:5]  # Top 5 exposed

                minFoodDist = min([self.getMazeDistance(myPos, food) for food in exposedFood])
                features['patrolDistance'] = minFoodDist

        # Feature 4: Stop/reverse penalty
        if action == Directions.STOP:
            features['stop'] = 1

        rev = Directions.REVERSE[gameState.getAgentState(self.index).configuration.direction]
        if action == rev:
            features['reverse'] = 1

        return features

    def getWeights(self, gameState, action):
        return {
            'numInvaders': -1000,
            'onDefense': 100,
            'invaderDistance': -150,  # More aggressive (was -100)
            'patrolDistance': -10,    # More active patrol (was -5)
            'stop': -150,             # Stronger stop penalty
            'reverse': -3
        }
