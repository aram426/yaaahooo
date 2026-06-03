# myTeam_simple.py
# Simple Reflex Agent to beat baseline
# Start with working solution, then improve

from captureAgents import CaptureAgent
import random
from game import Directions
from util import nearestPoint

def createTeam(firstIndex, secondIndex, isRed,
               first='OffensiveAgent', second='DefensiveAgent'):
    return [eval(first)(firstIndex), eval(second)(secondIndex)]

class ReflexAgent(CaptureAgent):
    """Base reflex agent"""

    def registerInitialState(self, gameState):
        self.start = gameState.getAgentPosition(self.index)
        CaptureAgent.registerInitialState(self, gameState)

    def chooseAction(self, gameState):
        actions = gameState.getLegalActions(self.index)
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
    """Offensive agent that collects food"""

    def getFeatures(self, gameState, action):
        features = util.Counter()
        successor = self.getSuccessor(gameState, action)
        myState = successor.getAgentState(self.index)
        myPos = myState.getPosition()

        # Feature 1: Score is most important
        features['successorScore'] = self.getScore(successor)

        # Feature 2: Distance to food
        foodList = self.getFood(successor).asList()
        if len(foodList) > 0:
            minDistance = min([self.getMazeDistance(myPos, food) for food in foodList])
            features['distanceToFood'] = minDistance

        # Feature 3: Carrying food (encourage return)
        features['carrying'] = myState.numCarrying

        # Feature 4: Enemy ghost proximity (danger)
        enemies = [successor.getAgentState(i) for i in self.getOpponents(successor)]
        ghosts = [a for a in enemies if not a.isPacman and a.getPosition() != None]
        if len(ghosts) > 0 and myState.isPacman:
            dists = [self.getMazeDistance(myPos, a.getPosition()) for a in ghosts]
            features['ghostDistance'] = min(dists)
        else:
            features['ghostDistance'] = 999  # Safe

        # Feature 5: Return home when carrying
        if myState.numCarrying > 0:
            # Get distance to boundary
            walls = gameState.getWalls()
            mid_x = walls.width // 2
            boundary_x = mid_x - 1 if self.red else mid_x
            boundary_positions = [(boundary_x, y) for y in range(1, walls.height - 1)
                                 if not walls[boundary_x][y]]
            if boundary_positions:
                minBoundaryDist = min([self.getMazeDistance(myPos, b) for b in boundary_positions])
                features['returnHome'] = minBoundaryDist

        return features

    def getWeights(self, gameState, action):
        successor = self.getSuccessor(gameState, action)
        myState = successor.getAgentState(self.index)
        features = self.getFeatures(gameState, action)

        # Base weights
        weights = {
            'successorScore': 100,
            'distanceToFood': -1,
            'carrying': 10,  # Increased from 5
            'ghostDistance': 0,
            'returnHome': 0
        }

        # Dynamic weights based on carrying
        if myState.numCarrying >= 5:
            # Lots of food → must return
            weights['returnHome'] = -20
            weights['distanceToFood'] = 0
            weights['carrying'] = 20
        elif myState.numCarrying >= 2:
            # Some food → consider return
            weights['returnHome'] = -5
            weights['distanceToFood'] = -0.5

        # Ghost danger response
        ghost_dist = features['ghostDistance']
        if ghost_dist < 999 and myState.isPacman:
            if ghost_dist <= 2:
                # Immediate danger → RUN!
                weights['ghostDistance'] = 100
                weights['distanceToFood'] = 0
                weights['returnHome'] = -50
            elif ghost_dist <= 4:
                # Close danger → be careful
                weights['ghostDistance'] = 20
                weights['distanceToFood'] = 0
                if myState.numCarrying > 0:
                    weights['returnHome'] = -30

        return weights

class DefensiveAgent(ReflexAgent):
    """Defensive agent that guards territory"""

    def getFeatures(self, gameState, action):
        features = util.Counter()
        successor = self.getSuccessor(gameState, action)
        myState = successor.getAgentState(self.index)
        myPos = myState.getPosition()

        # Feature 1: Not Pacman (stay in own territory)
        features['onDefense'] = 1
        if myState.isPacman:
            features['onDefense'] = 0

        # Feature 2: Number of invaders
        enemies = [successor.getAgentState(i) for i in self.getOpponents(successor)]
        invaders = [a for a in enemies if a.isPacman and a.getPosition() != None]
        features['numInvaders'] = len(invaders)

        # Feature 3: Distance to invaders
        if len(invaders) > 0:
            dists = [self.getMazeDistance(myPos, a.getPosition()) for a in invaders]
            features['invaderDistance'] = min(dists)
        else:
            # No invaders → patrol food
            foodList = self.getFoodYouAreDefending(successor).asList()
            if len(foodList) > 0:
                minFoodDist = min([self.getMazeDistance(myPos, food) for food in foodList])
                features['patrolDistance'] = minFoodDist

        # Feature 4: Stop penalty
        if action == Directions.STOP:
            features['stop'] = 1

        # Feature 5: Reverse penalty
        rev = Directions.REVERSE[gameState.getAgentState(self.index).configuration.direction]
        if action == rev:
            features['reverse'] = 1

        return features

    def getWeights(self, gameState, action):
        return {
            'numInvaders': -1000,   # HATE invaders
            'onDefense': 100,        # Stay on defense
            'invaderDistance': -100, # Chase invaders aggressively (was -10)
            'patrolDistance': -5,    # Patrol near food
            'stop': -100,            # Don't stop
            'reverse': -2            # Don't reverse
        }

# Import util module
import util
