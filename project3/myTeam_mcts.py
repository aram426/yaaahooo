# myTeam_mcts.py
# MCTS-based Pacman Competition Agent
# Phase 1: Core MCTS Framework

from captureAgents import CaptureAgent
import random, time, util, math
from game import Directions
import game

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
    """
    def __init__(self, state, parent=None, action=None):
        self.state = state              # GameState
        self.parent = parent            # MCTSNode or None
        self.action = action            # (action0, action2) joint action tuple
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
        self.exploration_constant = 1.41
        self.rollout_depth = 10
        self.time_budget = 0.8  # seconds

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
            return self._safe_fallback(gameState)

        # Debug info
        elapsed = time.time() - start_time
        avg_rollout_time = (elapsed / num_rollouts * 1000) if num_rollouts > 0 else 0
        print(f"Agent {self.index}: {num_rollouts} rollouts in {elapsed:.3f}s (avg {avg_rollout_time:.2f}ms/rollout)")

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
                    legal = current_state.getLegalActions(agent_idx)
                    if not legal:
                        actions.append(Directions.STOP)
                    else:
                        # Random policy for Phase 1 (will improve in Phase 2)
                        action = random.choice(legal)
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
        """
        # Base score
        score = state.getScore()

        # Adjust for team perspective
        if not self.red:
            score = -score

        return score

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
