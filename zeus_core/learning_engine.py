
import json
import os
import logging
from typing import Dict, Any, List, Tuple

class LearningEngine:
    """
    PHASE 7: Learning System.
    Adaptive intelligence based on a reward function.
    Adjusts strategy weights based on success, performance, and errors.
    """
    def __init__(self, blackboard, storage_file: str = "learning_weights.json"):
        self.blackboard = blackboard
        self.storage_file = storage_file
        self.logger = logging.getLogger("ZEUS_LEARNING")
        self.weights = self._load_weights()

    def _load_weights(self) -> Dict[str, float]:
        """Loads learned strategy weights from disk."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load weights: {e}")
        return {
            "aggressive": 1.0,  # Fast, high impact strategies
            "cautious": 1.0,    # Slow, high validation strategies
            "exploratory": 1.0  # Trying new patterns/paths
        }

    def save_weights(self):
        """Persists weights to disk using atomic write."""
        try:
            temp_file = self.storage_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.weights, f, indent=2)
            os.replace(temp_file, self.storage_file)
        except Exception as e:
            self.logger.error(f"Failed to save weights: {e}")

    def calculate_reward(self, execution_result: Dict[str, Any], performance_gain: float = 0.0, goal_progress: float = 0.0) -> float:
        """
        Implements the Reward Function from PLAN v3.0:
        reward = (success * 2) + (performance_gain * 1.5) - (errors * 3) - (rollback_cost * 2) + (goal_progress * 2)
        """
        success = 1.0 if execution_result.get("success", False) else 0.0
        errors = 1.0 if execution_result.get("error") else 0.0
        rollback_cost = 1.0 if execution_result.get("rollback_triggered", False) else 0.0
        
        reward = (success * 2.0) + \
                 (performance_gain * 1.5) - \
                 (errors * 3.0) - \
                 (rollback_cost * 2.0) + \
                 (goal_progress * 2.0)
        
        return reward

    def update_strategy(self, strategy_type: str, reward: float):
        """Adjusts weights based on the reward received."""
        if strategy_type not in self.weights:
            self.weights[strategy_type] = 1.0
            
        # Learning rate: weights move by 5% of the reward
        learning_rate = 0.05
        self.weights[strategy_type] += reward * learning_rate
        
        # Clamp weights to prevent explosion (between 0.1 and 5.0)
        self.weights[strategy_type] = max(0.1, min(5.0, self.weights[strategy_type]))
        
        self.save_weights()
        self.logger.info(f"Strategy {strategy_type} updated. New weight: {self.weights[strategy_type]:.4f} (Reward: {reward:.2f})")

    def get_best_strategy(self) -> str:
        """Returns the strategy with the highest weight."""
        return max(self.weights, key=self.weights.get)

    def record_experience(self, strategy_type: str, execution_result: Dict[str, Any], goal_progress: float = 0.0):
        """Processes an execution and updates the learning model."""
        # Calculate performance gain as a dummy for now (could be based on CPU/RAM metrics)
        perf_gain = 0.1 if execution_result.get("success") else -0.1
        
        reward = self.calculate_reward(execution_result, perf_gain, goal_progress)
        self.update_strategy(strategy_type, reward)
        
        # Update Blackboard with current learning state
        self.blackboard.update("learning_state", {
            "best_strategy": self.get_best_strategy(),
            "current_weights": self.weights,
            "last_reward": reward
        })
