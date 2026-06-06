"""
Stage 2 Layer 7 — Code Understanding via Tree-sitter AST Analysis.

Production-ready AST analyzer that parses code in Python, Java, JavaScript,
and C++ into structured output: functions, classes, imports, call graph,
control-flow metrics, and cyclomatic complexity.

No GPU required. No training. Deterministic and fast.
"""

import logging
from typing import Optional

from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language registry — lazy-loaded to avoid import-time cost
# ---------------------------------------------------------------------------

_LANGUAGES: dict[str, Language] = {}
_PARSERS: dict[str, Parser] = {}

# Mapping of user-facing language name → (tree-sitter module, ts module attr)
_LANG_MODULES = {
    "python": "tree_sitter_python",
    "java": "tree_sitter_java",
    "javascript": "tree_sitter_javascript",
    "cpp": "tree_sitter_cpp",
    "c": "tree_sitter_cpp",  # C is a subset; cpp grammar handles it
}

# AST node types per language for structural extraction
_FUNC_TYPES = {
    "python": "function_definition",
    "java": "method_declaration",
    "javascript": "function_declaration",
    "cpp": "function_definition",
    "c": "function_definition",
}

_CLASS_TYPES = {
    "python": "class_definition",
    "java": "class_declaration",
    "javascript": "class_declaration",
    "cpp": "class_specifier",
    "c": "struct_specifier",
}

_IMPORT_TYPES = {
    "python": ("import_statement", "import_from_statement"),
    "java": ("import_declaration",),
    "javascript": ("import_statement",),
    "cpp": ("preproc_include",),
    "c": ("preproc_include",),
}

_BRANCH_TYPES = frozenset({
    "if_statement", "elif_clause",
    "for_statement", "for_in_clause", "for_in_statement",
    "for_range_loop", "enhanced_for_statement",
    "while_statement", "do_statement",
    "switch_statement", "case_statement", "switch_section",
    "catch_clause", "except_clause",
    "conditional_expression", "ternary_expression",
    "boolean_operator", "&&", "||",
})


def _get_language(lang: str) -> Language:
    """Lazy-load a tree-sitter Language."""
    if lang not in _LANGUAGES:
        mod_name = _LANG_MODULES.get(lang)
        if not mod_name:
            raise ValueError(f"Unsupported language: {lang}")
        import importlib
        mod = importlib.import_module(mod_name)
        _LANGUAGES[lang] = Language(mod.language())
    return _LANGUAGES[lang]


def _get_parser(lang: str) -> Parser:
    """Get or create a Parser for the given language."""
    if lang not in _PARSERS:
        _PARSERS[lang] = Parser(_get_language(lang))
    return _PARSERS[lang]


# ---------------------------------------------------------------------------
# AST Analyzer
# ---------------------------------------------------------------------------

class ASTAnalyzer:
    """
    Parses source code into a Tree-sitter AST and extracts structured
    information: functions, classes, imports, call graph, and complexity.
    """

    SUPPORTED_LANGUAGES = tuple(_LANG_MODULES.keys())

    def analyze(self, code: str, language: str = "python") -> dict:
        """
        Full code analysis pipeline.

        Returns dict with keys: language, structure, metrics, call_graph, summary.
        """
        language = self._normalize_language(language)
        parser = _get_parser(language)
        tree = parser.parse(code.encode("utf-8"))
        root = tree.root_node

        if root.has_error:
            logger.warning("Tree-sitter reported parse errors for %s code", language)

        functions = self._extract_functions(root, language, code)
        classes = self._extract_classes(root, language, code)
        imports = self._extract_imports(root, language, code)
        call_graph = self._extract_call_graph(root, language, code)

        total_funcs = len(functions)
        complexities = [f["complexity"] for f in functions] if functions else [1]
        lengths = [f["end_line"] - f["start_line"] + 1 for f in functions] if functions else [0]

        metrics = {
            "total_functions": total_funcs,
            "total_classes": len(classes),
            "total_imports": len(imports),
            "max_complexity": max(complexities),
            "avg_complexity": round(sum(complexities) / len(complexities), 2),
            "max_nesting": max((f["max_nesting"] for f in functions), default=0),
            "avg_function_length": round(sum(lengths) / max(len(lengths), 1), 1),
            "total_lines": code.count("\n") + 1,
            "has_parse_errors": root.has_error,
        }

        parts = []
        if total_funcs:
            parts.append(f"{total_funcs} function{'s' if total_funcs != 1 else ''}")
        if classes:
            parts.append(f"{len(classes)} class{'es' if len(classes) != 1 else ''}")
        if imports:
            parts.append(f"{len(imports)} import{'s' if len(imports) != 1 else ''}")
        parts.append(f"avg complexity {metrics['avg_complexity']}")

        return {
            "language": language,
            "structure": {
                "functions": functions,
                "classes": classes,
                "imports": imports,
            },
            "metrics": metrics,
            "call_graph": call_graph,
            "summary": ", ".join(parts),
        }

    # ------------------------------------------------------------------
    # Language normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_language(lang: str) -> str:
        lang = lang.lower().strip()
        aliases = {
            "py": "python",
            "python3": "python",
            "js": "javascript",
            "typescript": "javascript",  # TS grammar not installed; JS is close
            "ts": "javascript",
            "c++": "cpp",
            "cxx": "cpp",
        }
        lang = aliases.get(lang, lang)
        if lang not in _LANG_MODULES:
            raise ValueError(
                f"Unsupported language '{lang}'. "
                f"Supported: {', '.join(_LANG_MODULES.keys())}"
            )
        return lang

    # ------------------------------------------------------------------
    # Function extraction
    # ------------------------------------------------------------------

    def _extract_functions(self, root, language: str, code: str) -> list[dict]:
        target_type = _FUNC_TYPES.get(language, "function_definition")
        functions = []
        self._walk_for_type(root, target_type, lambda node: functions.append(
            self._parse_function_node(node, language, code)
        ))
        return functions

    def _parse_function_node(self, node, language: str, code: str) -> dict:
        name = self._child_text(node, "identifier", code) or self._child_text(node, "property_identifier", code)
        # C++/Java: name is inside a function_declarator/declarator child
        if not name:
            for child in node.children:
                if child.type in ("function_declarator", "declarator"):
                    name = self._child_text(child, "identifier", code)
                    if name:
                        break
        name = name or "<anonymous>"
        params = self._extract_parameters(node, language, code)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        body = self._find_child_by_type(node, "block") or self._find_child_by_type(node, "statement_block") or self._find_child_by_type(node, "compound_statement")
        complexity = 1
        max_nesting = 0
        if body:
            complexity = self._cyclomatic_complexity(body)
            max_nesting = self._max_nesting_depth(body)

        return {
            "name": name,
            "parameters": params,
            "start_line": start_line,
            "end_line": end_line,
            "complexity": complexity,
            "max_nesting": max_nesting,
        }

    def _extract_parameters(self, func_node, language: str, code: str) -> list[str]:
        param_container = (
            self._find_child_by_type(func_node, "parameters")
            or self._find_child_by_type(func_node, "formal_parameters")
            or self._find_child_by_type(func_node, "parameter_list")
        )
        if not param_container:
            return []
        params = []
        for child in param_container.children:
            if child.type in ("identifier", "typed_parameter", "default_parameter",
                              "formal_parameter", "parameter_declaration",
                              "required_parameter", "optional_parameter"):
                text = child.text.decode("utf-8") if child.text else ""
                if text and text not in ("(", ")", ",", "self", "this"):
                    params.append(text)
        return params

    # ------------------------------------------------------------------
    # Class extraction
    # ------------------------------------------------------------------

    def _extract_classes(self, root, language: str, code: str) -> list[dict]:
        target_type = _CLASS_TYPES.get(language, "class_definition")
        classes = []
        self._walk_for_type(root, target_type, lambda node: classes.append(
            self._parse_class_node(node, language, code)
        ))
        return classes

    def _parse_class_node(self, node, language: str, code: str) -> dict:
        name = self._child_text(node, "identifier", code) or self._child_text(node, "type_identifier", code) or "<anonymous>"
        methods = []
        method_type = _FUNC_TYPES.get(language, "function_definition")
        self._walk_for_type(node, method_type, lambda n: methods.append(
            self._child_text(n, "identifier", code) or "<anonymous>"
        ))
        return {
            "name": name,
            "methods": methods,
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
        }

    # ------------------------------------------------------------------
    # Import extraction
    # ------------------------------------------------------------------

    def _extract_imports(self, root, language: str, code: str) -> list[dict]:
        import_types = _IMPORT_TYPES.get(language, ())
        imports = []
        for itype in import_types:
            self._walk_for_type(root, itype, lambda node: imports.append({
                "text": node.text.decode("utf-8").strip() if node.text else "",
                "start_line": node.start_point[0] + 1,
            }))
        return imports

    # ------------------------------------------------------------------
    # Call graph extraction
    # ------------------------------------------------------------------

    def _extract_call_graph(self, root, language: str, code: str) -> list[dict]:
        """Extract function call relationships from the AST."""
        calls = []
        func_type = _FUNC_TYPES.get(language, "function_definition")

        def _visit_function(func_node):
            caller = self._child_text(func_node, "identifier", code) or "<module>"
            self._walk_for_type(func_node, "call", lambda call_node: (
                calls.append({
                    "caller": caller,
                    "callee": self._extract_callee_name(call_node, code),
                })
            ))

        # Module-level calls (not inside a function or class)
        class_type = _CLASS_TYPES.get(language, "class_definition")
        for child in root.children:
            if child.type not in (func_type, class_type):
                self._walk_for_type(child, "call", lambda call_node: (
                    calls.append({
                        "caller": "<module>",
                        "callee": self._extract_callee_name(call_node, code),
                    })
                ))

        # Calls inside functions
        self._walk_for_type(root, func_type, _visit_function)

        # Deduplicate
        seen = set()
        unique = []
        for c in calls:
            key = (c["caller"], c["callee"])
            if key not in seen and c["callee"]:
                seen.add(key)
                unique.append(c)
        return unique

    @staticmethod
    def _extract_callee_name(call_node, code: str) -> str:
        """Get the function name from a call node."""
        if not call_node.children:
            return ""
        first = call_node.children[0]
        if first.type == "identifier":
            return first.text.decode("utf-8") if first.text else ""
        if first.type == "attribute":
            return first.text.decode("utf-8") if first.text else ""
        return first.text.decode("utf-8") if first.text else ""

    # ------------------------------------------------------------------
    # Complexity metrics
    # ------------------------------------------------------------------

    def _cyclomatic_complexity(self, node) -> int:
        """Estimate cyclomatic complexity (McCabe) by counting branch points + 1."""
        return 1 + self._count_branches(node)

    def _count_branches(self, node) -> int:
        """Count decision/branch points in the AST subtree."""
        count = 1 if node.type in _BRANCH_TYPES else 0
        for child in node.children:
            count += self._count_branches(child)
        return count

    def _max_nesting_depth(self, node, current_depth: int = 0) -> int:
        """Find the maximum nesting depth of control structures."""
        max_depth = current_depth
        for child in node.children:
            child_depth = current_depth
            if child.type in _BRANCH_TYPES:
                child_depth = current_depth + 1
            max_depth = max(max_depth, self._max_nesting_depth(child, child_depth))
        return max_depth

    # ------------------------------------------------------------------
    # AST traversal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _walk_for_type(node, target_type: str, callback):
        """Walk the AST and call `callback` for every node of `target_type`."""
        if node.type == target_type:
            callback(node)
        for child in node.children:
            ASTAnalyzer._walk_for_type(child, target_type, callback)

    @staticmethod
    def _child_text(node, child_type: str, code: str) -> Optional[str]:
        """Get the text of the first child with the given type."""
        for child in node.children:
            if child.type == child_type:
                return child.text.decode("utf-8") if child.text else None
        return None

    @staticmethod
    def _find_child_by_type(node, child_type: str):
        """Find the first child node with the given type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None
