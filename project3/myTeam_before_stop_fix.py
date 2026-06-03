# myTeam.py
# Single-Agent MCTS Implementation

from captureAgents import CaptureAgent
import random, time, math
from game import Directions
import util

def createTeam(firstIndex, secondIndex, isRed,
               first='MCTSAgent', second='MCTSAgent'):
    return [eval(first)(firstIndex), eval(second)(secondIndex)]

#################
# A* Pathfinding
#################

def aStarSearch(start, goal, gameState, walls):
    """
    A* search to find path from start to goal position.
    Returns list of positions (including start and goal).
    """
    from util import PriorityQueue

    def heuristic(pos):
        return abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])

    frontier = PriorityQueue()
    frontier.push((start, [start]), heuristic(start))
    explored = set()

    while not frontier.isEmpty():
        current, path = frontier.pop()

        if current == goal:
            return path

        if current in explored:
            continue

        explored.add(current)

        # Explore neighbors
        x, y = current
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            next_pos = (x + dx, y + dy)

            # Check bounds and walls
            if (next_pos[0] < 0 or next_pos[0] >= walls.width or
                next_pos[1] < 0 or next_pos[1] >= walls.height):
                continue
            if walls[next_pos[0]][next_pos[1]]:
                continue
            if next_pos in explored:
                continue

            new_path = path + [next_pos]
            priority = len(new_path) + heuristic(next_pos)
            frontier.push((next_pos, new_path), priority)

    return None  # No path found

def findNearestBoundaryCrossing(start, walls, isRed):
    """
    Find the nearest boundary crossing point from start position.
    Returns the boundary position and path to it.
    """
    mid_x = walls.width // 2
    boundary_x = mid_x - 1 if isRed else mid_x

    # Get all valid boundary positions
    boundary_positions = []
    for y in range(1, walls.height - 1):
        if not walls[boundary_x][y]:
            boundary_positions.append((boundary_x, y))

    if not boundary_positions:
        return None, None

    # Find closest boundary point using actual pathfinding
    best_path = None
    best_length = float('inf')

    for boundary_pos in boundary_positions:
        path = aStarSearch(start, boundary_pos, None, walls)
        if path and len(path) < best_length:
            best_path = path
            best_length = len(path)

    return best_path[0] if best_path and len(best_path) > 1 else None, best_path

class MCTSNode:
    """MCTS Node for single-agent tree search"""
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action  # Single action (not joint)
        self.children = []
        self.visits = 0
        self.total_reward = 0.0
        self.untried_actions = None

    def is_fully_expanded(self):
        return self.untried_actions is not None and len(self.untried_actions) == 0

    def is_terminal(self):
        return self.state.isOver()

    def ucb_score(self, exploration_constant=1.41):
        if self.visits == 0:
            return float('inf')
        if self.parent is None:
            return 0.0
        exploit = self.total_reward / self.visits
        explore = exploration_constant * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploit + explore

class MCTSAgent(CaptureAgent):
    def __init__(self, index, timeForComputing=0.1):
        super().__init__(index, timeForComputing)
        self.tree_root = None
        self.exploration_constant = 1.41
        self.rollout_depth = 10
        self.time_budget = 0.3

        # Role assignment
        self.role = 'offensive' if index in [0, 1] else 'defensive'

        # A* pathfinding cache
        self.cached_path = None
        self.path_target = None

        # Defensive patrol state
        self.patrol_target = None
        self.patrol_direction = 1  # 1 = North, -1 = South

    def registerInitialState(self, gameState):
        CaptureAgent.registerInitialState(self, gameState)
        self.start = gameState.getAgentPosition(self.index)
        self.walls = gameState.getWalls()
        self.move_count = 0

        # Pre-compute path to boundary for ALL agents (they all need to cross eventually)
        next_pos, path = findNearestBoundaryCrossing(self.start, self.walls, self.red)
        if path:
            print(f"Agent {self.index} ({self.role}) initialized - Path to boundary: {len(path)} steps")
            self.cached_path = path
        else:
            print(f"Agent {self.index} ({self.role}) initialized - WARNING: No path to boundary found!")

    def chooseAction(self, gameState):
        """Single-agent MCTS: only considers this agent's actions"""
        start_time = time.time()
        self.move_count += 1

        myPos = gameState.getAgentPosition(self.index)
        myState = gameState.getAgentState(self.index)
        legal_actions = gameState.getLegalActions(self.index)

        # Debug: Show we're being called
        if self.move_count % 10 == 1:
            print(f"[Agent {self.index}] Move {self.move_count}, pos={myPos}, isPacman={myState.isPacman}")

        # OFFENSIVE: Use A* to reach enemy territory
        if self.role == 'offensive' and not myState.isPacman:
            walls = gameState.getWalls()
            mid_x = walls.width // 2

            # Use cached path if available
            if self.cached_path and len(self.cached_path) > 1:
                try:
                    current_idx = self.cached_path.index(myPos)
                    if current_idx < len(self.cached_path) - 1:
                        next_pos = self.cached_path[current_idx + 1]
                        action = self._get_direction_to(myPos, next_pos)
                        if action in legal_actions:
                            if self.move_count % 10 == 1:
                                print(f"[Agent {self.index}] Following A* path to {next_pos}")
                            return action
                except ValueError:
                    pass

            # Recompute path if needed
            next_pos, new_path = findNearestBoundaryCrossing(myPos, walls, self.red)
            if new_path and len(new_path) > 1:
                self.cached_path = new_path
                next_pos = new_path[1]
                action = self._get_direction_to(myPos, next_pos)
                if action in legal_actions:
                    if self.move_count % 10 == 1:
                        print(f"[Agent {self.index}] New A* path: {len(new_path)} steps")
                    return action

        # DEFENSIVE: Patrol home territory
        elif self.role == 'defensive':
            # Check for invaders first
            enemies = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
            invaders = [e for e in enemies if e.isPacman and e.getPosition() is not None]

            if invaders:
                # Chase closest invader using A*
                closest_invader = min(invaders, key=lambda e: self._manhattan(myPos, e.getPosition()))
                target = closest_invader.getPosition()

                # Use A* for smart pathfinding to invader
                walls = gameState.getWalls()
                path = aStarSearch(myPos, target, gameState, walls)
                if path and len(path) > 1:
                    next_pos = path[1]
                    action = self._get_direction_to(myPos, next_pos)
                    if action in legal_actions:
                        if self.move_count % 10 == 1:
                            print(f"[Agent {self.index}] Chasing invader at {target}")
                        return action
            else:
                # No invaders - patrol along boundary
                boundary = self._get_boundary(gameState)
                if boundary:
                    walls = gameState.getWalls()

                    # Check if we're at boundary (our x-coordinate matches boundary x)
                    boundary_x = boundary[0][0] if boundary else None
                    at_boundary = (myPos[0] == boundary_x)

                    if at_boundary:
                        # We're at boundary - patrol up and down
                        boundary_y_values = [b[1] for b in boundary]
                        min_y, max_y = min(boundary_y_values), max(boundary_y_values)

                        # Check if we're near an edge and need to reverse
                        if myPos[1] >= max_y - 1:
                            self.patrol_direction = -1  # Go south
                        elif myPos[1] <= min_y + 1:
                            self.patrol_direction = 1  # Go north

                        # Simple patrol: just move North or South along boundary
                        if self.patrol_direction > 0:
                            # Going north
                            if Directions.NORTH in legal_actions:
                                if self.move_count % 20 == 1:
                                    print(f"[Agent {self.index}] Patrolling north at boundary")
                                return Directions.NORTH
                        else:
                            # Going south
                            if Directions.SOUTH in legal_actions:
                                if self.move_count % 20 == 1:
                                    print(f"[Agent {self.index}] Patrolling south at boundary")
                                return Directions.SOUTH

                        # If can't move in desired direction, reverse
                        if self.patrol_direction > 0:
                            self.patrol_direction = -1
                            if Directions.SOUTH in legal_actions:
                                return Directions.SOUTH
                        else:
                            self.patrol_direction = 1
                            if Directions.NORTH in legal_actions:
                                return Directions.NORTH

                    else:
                        # Not at boundary yet - use A* to get there
                        mid_y = walls.height // 2
                        patrol_points = [b for b in boundary if abs(b[1] - mid_y) < walls.height // 4]
                        if not patrol_points:
                            patrol_points = boundary

                        # Find closest boundary point using A*
                        best_path = None
                        best_length = float('inf')
                        for target in patrol_points[:5]:
                            path = aStarSearch(myPos, target, gameState, walls)
                            if path and len(path) < best_length:
                                best_path = path
                                best_length = len(path)

                        if best_path and len(best_path) > 1:
                            next_pos = best_path[1]
                            action = self._get_direction_to(myPos, next_pos)
                            if action in legal_actions:
                                if self.move_count % 20 == 1:
                                    print(f"[Agent {self.index}] Moving to boundary")
                                return action

        # Initialize tree
        self.tree_root = MCTSNode(gameState)

        # Run MCTS
        num_rollouts = 0
        while time.time() - start_time < self.time_budget:
            node = self._select(self.tree_root)
            if not node.is_terminal() and node.visits > 0:
                node = self._expand(node)
            reward = self._simulate(node.state)
            self._backpropagate(node, reward)
            num_rollouts += 1

        # Select best action
        if not self.tree_root.children:
            return self._safe_fallback(gameState)

        best_child = max(self.tree_root.children, key=lambda c: c.visits)
        action = best_child.action

        elapsed = time.time() - start_time
        print(f"Agent {self.index}: {num_rollouts} rollouts in {elapsed:.3f}s, action={action}")

        return action if action in legal_actions else self._safe_fallback(gameState)

    def _select(self, node):
        while not node.is_terminal() and node.is_fully_expanded():
            node = max(node.children, key=lambda c: c.ucb_score(self.exploration_constant))
        return node

    def _expand(self, node):
        """Expand with SINGLE action for this agent only"""
        if node.untried_actions is None:
            node.untried_actions = node.state.getLegalActions(self.index)
            random.shuffle(node.untried_actions)

        if not node.untried_actions:
            return node

        action = node.untried_actions.pop()

        # Generate successor: apply this agent's action + model other agents
        successor_state = self._apply_action_with_others(node.state, action)

        child = MCTSNode(successor_state, parent=node, action=action)
        node.children.append(child)
        return child

    def _apply_action_with_others(self, state, my_action):
        """Apply my action along with modeled actions for all other agents"""
        current_state = state

        for agent_idx in range(state.getNumAgents()):
            if current_state.isOver():
                break

            try:
                if agent_idx == self.index:
                    action = my_action
                else:
                    # Model other agents with simple policy
                    legal = current_state.getLegalActions(agent_idx)
                    if not legal:
                        continue

                    agent_state = current_state.getAgentState(agent_idx)

                    # Teammate: help offense/defense
                    if agent_idx in self.getTeam(current_state):
                        action = self._teammate_policy(current_state, agent_idx)
                    # Opponent: model as pursuing/defending
                    else:
                        action = self._opponent_policy(current_state, agent_idx)

                current_state = current_state.generateSuccessor(agent_idx, action)
            except:
                continue

        return current_state

    def _simulate(self, state):
        """Fast rollout to depth limit"""
        current_state = state
        depth = 0

        while depth < self.rollout_depth and not current_state.isOver():
            for agent_idx in range(current_state.getNumAgents()):
                if current_state.isOver():
                    break

                try:
                    legal = current_state.getLegalActions(agent_idx)
                    if not legal:
                        continue

                    if agent_idx in self.getTeam(current_state):
                        action = self._teammate_policy(current_state, agent_idx)
                    else:
                        action = self._opponent_policy(current_state, agent_idx)

                    current_state = current_state.generateSuccessor(agent_idx, action)
                except:
                    continue

            depth += 1

        return self._evaluate_state(current_state)

    def _backpropagate(self, node, reward):
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            node = node.parent

    def _evaluate_state(self, state):
        """Evaluate state from this agent's perspective"""
        score = state.getScore()
        if not self.red:
            score = -score

        reward = score * 10  # Base score is most important

        # Add positional heuristics
        myPos = state.getAgentPosition(self.index)
        if myPos is None:
            return reward

        myState = state.getAgentState(self.index)
        walls = state.getWalls()
        mid_x = walls.width // 2

        # Reward being Pacman
        if myState.isPacman:
            reward += 10.0

            # Reward food proximity
            food = self.getFood(state).asList()
            if food:
                try:
                    min_dist = min([self.distancer.getDistance(myPos, f) for f in food])
                    reward += (100 - min_dist) * 0.1
                except:
                    min_dist = min([self._manhattan(myPos, f) for f in food])
                    reward += (100 - min_dist) * 0.05

            # Reward carrying food
            reward += myState.numCarrying * 2.0

            # Return home if carrying enough
            if myState.numCarrying >= 5:
                boundary = self._get_boundary(state)
                if boundary:
                    min_boundary_dist = min([self._manhattan(myPos, b) for b in boundary])
                    reward += (50 - min_boundary_dist) * 0.3

        # Ghost mode - encourage forward progress for offensive agents
        else:
            if self.role == 'offensive':
                # Strong reward for x progress towards enemy
                if self.red:
                    reward += myPos[0] * myPos[0] * 0.1  # Quadratic
                else:
                    x_from_right = (walls.width - myPos[0])
                    reward += x_from_right * x_from_right * 0.1

        return reward

    def _teammate_policy(self, state, agent_idx):
        """Model teammate behavior"""
        myPos = state.getAgentPosition(agent_idx)
        if myPos is None:
            return Directions.STOP

        myState = state.getAgentState(agent_idx)
        legal = state.getLegalActions(agent_idx)

        # Simple: go towards food if Pacman, defend if ghost
        if myState.isPacman:
            food = self.getFood(state).asList()
            if food:
                target = min(food, key=lambda f: self._manhattan(myPos, f))
                return self._move_towards(myPos, target, state, agent_idx)

        return random.choice([a for a in legal if a != Directions.STOP]) if legal else Directions.STOP

    def _opponent_policy(self, state, agent_idx):
        """Model opponent behavior"""
        oppPos = state.getAgentPosition(agent_idx)
        if oppPos is None:
            return Directions.STOP

        legal = state.getLegalActions(agent_idx)

        # Simple model: opponents chase our Pacmen
        our_agents = self.getTeam(state)
        for i in our_agents:
            pos = state.getAgentPosition(i)
            if pos and state.getAgentState(i).isPacman:
                return self._move_towards(oppPos, pos, state, agent_idx)

        return random.choice(legal) if legal else Directions.STOP

    def _safe_fallback(self, gameState):
        legal = gameState.getLegalActions(self.index)
        legal = [a for a in legal if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _get_direction_to(self, fromPos, toPos):
        """Convert position difference to Direction"""
        dx = toPos[0] - fromPos[0]
        dy = toPos[1] - fromPos[1]

        if dx > 0:
            return Directions.EAST
        elif dx < 0:
            return Directions.WEST
        elif dy > 0:
            return Directions.NORTH
        elif dy < 0:
            return Directions.SOUTH
        else:
            return Directions.STOP

    def _manhattan(self, pos1, pos2):
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _move_towards(self, fromPos, toPos, state, agent_idx):
        dx = toPos[0] - fromPos[0]
        dy = toPos[1] - fromPos[1]

        if abs(dx) > abs(dy):
            primary = Directions.EAST if dx > 0 else Directions.WEST
        else:
            primary = Directions.NORTH if dy > 0 else Directions.SOUTH

        legal = state.getLegalActions(agent_idx)
        if primary in legal:
            return primary

        # Try secondary
        if abs(dx) > abs(dy):
            secondary = Directions.NORTH if dy > 0 else Directions.SOUTH
        else:
            secondary = Directions.EAST if dx > 0 else Directions.WEST

        if secondary in legal:
            return secondary

        # Fallback
        legal = [a for a in legal if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _get_boundary(self, state):
        walls = state.getWalls()
        width, height = walls.width, walls.height
        mid_x = width // 2

        x = mid_x - 1 if self.red else mid_x

        boundary = []
        for y in range(1, height - 1):
            if not walls[x][y]:
                boundary.append((x, y))

        return boundary
