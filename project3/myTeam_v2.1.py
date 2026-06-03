# myTeam_v2.1.py
# Phase 2.1: Quick Wins
# - Improved evaluation function (numCarrying)
# - Increased danger detection range (3 → 5)
# - Dynamic return threshold (3-8 based on danger)
# - Remove Stop action for offensive agents

from captureAgents import CaptureAgent
import random, time, util, math
from game import Directions
import game

def createTeam(firstIndex, secondIndex, isRed,
               first='MCTSAgent', second='MCTSAgent'):
    return [eval(first)(firstIndex), eval(second)(secondIndex)]

class MCTSNode:
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action
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
        self.teammate_index = None
        self.exploration_constant = 1.41
        self.rollout_depth = 10
        self.time_budget = 0.3  # Reduced from 0.8 to prevent game timeout

    def registerInitialState(self, gameState):
        CaptureAgent.registerInitialState(self, gameState)
        team = self.getTeam(gameState)
        self.teammate_index = [i for i in team if i != self.index][0]
        self.start = gameState.getAgentPosition(self.index)
        self.walls = gameState.getWalls()
        print(f"Agent {self.index} initialized with teammate {self.teammate_index}")

    def chooseAction(self, gameState):
        start_time = time.time()

        if self.tree_root is None:
            self.tree_root = MCTSNode(gameState)
        else:
            self.tree_root = self._reuse_tree(gameState)

        num_rollouts = 0
        while time.time() - start_time < self.time_budget:
            node = self._select(self.tree_root)
            if not node.is_terminal() and node.visits > 0:
                node = self._expand(node)
            reward = self._simulate(node.state)
            self._backpropagate(node, reward)
            num_rollouts += 1

        if not self.tree_root.children:
            return self._safe_fallback(gameState)

        best_child = max(self.tree_root.children, key=lambda c: c.visits)
        joint_action = best_child.action
        my_action = self._extract_my_action(joint_action)

        legal_actions = gameState.getLegalActions(self.index)
        if my_action not in legal_actions:
            print(f"Warning: extracted action {my_action} not legal, using fallback")
            return self._safe_fallback(gameState)

        elapsed = time.time() - start_time
        print(f"Agent {self.index}: {num_rollouts} rollouts in {elapsed:.3f}s")

        return my_action

    def _select(self, node):
        while not node.is_terminal() and node.is_fully_expanded():
            node = max(node.children, key=lambda c: c.ucb_score(self.exploration_constant))
        return node

    def _expand(self, node):
        if node.untried_actions is None:
            node.untried_actions = self._get_legal_joint_actions(node.state)

        if not node.untried_actions:
            return node

        joint_action = node.untried_actions.pop(0)
        successor_state = self._apply_joint_action(node.state, joint_action)
        child = MCTSNode(successor_state, parent=node, action=joint_action)
        node.children.append(child)
        return child

    def _simulate(self, state):
        current_state = state
        depth = 0

        while depth < self.rollout_depth and not current_state.isOver():
            actions = []
            for agent_idx in range(4):
                try:
                    if agent_idx in self.getTeam(current_state):
                        action = self._rollout_policy(current_state, agent_idx)
                    else:
                        action = self._opponent_policy(current_state, agent_idx)
                    actions.append(action)
                except:
                    actions.append(Directions.STOP)

            for i, action in enumerate(actions):
                if not current_state.isOver():
                    try:
                        current_state = current_state.generateSuccessor(i, action)
                    except:
                        return self._evaluate_state(current_state)

            depth += 1

        return self._evaluate_state(current_state)

    def _backpropagate(self, node, reward):
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            node = node.parent

    def _evaluate_state(self, state):
        """
        IMPROVEMENT 1: Better evaluation function
        - Score is primary (x100 weight)
        - numCarrying = potential score (+10 per food)
        - Danger penalty when carrying near enemies
        """
        score = state.getScore()
        if not self.red:
            score = -score

        reward = score * 100  # Primary: actual score

        # Secondary: potential score and danger
        for agent_idx in self.getTeam(state):
            agent_state = state.getAgentState(agent_idx)
            pos = state.getAgentPosition(agent_idx)

            if pos and agent_state.isPacman:
                # Reward for carrying food (potential score)
                reward += agent_state.numCarrying * 10

                # Penalty for danger while carrying
                enemies = self._get_enemy_ghosts(state, agent_idx)
                if enemies and agent_state.numCarrying > 0:
                    closest_dist = min(self._manhattan(pos, e.getPosition()) for e in enemies)
                    if closest_dist < 5:
                        # Higher penalty when closer to enemy with food
                        danger_penalty = (5 - closest_dist) * agent_state.numCarrying * 5
                        reward -= danger_penalty

        return reward

    def _get_legal_joint_actions(self, state):
        """
        IMPROVEMENT 4: Remove Stop actions for offensive play
        """
        team = self.getTeam(state)
        agent0 = min(team)
        agent2 = max(team)

        actions0 = state.getLegalActions(agent0)
        actions2 = state.getLegalActions(agent2)

        # Remove STOP unless it's the only option
        if len(actions0) > 1:
            actions0 = [a for a in actions0 if a != Directions.STOP]
        if len(actions2) > 1:
            actions2 = [a for a in actions2 if a != Directions.STOP]

        joint_actions = []
        for a0 in actions0:
            for a2 in actions2:
                joint_actions.append((a0, a2))

        return joint_actions

    def _apply_joint_action(self, state, joint_action):
        action0, action2 = joint_action
        team = self.getTeam(state)
        agent0 = min(team)
        agent2 = max(team)

        current_state = state

        for agent_idx in range(4):
            if current_state.isOver():
                break

            try:
                if agent_idx == agent0:
                    action = action0
                elif agent_idx == agent2:
                    action = action2
                else:
                    legal = current_state.getLegalActions(agent_idx)
                    action = random.choice(legal) if legal else Directions.STOP

                current_state = current_state.generateSuccessor(agent_idx, action)
            except:
                continue

        return current_state

    def _extract_my_action(self, joint_action):
        team = self.getTeam(self.tree_root.state)
        agent0 = min(team)
        if self.index == agent0:
            return joint_action[0]
        else:
            return joint_action[1]

    def _reuse_tree(self, gameState):
        current_score = gameState.getScore()
        for child in self.tree_root.children:
            if child.state.getScore() == current_score:
                child.parent = None
                return child
        return MCTSNode(gameState)

    def _safe_fallback(self, gameState):
        legal = gameState.getLegalActions(self.index)
        legal = [a for a in legal if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _rollout_policy(self, state, agent_idx):
        """
        IMPROVEMENT 2 & 3:
        - Increased danger detection (3 → 5 squares)
        - Dynamic return threshold (3-8 based on danger)
        """
        myPos = state.getAgentPosition(agent_idx)
        if myPos is None:
            return Directions.STOP

        myState = state.getAgentState(agent_idx)
        legal = state.getLegalActions(agent_idx)

        # Priority 1: Emergency escape (IMPROVED: 5 squares instead of 3)
        if myState.isPacman:
            ghosts = self._get_enemy_ghosts(state, agent_idx)
            if ghosts:
                closest_ghost_pos = min([g.getPosition() for g in ghosts],
                                       key=lambda p: self._manhattan(myPos, p))
                ghost_dist = self._manhattan(myPos, closest_ghost_pos)

                # IMPROVED: Wider danger range
                if ghost_dist <= 5:
                    action = self._move_away(myPos, closest_ghost_pos, state, agent_idx)
                    if action in legal:
                        return action

        # Priority 2: Chase invader (if we're ghost)
        if not myState.isPacman:
            invaders = self._get_invaders(state, agent_idx)
            if invaders:
                closest_inv = min([inv.getPosition() for inv in invaders],
                                key=lambda p: self._manhattan(myPos, p))
                action = self._move_towards(myPos, closest_inv, state, agent_idx)
                if action in legal:
                    return action

        # Priority 3: Go to food (if we're pacman)
        if myState.isPacman:
            food = self.getFood(state).asList()
            if food:
                closest_food = min(food, key=lambda f: self._manhattan(myPos, f))
                action = self._move_towards(myPos, closest_food, state, agent_idx)
                if action in legal:
                    return action

        # Priority 4: Return home with DYNAMIC threshold (IMPROVED)
        if myState.isPacman:
            # Calculate dynamic threshold based on danger
            carrying_threshold = 8  # Default: greedy

            ghosts = self._get_enemy_ghosts(state, agent_idx)
            if ghosts:
                closest_ghost_dist = min(self._manhattan(myPos, g.getPosition()) for g in ghosts)
                if closest_ghost_dist < 8:
                    # Danger nearby → be conservative
                    carrying_threshold = 3
                elif closest_ghost_dist < 12:
                    # Medium danger → balanced
                    carrying_threshold = 5

            if myState.numCarrying >= carrying_threshold:
                boundary = self._get_boundary(state, agent_idx)
                if boundary:
                    closest_boundary = min(boundary, key=lambda b: self._manhattan(myPos, b))
                    action = self._move_towards(myPos, closest_boundary, state, agent_idx)
                    if action in legal:
                        return action

        # Priority 5: Default - enter enemy territory
        boundary = self._get_boundary(state, agent_idx)
        if boundary:
            closest_boundary = min(boundary, key=lambda b: self._manhattan(myPos, b))
            action = self._move_towards(myPos, closest_boundary, state, agent_idx)
            if action in legal:
                return action

        legal = [a for a in legal if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _opponent_policy(self, state, agent_idx):
        oppPos = state.getAgentPosition(agent_idx)
        if oppPos is None:
            return Directions.STOP

        oppState = state.getAgentState(agent_idx)
        legal = state.getLegalActions(agent_idx)

        our_agents = self.getTeam(state)
        our_positions = []
        for i in our_agents:
            pos = state.getAgentPosition(i)
            if pos:
                our_positions.append(pos)

        our_pacmen = [pos for i, pos in zip(our_agents, our_positions)
                     if state.getAgentState(i).isPacman]

        if our_pacmen and not oppState.isPacman:
            closest_pacman = min(our_pacmen, key=lambda p: self._manhattan(oppPos, p))
            action = self._move_towards(oppPos, closest_pacman, state, agent_idx)
            if action in legal:
                return action

        if oppState.isPacman:
            our_food = self.getFoodYouAreDefending(state).asList()
            if our_food:
                closest_food = min(our_food, key=lambda f: self._manhattan(oppPos, f))
                action = self._move_towards(oppPos, closest_food, state, agent_idx)
                if action in legal:
                    return action

        return random.choice(legal) if legal else Directions.STOP

    # Helper functions
    def _manhattan(self, pos1, pos2):
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _move_towards(self, fromPos, toPos, state, agent_idx):
        dx = toPos[0] - fromPos[0]
        dy = toPos[1] - fromPos[1]

        if abs(dx) > abs(dy):
            primary = Directions.EAST if dx > 0 else Directions.WEST
        else:
            primary = Directions.NORTH if dy > 0 else Directions.SOUTH

        if primary in state.getLegalActions(agent_idx):
            return primary

        if abs(dx) > abs(dy):
            secondary = Directions.NORTH if dy > 0 else Directions.SOUTH
        else:
            secondary = Directions.EAST if dx > 0 else Directions.WEST

        if secondary in state.getLegalActions(agent_idx):
            return secondary

        legal = [a for a in state.getLegalActions(agent_idx) if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _move_away(self, fromPos, threatPos, state, agent_idx):
        dx = fromPos[0] - threatPos[0]
        dy = fromPos[1] - threatPos[1]

        if abs(dx) > abs(dy):
            primary = Directions.EAST if dx > 0 else Directions.WEST
        else:
            primary = Directions.NORTH if dy > 0 else Directions.SOUTH

        if primary in state.getLegalActions(agent_idx):
            return primary

        legal = [a for a in state.getLegalActions(agent_idx) if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _get_enemy_ghosts(self, state, agent_idx):
        opponents = self.getOpponents(state)
        ghosts = []
        for opp in opponents:
            opp_state = state.getAgentState(opp)
            if not opp_state.isPacman and opp_state.getPosition() is not None:
                if opp_state.scaredTimer <= 0:
                    ghosts.append(opp_state)
        return ghosts

    def _get_invaders(self, state, agent_idx):
        opponents = self.getOpponents(state)
        invaders = []
        for opp in opponents:
            opp_state = state.getAgentState(opp)
            if opp_state.isPacman and opp_state.getPosition() is not None:
                invaders.append(opp_state)
        return invaders

    def _get_boundary(self, state, agent_idx):
        walls = state.getWalls()
        width, height = walls.width, walls.height
        mid_x = width // 2

        if agent_idx in self.getTeam(state):
            if self.red:
                x = mid_x - 1
            else:
                x = mid_x
        else:
            return []

        boundary = []
        for y in range(1, height - 1):
            if not walls[x][y]:
                boundary.append((x, y))

        return boundary
