# myTeam_mcts.py
# MCTS-based Pacman Competition Agent
# Phase 1: Core MCTS Framework

from captureAgents import CaptureAgent
import random, time, util, math
from game import Directions
import game
import os
from datetime import datetime

#################
# Team creation #
#################

def createTeam(firstIndex, secondIndex, isRed,
               first='MCTSAgent', second='MCTSAgent'):
    """
    This function returns a list of two MCTS agents.
    Both agents use the same MCTS algorithm but coordinate through joint actions.
    """
    return [eval(first)(firstIndex), eval(second)(secondIndex)]

###############
# MCTS Node   #
###############

class MCTSNode:
    """
    Node in the MCTS tree.
    Represents a game state and tracks visit/reward statistics.
    SINGLE-AGENT: Each agent maintains its own tree independently.
    """
    def __init__(self, state, parent=None, action=None):
        self.state = state              # GameState
        self.parent = parent            # MCTSNode or None
        self.action = action            # Single action (Direction) for this agent
        self.children = []              # List[MCTSNode]
        self.visits = 0                 # int: number of times visited
        self.total_reward = 0.0         # float: cumulative reward
        self.untried_actions = None     # Will be set during expansion

    def is_fully_expanded(self):
        """Check if all legal joint actions have been tried"""
        return self.untried_actions is not None and len(self.untried_actions) == 0

    def is_terminal(self):
        """Check if this is a terminal game state"""
        return self.state.isOver()

    def ucb_score(self, exploration_constant=1.41):
        """
        Calculate UCB1 score for this node.
        UCB1 = exploitation + exploration
        """
        if self.visits == 0:
            return float('inf')  # Prioritize unvisited nodes

        if self.parent is None:
            return 0.0

        # Exploitation term
        exploit = self.total_reward / self.visits

        # Exploration term
        explore = exploration_constant * math.sqrt(math.log(self.parent.visits) / self.visits)

        return exploit + explore

###############
# MCTS Agent  #
###############

class MCTSAgent(CaptureAgent):
    """
    MCTS-based agent that uses Monte Carlo Tree Search to select actions.
    Uses joint action space (coordinates with teammate).
    """

    def __init__(self, index, timeForComputing=0.1):
        super().__init__(index, timeForComputing)
        self.tree_root = None
        self.teammate_index = None
        self.exploration_constant = 2.0  # Higher exploration (was 1.41)
        self.rollout_depth = 10
        self.time_budget = 0.3  # seconds - balanced for strong play + fast iteration
        self.debug_mode = True  # Set to False to disable visual debugging
        self.move_count = 0

        # Role assignment: first agent (index 0 or 1) is offensive, second is defensive
        self.role = 'offensive' if index in [0, 1] else 'defensive'

        # Create debug log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"agent_{index}_debug_{timestamp}.log"
        with open(self.log_file, 'w') as f:
            f.write(f"Agent {index} Debug Log (Role: {self.role})\n")
            f.write("="*60 + "\n\n")

    def registerInitialState(self, gameState):
        """
        This method handles the initial setup of the agent.
        Initialize team structure and find teammate.
        """
        CaptureAgent.registerInitialState(self, gameState)

        # Find teammate index
        team = self.getTeam(gameState)
        self.teammate_index = [i for i in team if i != self.index][0]

        # Cache initial state info
        self.start = gameState.getAgentPosition(self.index)
        self.walls = gameState.getWalls()

        print(f"Agent {self.index} initialized with teammate {self.teammate_index}")

    def chooseAction(self, gameState):
        """
        Main entry point for action selection.
        Runs MCTS and returns the best action.
        """
        start_time = time.time()
        self.move_count += 1

        # Log current state
        myPos = gameState.getAgentPosition(self.index)
        myState = gameState.getAgentState(self.index)
        score = gameState.getScore()

        legal_actions = gameState.getLegalActions(self.index)

        # OFFENSIVE OVERRIDE: Force forward movement until we reach enemy territory
        if self.role == 'offensive' and not myState.isPacman:
            walls = gameState.getWalls()
            mid_x = walls.width // 2

            # Try to go forward (East/West)
            if self.red and myPos[0] < mid_x - 1:
                if Directions.EAST in legal_actions:
                    with open(self.log_file, 'a') as f:
                        f.write(f"\n--- Move {self.move_count} (FORCE EAST) ---\nPosition: {myPos}\n")
                    return Directions.EAST
                else:
                    # Can't go East - explore North/South to find opening
                    # Prefer directions that might lead to openings
                    if Directions.NORTH in legal_actions and Directions.SOUTH in legal_actions:
                        # Randomly pick to explore
                        choice = random.choice([Directions.NORTH, Directions.SOUTH])
                        with open(self.log_file, 'a') as f:
                            f.write(f"\n--- Move {self.move_count} (EXPLORE {choice} - East blocked) ---\n")
                        return choice
                    elif Directions.NORTH in legal_actions:
                        return Directions.NORTH
                    elif Directions.SOUTH in legal_actions:
                        return Directions.SOUTH

            elif not self.red and myPos[0] > mid_x:
                if Directions.WEST in legal_actions:
                    with open(self.log_file, 'a') as f:
                        f.write(f"\n--- Move {self.move_count} (FORCE WEST) ---\nPosition: {myPos}\n")
                    return Directions.WEST
                else:
                    # Can't go West - explore North/South
                    if Directions.NORTH in legal_actions and Directions.SOUTH in legal_actions:
                        choice = random.choice([Directions.NORTH, Directions.SOUTH])
                        with open(self.log_file, 'a') as f:
                            f.write(f"\n--- Move {self.move_count} (EXPLORE {choice} - West blocked) ---\n")
                        return choice
                    elif Directions.NORTH in legal_actions:
                        return Directions.NORTH
                    elif Directions.SOUTH in legal_actions:
                        return Directions.SOUTH

        log_msg = f"\n--- Move {self.move_count} ---\n"
        log_msg += f"Position: {myPos}\n"
        log_msg += f"isPacman: {myState.isPacman}\n"
        log_msg += f"Carrying: {myState.numCarrying}\n"
        log_msg += f"Score: {score}\n"
        log_msg += f"Legal actions: {legal_actions}\n"

        # Initialize or reuse tree
        if self.tree_root is None:
            self.tree_root = MCTSNode(gameState)
        else:
            # Try to reuse tree from previous turn
            self.tree_root = self._reuse_tree(gameState)

        # Run MCTS iterations
        num_rollouts = 0
        while time.time() - start_time < self.time_budget:
            # 1. Selection: traverse tree using UCB1
            node = self._select(self.tree_root)

            # 2. Expansion: add one child if not terminal
            if not node.is_terminal() and node.visits > 0:
                node = self._expand(node)

            # 3. Simulation: rollout to depth limit
            reward = self._simulate(node.state)

            # 4. Backpropagation: update all ancestors
            self._backpropagate(node, reward)

            num_rollouts += 1

        # Select best action (most visited child)
        if not self.tree_root.children:
            # Fallback if no children (shouldn't happen)
            return self._safe_fallback(gameState)

        best_child = max(self.tree_root.children, key=lambda c: c.visits)
        joint_action = best_child.action

        # Extract my action from joint action
        my_action = self._extract_my_action(joint_action)

        # Verify action is legal before returning
        legal_actions = gameState.getLegalActions(self.index)
        if my_action not in legal_actions:
            # Fallback to safe action if extracted action is illegal
            print(f"Warning: extracted action {my_action} not legal, using fallback")
            my_action = self._safe_fallback(gameState)
            log_msg += "WARNING: Illegal action, using fallback!\n"

        # Log action details
        log_msg += f"Action chosen: {my_action}\n"

        # Log what agent is trying to do
        if myState.isPacman:
            food = self.getFood(gameState).asList()
            if food:
                closest_food = min(food, key=lambda f: self._manhattan(myPos, f))
                log_msg += f"Target food: {closest_food} (dist: {self._manhattan(myPos, closest_food)})\n"

            # Check for nearby threats
            enemies = self.getOpponents(gameState)
            threats = []
            for enemy_idx in enemies:
                enemy_state = gameState.getAgentState(enemy_idx)
                enemy_pos = enemy_state.getPosition()
                if enemy_pos and not enemy_state.isPacman and enemy_state.scaredTimer == 0:
                    dist = self._manhattan(myPos, enemy_pos)
                    if dist <= 5:
                        threats.append((enemy_idx, enemy_pos, dist))
            if threats:
                log_msg += f"Threats nearby: {threats}\n"

            # Check if should return home
            if myState.numCarrying >= 5:
                boundary = self._get_boundary(gameState, self.index)
                if boundary:
                    closest_boundary = min(boundary, key=lambda b: self._manhattan(myPos, b))
                    log_msg += f"Carrying {myState.numCarrying}, should return to: {closest_boundary}\n"
        else:
            # Ghost mode - check for invaders
            invaders = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
            invader_positions = [(i, inv.getPosition()) for i, inv in enumerate(invaders)
                               if inv.isPacman and inv.getPosition() is not None]
            if invader_positions:
                log_msg += f"Invaders detected: {invader_positions}\n"

        # Debug info
        elapsed = time.time() - start_time
        avg_rollout_time = (elapsed / num_rollouts * 1000) if num_rollouts > 0 else 0
        log_msg += f"MCTS: {num_rollouts} rollouts in {elapsed:.3f}s\n"
        print(f"Agent {self.index}: {num_rollouts} rollouts in {elapsed:.3f}s (avg {avg_rollout_time:.2f}ms/rollout)")

        # Write to log file
        with open(self.log_file, 'a') as f:
            f.write(log_msg)

        # Visual debugging
        if self.debug_mode:
            self._visualize_state(gameState)

        return my_action

    def _select(self, node):
        """
        Selection phase: traverse tree using UCB1 until reaching a leaf.
        """
        while not node.is_terminal() and node.is_fully_expanded():
            node = max(node.children, key=lambda c: c.ucb_score(self.exploration_constant))
        return node

    def _expand(self, node):
        """
        Expansion phase: add one child to the tree.
        """
        # Initialize untried actions if needed
        if node.untried_actions is None:
            node.untried_actions = self._get_legal_joint_actions(node.state)

        # No untried actions left
        if not node.untried_actions:
            return node

        # Pick first untried action (TODO: can prioritize offensive actions)
        joint_action = node.untried_actions.pop(0)

        # Create successor state
        successor_state = self._apply_joint_action(node.state, joint_action)

        # Create child node
        child = MCTSNode(successor_state, parent=node, action=joint_action)
        node.children.append(child)

        return child

    def _simulate(self, state):
        """
        Simulation phase: rollout using fast heuristic policy.
        Returns reward for terminal state.
        """
        current_state = state
        depth = 0

        # Rollout for fixed depth
        while depth < self.rollout_depth and not current_state.isOver():
            # Get actions for all 4 agents
            actions = []
            for agent_idx in range(4):
                try:
                    if agent_idx in self.getTeam(current_state):
                        # Our agent: smart heuristic
                        action = self._rollout_policy(current_state, agent_idx)
                    else:
                        # Opponent: chase our pacmen
                        action = self._opponent_policy(current_state, agent_idx)
                    actions.append(action)
                except:
                    # Agent might be dead/invalid, skip
                    actions.append(Directions.STOP)

            # Apply actions sequentially (turn order: 0, 1, 2, 3)
            for i, action in enumerate(actions):
                if not current_state.isOver():
                    try:
                        current_state = current_state.generateSuccessor(i, action)
                    except:
                        # State might be invalid, abort simulation
                        return self._evaluate_state(current_state)

            depth += 1

        # Evaluate final state
        return self._evaluate_state(current_state)

    def _backpropagate(self, node, reward):
        """
        Backpropagation phase: update visit counts and rewards.
        """
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            node = node.parent

    def _evaluate_state(self, state):
        """
        Evaluate a game state and return a reward.
        Positive = good for our team, negative = bad.
        Enhanced to consider position quality, not just score.
        """
        # Base score (most important)
        score = state.getScore()

        # Adjust for team perspective
        if not self.red:
            score = -score

        # Additional heuristics to guide MCTS
        team = self.getTeam(state)
        reward = score * 10  # Score is most important

        walls = state.getWalls()
        mid_x = walls.width // 2

        for agent_idx in team:
            agent_pos = state.getAgentPosition(agent_idx)
            if agent_pos is None:
                continue

            agent_state = state.getAgentState(agent_idx)

            # Determine agent role (offensive agents should cross boundary)
            is_offensive_agent = (agent_idx == self.index and self.role == 'offensive')

            # Reward being Pacman (in enemy territory)
            if agent_state.isPacman:
                # Offensive agents get huge reward for being Pacman
                if is_offensive_agent or agent_idx == self.index:
                    reward += 10.0  # Very strong reward
                else:
                    reward += 2.0  # Defensive agent can go offensive too, but less incentive
                reward += 5.0  # Strong reward for being offensive

                # Reward proximity to food
                food = self.getFood(state).asList()
                if food:
                    min_food_dist = min([self._manhattan(agent_pos, f) for f in food])
                    reward += (50 - min_food_dist) * 0.05  # Closer to food = better

                # Penalty for being close to enemy ghosts
                enemies = self.getOpponents(state)
                for enemy_idx in enemies:
                    enemy_state = state.getAgentState(enemy_idx)
                    enemy_pos = enemy_state.getPosition()
                    if enemy_pos and not enemy_state.isPacman and enemy_state.scaredTimer == 0:
                        dist = self._manhattan(agent_pos, enemy_pos)
                        if dist <= 5:
                            reward -= (6 - dist) * 1.0  # Strong danger penalty

                # Reward carrying food (but encourage depositing)
                carrying = agent_state.numCarrying
                if carrying > 0:
                    reward += carrying * 1.0  # Strong incentive to carry

                    # Strong incentive to return home when carrying 5+
                    if carrying >= 5:
                        boundary = self._get_boundary(state, agent_idx)
                        if boundary:
                            min_boundary_dist = min([self._manhattan(agent_pos, b) for b in boundary])
                            reward += (50 - min_boundary_dist) * 0.2  # Closer to home = better

            # If we're ghost
            else:
                # Reward proximity to invaders (defense) - especially for defensive agents
                invaders = [state.getAgentState(i) for i in self.getOpponents(state)]
                invaders = [inv for inv in invaders if inv.isPacman and inv.getPosition() is not None]

                if invaders and not is_offensive_agent:
                    # Defensive agent prioritizes catching invaders
                    min_invader_dist = min([self._manhattan(agent_pos, inv.getPosition()) for inv in invaders])
                    reward += (50 - min_invader_dist) * 0.5  # Strong defense incentive
                elif is_offensive_agent or agent_idx == self.index:
                    # Offensive agent should push into enemy territory
                    food = self.getFood(state).asList()
                    if food:
                        # Use actual maze distance, not Manhattan
                        try:
                            min_food_dist = min([self.distancer.getDistance(agent_pos, f) for f in food])
                            reward += (100 - min_food_dist) * 0.5  # Very strong forward incentive
                        except:
                            # Fallback to Manhattan if distancer fails
                            min_food_dist = min([self._manhattan(agent_pos, f) for f in food])
                            reward += (100 - min_food_dist) * 0.3

                    # MASSIVE reward for x-axis progress towards enemy (offensive only)
                    if self.red:
                        x_progress = agent_pos[0]
                        reward += x_progress * x_progress * 0.5  # Quadratic reward
                    else:
                        x_progress = (walls.width - agent_pos[0])
                        reward += x_progress * x_progress * 0.5

        return reward

    def _get_legal_joint_actions(self, state):
        """
        Get all legal joint actions (action0, action2) for our team.
        """
        team = self.getTeam(state)
        agent0 = min(team)
        agent2 = max(team)

        actions0 = state.getLegalActions(agent0)
        actions2 = state.getLegalActions(agent2)

        # Generate all combinations
        joint_actions = []
        for a0 in actions0:
            for a2 in actions2:
                joint_actions.append((a0, a2))

        return joint_actions

    def _apply_joint_action(self, state, joint_action):
        """
        Apply a joint action (action0, action2) to the state.
        Must handle turn order correctly (0, 1, 2, 3).
        """
        action0, action2 = joint_action
        team = self.getTeam(state)
        agent0 = min(team)
        agent2 = max(team)

        # We need to apply all 4 agents' actions in order
        # For now, opponents take random actions
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
                    # Opponent: random action
                    legal = current_state.getLegalActions(agent_idx)
                    action = random.choice(legal) if legal else Directions.STOP

                current_state = current_state.generateSuccessor(agent_idx, action)
            except:
                # Agent might be invalid/dead, skip
                continue

        return current_state

    def _extract_my_action(self, joint_action):
        """
        Extract my action from a joint action tuple.
        """
        team = self.getTeam(self.tree_root.state)
        agent0 = min(team)

        if self.index == agent0:
            return joint_action[0]
        else:
            return joint_action[1]

    def _reuse_tree(self, gameState):
        """
        Try to reuse tree from previous turn by finding matching child.
        If no match, create new root.
        """
        # Simple matching: compare scores
        current_score = gameState.getScore()

        for child in self.tree_root.children:
            if child.state.getScore() == current_score:
                # Found matching child, make it new root
                child.parent = None
                return child

        # No match found, create new root
        return MCTSNode(gameState)

    def _safe_fallback(self, gameState):
        """
        Fallback action if MCTS fails.
        Returns a safe random legal action.
        """
        legal = gameState.getLegalActions(self.index)
        legal = [a for a in legal if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    # ==========================================
    # Phase 2: Fast Rollout Policy
    # ==========================================

    def _rollout_policy(self, state, agent_idx):
        """
        Fast heuristic for our agents during simulation.
        Priority-based decision making.
        """
        myPos = state.getAgentPosition(agent_idx)
        if myPos is None:
            return Directions.STOP

        myState = state.getAgentState(agent_idx)
        legal = state.getLegalActions(agent_idx)

        # Stuck detection: if we're ghost and can't go East/West, we need to explore vertically
        if not myState.isPacman:
            walls = state.getWalls()
            mid_x = walls.width // 2
            # Check if we're far from boundary and can't move horizontally
            if self.red and myPos[0] < mid_x - 5:
                # Stuck on Red side, need to find opening
                if Directions.EAST not in legal:
                    # Can't go East, must explore North/South to find opening
                    # Use random to avoid getting stuck in local minimum
                    if random.random() < 0.3:  # 30% random exploration
                        legal_no_stop = [a for a in legal if a != Directions.STOP]
                        return random.choice(legal_no_stop) if legal_no_stop else Directions.STOP
            elif not self.red and myPos[0] > mid_x + 5:
                # Stuck on Blue side
                if Directions.WEST not in legal:
                    if random.random() < 0.3:
                        legal_no_stop = [a for a in legal if a != Directions.STOP]
                        return random.choice(legal_no_stop) if legal_no_stop else Directions.STOP

        # Priority 1: Emergency escape (ghost within 3)
        if myState.isPacman:
            ghosts = self._get_enemy_ghosts(state, agent_idx)
            if ghosts:
                closest_ghost_pos = min([g.getPosition() for g in ghosts],
                                       key=lambda p: self._manhattan(myPos, p))
                if self._manhattan(myPos, closest_ghost_pos) <= 3:
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

        # Priority 4: Return home if carrying 8+
        if myState.isPacman and myState.numCarrying >= 8:
            boundary = self._get_boundary(state, agent_idx)
            if boundary:
                closest_boundary = min(boundary, key=lambda b: self._manhattan(myPos, b))
                action = self._move_towards(myPos, closest_boundary, state, agent_idx)
                if action in legal:
                    return action

        # Priority 5: Enter enemy territory if we're on our side
        if not myState.isPacman:
            # Target enemy food, not boundary - use MAZE distance
            food = self.getFood(state).asList()
            if food:
                # Pick closest food using actual maze distance
                try:
                    target_food = min(food, key=lambda f: self.distancer.getDistance(myPos, f))
                except:
                    target_food = min(food, key=lambda f: self._manhattan(myPos, f))

                action = self._move_towards(myPos, target_food, state, agent_idx)
                if action in legal:
                    return action

        # Fallback: prefer moving towards center (not just random)
        walls = state.getWalls()
        mid_x = walls.width // 2
        legal_no_stop = [a for a in legal if a != Directions.STOP]

        if legal_no_stop and not myState.isPacman:
            # Try to move towards the center (boundary)
            if myPos[0] < mid_x:
                # We're on Red side, try to go East
                if Directions.EAST in legal_no_stop:
                    return Directions.EAST
            elif myPos[0] > mid_x:
                # We're on Blue side, try to go West
                if Directions.WEST in legal_no_stop:
                    return Directions.WEST

        # Final fallback: random movement
        return random.choice(legal_no_stop) if legal_no_stop else Directions.STOP

    def _opponent_policy(self, state, agent_idx):
        """
        Model opponent behavior during simulation.
        Opponents chase our pacmen.
        """
        oppPos = state.getAgentPosition(agent_idx)
        if oppPos is None:
            return Directions.STOP

        oppState = state.getAgentState(agent_idx)
        legal = state.getLegalActions(agent_idx)

        # Model 1: Opponent chases our agents
        our_agents = self.getTeam(state)
        our_positions = []
        for i in our_agents:
            pos = state.getAgentPosition(i)
            if pos:
                our_positions.append(pos)

        our_pacmen = [pos for i, pos in zip(our_agents, our_positions)
                     if state.getAgentState(i).isPacman]

        if our_pacmen and not oppState.isPacman:
            # Opponent is ghost, we have pacmen → chase closest pacman
            closest_pacman = min(our_pacmen, key=lambda p: self._manhattan(oppPos, p))
            action = self._move_towards(oppPos, closest_pacman, state, agent_idx)
            if action in legal:
                return action

        # Model 2: Opponent goes for food
        if oppState.isPacman:
            our_food = self.getFoodYouAreDefending(state).asList()
            if our_food:
                closest_food = min(our_food, key=lambda f: self._manhattan(oppPos, f))
                action = self._move_towards(oppPos, closest_food, state, agent_idx)
                if action in legal:
                    return action

        # Default: random legal action
        return random.choice(legal) if legal else Directions.STOP

    # Helper functions
    def _manhattan(self, pos1, pos2):
        """Manhattan distance (fast, O(1))"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

    def _move_towards(self, fromPos, toPos, state, agent_idx):
        """Return action that moves towards target"""
        dx = toPos[0] - fromPos[0]
        dy = toPos[1] - fromPos[1]

        # Try primary direction
        if abs(dx) > abs(dy):
            primary = Directions.EAST if dx > 0 else Directions.WEST
        else:
            primary = Directions.NORTH if dy > 0 else Directions.SOUTH

        if primary in state.getLegalActions(agent_idx):
            return primary

        # Try secondary direction
        if abs(dx) > abs(dy):
            secondary = Directions.NORTH if dy > 0 else Directions.SOUTH
        else:
            secondary = Directions.EAST if dx > 0 else Directions.WEST

        if secondary in state.getLegalActions(agent_idx):
            return secondary

        # Fallback: any legal action except STOP
        legal = [a for a in state.getLegalActions(agent_idx) if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _move_away(self, fromPos, threatPos, state, agent_idx):
        """Return action that moves away from threat"""
        # Opposite of _move_towards
        dx = fromPos[0] - threatPos[0]
        dy = fromPos[1] - threatPos[1]

        if abs(dx) > abs(dy):
            primary = Directions.EAST if dx > 0 else Directions.WEST
        else:
            primary = Directions.NORTH if dy > 0 else Directions.SOUTH

        if primary in state.getLegalActions(agent_idx):
            return primary

        # Fallback
        legal = [a for a in state.getLegalActions(agent_idx) if a != Directions.STOP]
        return random.choice(legal) if legal else Directions.STOP

    def _get_enemy_ghosts(self, state, agent_idx):
        """Enemy agents that are ghosts (not scared)"""
        opponents = self.getOpponents(state)
        ghosts = []
        for opp in opponents:
            opp_state = state.getAgentState(opp)
            if not opp_state.isPacman and opp_state.getPosition() is not None:
                if opp_state.scaredTimer <= 0:
                    ghosts.append(opp_state)
        return ghosts

    def _get_invaders(self, state, agent_idx):
        """Enemy agents in our territory"""
        opponents = self.getOpponents(state)
        invaders = []
        for opp in opponents:
            opp_state = state.getAgentState(opp)
            if opp_state.isPacman and opp_state.getPosition() is not None:
                invaders.append(opp_state)
        return invaders

    def _get_boundary(self, state, agent_idx):
        """Boundary positions between territories"""
        walls = state.getWalls()
        width, height = walls.width, walls.height
        mid_x = width // 2

        # Red team: x = mid_x - 1, Blue team: x = mid_x
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

    def _visualize_state(self, gameState):
        """
        Visualize agent's strategic understanding on the game map.
        Colors: RED = target food, BLUE = boundary, GREEN = safe path
        """
        myPos = gameState.getAgentPosition(self.index)
        if myPos is None:
            return

        myState = gameState.getAgentState(self.index)

        # Clear previous debug drawings
        self.debugClear()

        if myState.isPacman:
            # Show food targets in RED
            food = self.getFood(gameState).asList()
            if food:
                closest_food = min(food, key=lambda f: self._manhattan(myPos, f))
                self.debugDraw([closest_food], [1, 0, 0], clear=False)  # RED

            # Show enemy ghosts in ORANGE (danger zones)
            enemies = self.getOpponents(gameState)
            danger_zones = []
            for enemy_idx in enemies:
                enemy_state = gameState.getAgentState(enemy_idx)
                enemy_pos = enemy_state.getPosition()
                if enemy_pos and not enemy_state.isPacman and enemy_state.scaredTimer == 0:
                    dist = self._manhattan(myPos, enemy_pos)
                    if dist <= 5:
                        danger_zones.append(enemy_pos)
            if danger_zones:
                self.debugDraw(danger_zones, [1, 0.5, 0], clear=False)  # ORANGE

            # Show boundary (escape route) in BLUE
            boundary = self._get_boundary(gameState, self.index)
            if boundary and myState.numCarrying >= 5:
                closest_boundary = min(boundary, key=lambda b: self._manhattan(myPos, b))
                self.debugDraw([closest_boundary], [0, 0, 1], clear=False)  # BLUE
        else:
            # Ghost mode: show invaders in RED
            invaders = [gameState.getAgentState(i) for i in self.getOpponents(gameState)]
            invader_positions = [inv.getPosition() for inv in invaders
                               if inv.isPacman and inv.getPosition() is not None]
            if invader_positions:
                self.debugDraw(invader_positions, [1, 0, 0], clear=False)  # RED

            # Show boundary patrol zone in GREEN
            boundary = self._get_boundary(gameState, self.index)
            if boundary:
                # Show a few boundary points (not all, to avoid clutter)
                sample_boundary = boundary[::3]  # Every 3rd point
                self.debugDraw(sample_boundary, [0, 1, 0], clear=False)  # GREEN
