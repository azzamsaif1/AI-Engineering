"""
Stage 2 Layer 8 — Performance Analysis.

Builds directly on the Layer 7 Tree-sitter AST (reusing `ASTAnalyzer`) to
produce a static performance profile of source code:

- per-function time-complexity estimate from loop-nesting depth and recursion,
- bottleneck detection (nested loops, deep nesting, high cyclomatic complexity,
  long functions, un-memoized recursion),
- actionable, pattern-driven optimization hints (no hardcoded algorithm names),
- an overall complexity label and a 0-100 performance score.

Deterministic, CPU-only, no training. Supports the same languages as Layer 7
(Python, Java, JavaScript, C++, C).
"""

import logging

from backend.code_understanding.ast_analyzer import (
    ASTAnalyzer,
    _get_parser,
    _FUNC_TYPES,
    _CLASS_TYPES,
)

logger = logging.getLogger(__name__)

# Loop node types per language (drives Big-O nesting estimate).
_LOOP_TYPES = {
    "python": frozenset({"for_statement", "while_statement"}),
    "java": frozenset({"for_statement", "enhanced_for_statement",
                       "while_statement", "do_statement"}),
    "javascript": frozenset({"for_statement", "for_in_statement",
                            "while_statement", "do_statement"}),
    "cpp": frozenset({"for_statement", "for_range_loop",
                     "while_statement", "do_statement"}),
    "c": frozenset({"for_statement", "while_statement", "do_statement"}),
}

# Call node types per language (used for recursion detection). Kept local so
# Layer 8 does not depend on Layer 7 internals that may change independently.
_CALL_TYPES = {
    "python": ("call",),
    "java": ("method_invocation",),
    "javascript": ("call_expression",),
    "cpp": ("call_expression",),
    "c": ("call_expression",),
}

# Thresholds for flagging issues.
_COMPLEXITY_THRESHOLD = 10      # McCabe cyclomatic complexity
_NESTING_THRESHOLD = 4          # control-structure nesting depth
_LENGTH_THRESHOLD = 50          # function length in lines


class PerformanceAnalyzer:
    """Static performance profiler built on the Layer 7 AST."""

    def __init__(self):
        self._ast = ASTAnalyzer()

    def analyze(self, code: str, language: str = "python") -> dict:
        language = self._ast._normalize_language(language)
        parser = _get_parser(language)
        root = parser.parse(code.encode("utf-8")).root_node

        func_type = _FUNC_TYPES.get(language, "function_definition")
        func_nodes = []
        ASTAnalyzer._walk_for_type(root, func_type, func_nodes.append)

        funcs = []
        for node in func_nodes:
            funcs.append(self._profile_function(node, language, code))

        bottlenecks = self._rank_bottlenecks(funcs)
        suggestions = self._suggest(funcs)
        overall = self._overall_complexity(funcs)
        score = self._score(funcs)

        return {
            "language": language,
            "overall_complexity": overall,
            "performance_score": score,
            "functions": funcs,
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
            "summary": self._summary(funcs, overall, score),
        }

    # ------------------------------------------------------------------
    # Per-function profiling
    # ------------------------------------------------------------------

    def _profile_function(self, node, language: str, code: str) -> dict:
        base = self._ast._parse_function_node(node, language, code)
        body = (self._ast._find_child_by_type(node, "block")
                or self._ast._find_child_by_type(node, "statement_block")
                or self._ast._find_child_by_type(node, "compound_statement"))

        func_type = _FUNC_TYPES.get(language, "function_definition")
        class_type = _CLASS_TYPES.get(language, "class_definition")
        stop_types = frozenset({func_type, class_type})

        loop_depth = 0
        self_calls = 0
        if body is not None:
            loop_depth = self._max_loop_depth(body, language, stop_types)
            self_calls = self._count_self_calls(body, language, base["name"], stop_types)

        is_recursive = self_calls > 0
        length = base["end_line"] - base["start_line"] + 1
        time_complexity = self._time_complexity(loop_depth, is_recursive, self_calls)
        issues = self._function_issues(base, loop_depth, is_recursive, self_calls, length)

        return {
            "name": base["name"],
            "start_line": base["start_line"],
            "end_line": base["end_line"],
            "length": length,
            "cyclomatic_complexity": base["complexity"],
            "max_nesting": base["max_nesting"],
            "loop_depth": loop_depth,
            "is_recursive": is_recursive,
            "recursive_calls": self_calls,
            "time_complexity": time_complexity,
            "issues": issues,
        }

    # ------------------------------------------------------------------
    # Loop nesting + recursion
    # ------------------------------------------------------------------

    def _max_loop_depth(self, node, language: str, stop_types, current: int = 0) -> int:
        """Deepest nesting of loops, without descending into nested functions."""
        loops = _LOOP_TYPES.get(language, frozenset())
        best = current
        for child in node.children:
            if child.type in stop_types:
                continue  # nested function/class — its loops aren't this function's cost
            depth = current + (1 if child.type in loops else 0)
            best = max(best, self._max_loop_depth(child, language, stop_types, depth))
        return best

    def _count_self_calls(self, node, language: str, name: str, stop_types, _root=True) -> int:
        """Count direct calls to `name` within this function (recursion)."""
        if not name or name == "<anonymous>":
            return 0
        call_types = _CALL_TYPES.get(language, ("call",))
        count = 0
        if not _root and node.type in stop_types:
            return 0
        if node.type in call_types:
            callee = self._callee_name(node)
            if callee == name or callee.endswith("." + name):
                count += 1
        for child in node.children:
            count += self._count_self_calls(child, language, name, stop_types, _root=False)
        return count

    @staticmethod
    def _callee_name(call_node) -> str:
        """Resolve a call's callee name across languages (self-contained)."""
        name_field = call_node.child_by_field_name("name")
        if name_field is not None and name_field.text:
            return name_field.text.decode("utf-8")
        fn = call_node.child_by_field_name("function")
        if fn is None and call_node.children:
            fn = call_node.children[0]
        if fn is not None and fn.text:
            text = fn.text.decode("utf-8")
            return text.split(".")[-1] if "." in text else text
        return ""

    # ------------------------------------------------------------------
    # Estimates + issues
    # ------------------------------------------------------------------

    @staticmethod
    def _time_complexity(loop_depth: int, is_recursive: bool, self_calls: int) -> str:
        if is_recursive:
            if self_calls >= 2:
                return "O(2^n) worst-case (exponential without memoization)"
            return "O(n) (linear recursion)"
        if loop_depth <= 0:
            return "O(1)"
        if loop_depth == 1:
            return "O(n)"
        if loop_depth == 2:
            return "O(n^2)"
        if loop_depth == 3:
            return "O(n^3)"
        return f"O(n^{loop_depth})"

    def _function_issues(self, base, loop_depth, is_recursive, self_calls, length) -> list[str]:
        issues = []
        if loop_depth >= 2:
            issues.append(f"depth-{loop_depth} nested loops (~O(n^{loop_depth}))")
        if is_recursive and self_calls >= 2:
            issues.append(f"{self_calls} recursive self-calls (exponential risk without memoization)")
        if base["complexity"] >= _COMPLEXITY_THRESHOLD:
            issues.append(f"high cyclomatic complexity ({base['complexity']})")
        if base["max_nesting"] >= _NESTING_THRESHOLD:
            issues.append(f"deep nesting ({base['max_nesting']} levels)")
        if length > _LENGTH_THRESHOLD:
            issues.append(f"long function ({length} lines)")
        return issues

    @staticmethod
    def _rank_bottlenecks(funcs: list[dict]) -> list[dict]:
        flagged = [f for f in funcs if f["issues"]]
        flagged.sort(
            key=lambda f: (f["loop_depth"], f["cyclomatic_complexity"], f["length"]),
            reverse=True,
        )
        return [
            {"name": f["name"], "time_complexity": f["time_complexity"],
             "issues": f["issues"], "start_line": f["start_line"]}
            for f in flagged
        ]

    def _suggest(self, funcs: list[dict]) -> list[str]:
        out = []
        for f in funcs:
            n = f["name"]
            if f["loop_depth"] >= 2:
                out.append(
                    f"`{n}`: depth-{f['loop_depth']} nested loops (~O(n^{f['loop_depth']})). "
                    "Reduce nesting via hashing/sets, precomputation, or a lower-complexity algorithm."
                )
            if f["is_recursive"] and f["recursive_calls"] >= 2:
                out.append(
                    f"`{n}`: {f['recursive_calls']} recursive self-calls. "
                    "Add memoization or convert to iterative dynamic programming to avoid exponential cost."
                )
            if f["cyclomatic_complexity"] >= _COMPLEXITY_THRESHOLD:
                out.append(
                    f"`{n}`: cyclomatic complexity {f['cyclomatic_complexity']}. "
                    "Split into smaller functions to reduce branching and improve testability."
                )
            if f["max_nesting"] >= _NESTING_THRESHOLD:
                out.append(
                    f"`{n}`: nests {f['max_nesting']} levels deep. "
                    "Use guard clauses / early returns to flatten control flow."
                )
            if f["length"] > _LENGTH_THRESHOLD:
                out.append(f"`{n}`: {f['length']} lines. Consider decomposing into helpers.")
        return out

    @staticmethod
    def _overall_complexity(funcs: list[dict]) -> str:
        if not funcs:
            return "O(1)"
        order = {"O(1)": 0, "O(n)": 1, "O(n^2)": 2, "O(n^3)": 3}

        def rank(tc: str) -> int:
            if tc.startswith("O(2^n)"):
                return 100
            if tc.startswith("O(n^"):
                try:
                    return int(tc.split("O(n^")[1].split(")")[0])
                except (ValueError, IndexError):
                    return 4
            return order.get(tc.split(" ")[0], 1)

        worst = max(funcs, key=lambda f: rank(f["time_complexity"]))
        return worst["time_complexity"]

    @staticmethod
    def _score(funcs: list[dict]) -> int:
        score = 100
        for f in funcs:
            if f["loop_depth"] >= 2:
                score -= 10 * (f["loop_depth"] - 1)
            if f["is_recursive"] and f["recursive_calls"] >= 2:
                score -= 20
            if f["cyclomatic_complexity"] >= _COMPLEXITY_THRESHOLD:
                score -= 10
            if f["max_nesting"] >= _NESTING_THRESHOLD:
                score -= 5
            if f["length"] > _LENGTH_THRESHOLD:
                score -= 5
        return max(0, min(100, score))

    @staticmethod
    def _summary(funcs: list[dict], overall: str, score: int) -> str:
        flagged = sum(1 for f in funcs if f["issues"])
        return (
            f"{len(funcs)} function(s), worst-case {overall}, "
            f"performance score {score}/100, {flagged} flagged for optimization"
        )
