"""Evaluation scoring functions for agent performance metrics."""

from typing import List, Dict, Any, Set
import difflib


def calculate_file_correctness_score(
    baseline_files: List[str],
    agent_files: List[str],
) -> float:
    """
    Calculate file correctness score based on overlap between baseline and agent files.

    Args:
        baseline_files: Files modified in the human baseline (merged PR)
        agent_files: Files modified by the agent

    Returns:
        Score between 0.0 and 1.0
        Formula: correct_files / (correct_files + missed_files + extra_files)
    """
    baseline_set = set(baseline_files)
    agent_set = set(agent_files)

    correct_files = len(baseline_set & agent_set)
    missed_files = len(baseline_set - agent_set)
    extra_files = len(agent_set - baseline_set)

    total = correct_files + missed_files + extra_files
    if total == 0:
        return 1.0

    return correct_files / total


def calculate_trajectory_similarity_score(
    baseline_decisions: List[str],
    agent_decisions: List[str],
) -> float:
    """
    Calculate trajectory similarity based on decision overlap.

    Args:
        baseline_decisions: High-level decisions/steps from human baseline
        agent_decisions: High-level decisions/steps from agent

    Returns:
        Score between 0.0 and 1.0 based on sequence similarity
    """
    if not baseline_decisions and not agent_decisions:
        return 1.0

    if not baseline_decisions or not agent_decisions:
        return 0.0

    # Use SequenceMatcher to compare decision sequences
    matcher = difflib.SequenceMatcher(None, baseline_decisions, agent_decisions)
    return matcher.ratio()


def calculate_code_quality_score(
    agent_code: str,
    has_tests: bool = False,
    has_type_hints: bool = False,
    has_error_handling: bool = False,
    follows_conventions: bool = True,
) -> float:
    """
    Calculate code quality score based on various quality indicators.

    Args:
        agent_code: The code produced by the agent
        has_tests: Whether tests were written
        has_type_hints: Whether type hints are present
        has_error_handling: Whether error handling is included
        follows_conventions: Whether code follows project conventions

    Returns:
        Score between 0.0 and 1.0
    """
    # TODO: Implement more sophisticated code quality checks
    # - Syntax validation
    # - Linting
    # - Complexity analysis
    # - Documentation completeness

    score = 0.0
    weights = {
        "tests": 0.3,
        "type_hints": 0.2,
        "error_handling": 0.2,
        "conventions": 0.3,
    }

    if has_tests:
        score += weights["tests"]
    if has_type_hints:
        score += weights["type_hints"]
    if has_error_handling:
        score += weights["error_handling"]
    if follows_conventions:
        score += weights["conventions"]

    return score


def calculate_completeness_score(
    requirements_met: List[bool],
    tests_pass: bool = True,
    no_blockers: bool = True,
) -> float:
    """
    Calculate completeness score based on requirements satisfaction.

    Args:
        requirements_met: Boolean list indicating which requirements were met
        tests_pass: Whether all tests pass
        no_blockers: Whether there are no blockers

    Returns:
        Score between 0.0 and 1.0
    """
    if not requirements_met:
        return 0.0

    # Requirements component (60%)
    requirements_score = sum(requirements_met) / len(requirements_met) * 0.6

    # Tests component (20%)
    tests_score = 0.2 if tests_pass else 0.0

    # Blockers component (20%)
    blockers_score = 0.2 if no_blockers else 0.0

    return requirements_score + tests_score + blockers_score


def calculate_efficiency_score(
    tool_calls: int,
    baseline_tool_calls: int,
    execution_time_ms: int,
    baseline_execution_time_ms: int,
) -> float:
    """
    Calculate efficiency score based on tool usage and execution time.

    Args:
        tool_calls: Number of tool calls made by agent
        baseline_tool_calls: Expected number of tool calls
        execution_time_ms: Agent execution time in milliseconds
        baseline_execution_time_ms: Expected execution time in milliseconds

    Returns:
        Score between 0.0 and 1.0
        Lower is better for both metrics, but within reasonable bounds
    """
    # Tool call efficiency (50%)
    if baseline_tool_calls == 0:
        tool_efficiency = 1.0
    else:
        # Penalize excessive tool calls
        tool_ratio = tool_calls / baseline_tool_calls
        if tool_ratio <= 1.0:
            tool_efficiency = 1.0
        elif tool_ratio <= 1.5:
            tool_efficiency = 0.8
        elif tool_ratio <= 2.0:
            tool_efficiency = 0.6
        else:
            tool_efficiency = 0.4

    # Time efficiency (50%)
    if baseline_execution_time_ms == 0:
        time_efficiency = 1.0
    else:
        time_ratio = execution_time_ms / baseline_execution_time_ms
        if time_ratio <= 1.5:
            time_efficiency = 1.0
        elif time_ratio <= 2.0:
            time_efficiency = 0.8
        elif time_ratio <= 3.0:
            time_efficiency = 0.6
        else:
            time_efficiency = 0.4

    return (tool_efficiency * 0.5) + (time_efficiency * 0.5)


def evaluate_pass_gates(
    metrics: Dict[str, float],
    gates: Dict[str, float],
) -> Dict[str, bool]:
    """
    Evaluate whether each metric passes its quality gate.

    Args:
        metrics: Dictionary of metric name to score
        gates: Dictionary of metric name to minimum passing score

    Returns:
        Dictionary of metric name to pass/fail boolean
    """
    results = {}
    for metric_name, score in metrics.items():
        gate = gates.get(metric_name, 0.0)
        results[metric_name] = score >= gate
    return results


def calculate_overall_pass(pass_results: Dict[str, bool]) -> bool:
    """
    Calculate overall pass/fail based on individual metric results.

    Args:
        pass_results: Dictionary of metric name to pass/fail boolean

    Returns:
        True if ALL metrics pass, False otherwise
    """
    return all(pass_results.values())


def calculate_improvement_rate(
    current_score: float,
    previous_score: float,
) -> float:
    """
    Calculate improvement rate between iterations.

    Args:
        current_score: Score in current iteration
        previous_score: Score in previous iteration

    Returns:
        Improvement rate (positive = improvement, negative = regression)
    """
    if previous_score == 0.0:
        return 1.0 if current_score > 0.0 else 0.0

    return (current_score - previous_score) / previous_score
