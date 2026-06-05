"""
Ghost Coder Engine
An adaptive AI coding mentor that learns from the user,
corrects mistakes, predicts code, and gradually disappears
as the user masters programming.
"""

import random
from collections import defaultdict


class GhostCoderEngine:
    def __init__(self, user_id):
        self.user_id = user_id
        self.mastery_level = 0  # 0-5, where 5 = fully independent
        self.learning_patterns = defaultdict(list)
        self.style_profile = {}
        self.common_mistakes = []
        self.load_user_style()

    # =========================================================
    # USER STYLE SYSTEM
    # =========================================================

    def load_user_style(self):
        """Load user coding style preferences."""
        self.style_profile = {
            "indentation": "spaces",
            "indent_size": 4,
            "naming_convention": "snake_case",
            "comment_style": "minimal",
            "line_spacing": 1,
            "preferred_language": "python"
        }

    # =========================================================
    # CODE PREDICTION
    # =========================================================

    def predict_next_line(self, current_code):
        """
        Predict the next line of code based on context.
        """

        lines = current_code.split("\n")

        if not lines:
            return None

        last_line = lines[-1].strip()
        predictions = []

        # Function detection
        if last_line.startswith("def "):
            predictions.extend([
                {
                    "line": "    pass",
                    "confidence": 0.92,
                    "explanation": "Temporary function body."
                },
                {
                    "line": "    # TODO: implement logic",
                    "confidence": 0.85,
                    "explanation": "Suggested placeholder comment."
                }
            ])

        # Loop detection
        elif last_line.startswith("for ") and ":" in last_line:
            predictions.append({
                "line": "    print(item)",
                "confidence": 0.81,
                "explanation": "Typical loop body example."
            })

        # Conditional detection
        elif last_line.startswith("if ") and ":" in last_line:
            predictions.extend([
                {
                    "line": "    return True",
                    "confidence": 0.84,
                    "explanation": "Common conditional return."
                },
                {
                    "line": "else:",
                    "confidence": 0.65,
                    "explanation": "Possible else branch."
                }
            ])

        # Return statement
        elif last_line.startswith("return"):
            predictions.append({
                "line": "",
                "confidence": 0.95,
                "explanation": "Likely end of function."
            })

        # Generic continuation
        if not predictions:
            predictions.append({
                "line": "    # continue coding...",
                "confidence": 0.55,
                "explanation": "General continuation."
            })

        predictions.sort(
            key=lambda item: item["confidence"],
            reverse=True
        )

        return predictions[0]

    # =========================================================
    # GHOST VISIBILITY SYSTEM
    # =========================================================

    def should_appear(self, mistake_rate):
        """
        Decide whether the ghost should appear.
        The better the user becomes, the less visible it gets.
        """

        if mistake_rate < 0.1 and self.mastery_level < 5:
            self.mastery_level += 1

        elif mistake_rate > 0.3 and self.mastery_level > 0:
            self.mastery_level -= 1

        visibility_table = {
            0: 1.0,
            1: 0.9,
            2: 0.7,
            3: 0.5,
            4: 0.3,
            5: 0.0
        }

        chance = visibility_table.get(self.mastery_level, 0)

        return random.random() < chance

    # =========================================================
    # CODE ANALYSIS
    # =========================================================

    def analyze_user_code(self, user_code):
        """
        Analyze user code and detect common mistakes.
        """

        errors = []
        suggestions = []

        lines = user_code.split("\n")

        for index, line in enumerate(lines):

            # Bubble sort optimization check
            if (
                "for j in range" in line
                and "n-1" in line
                and "n-i-1" not in line
            ):
                errors.append({
                    "line": index + 1,
                    "original": line,
                    "correction": line.replace(
                        "range(n-1)",
                        "range(n-i-1)"
                    ),
                    "type": "loop_range",
                    "explanation":
                        "Use range(n-i-1) to avoid unnecessary comparisons."
                })

            # Unused loop variable
            if (
                "for i in range" in line
                and "i" not in user_code.replace(line, "")
            ):
                suggestions.append({
                    "line": index + 1,
                    "original": line,
                    "type": "unused_variable",
                    "explanation":
                        "Variable 'i' seems unused. Consider using '_' instead."
                })

            # Indentation issues
            if (
                line
                and not line.startswith((" ", "\t"))
                and index > 0
                and lines[index - 1].strip().endswith(":")
            ):
                suggestions.append({
                    "line": index + 1,
                    "original": line,
                    "type": "indentation",
                    "explanation":
                        "This line requires indentation."
                })

        return {
            "errors": errors,
            "suggestions": suggestions
        }

    # =========================================================
    # GHOST CORRECTION ENGINE
    # =========================================================

    def generate_ghost_code(self, user_code):
        """
        Generate corrected ghost code.
        """

        analysis = self.analyze_user_code(user_code)

        lines = user_code.split("\n")

        for error in analysis["errors"]:

            line_index = error["line"] - 1

            if line_index < len(lines):
                lines[line_index] = error["correction"]

        ghost_code = "\n".join(lines)

        return {
            "ghost_code": ghost_code,
            "corrections": analysis["errors"],
            "suggestions": analysis["suggestions"],
            "mastery_level": self.mastery_level,
            "visibility": self.should_appear(
                len(analysis["errors"]) / max(len(lines), 1)
            )
        }

    # =========================================================
    # LEARNING SYSTEM
    # =========================================================

    def learn_from_user(self, user_code, ghost_code, corrections):
        """
        Learn from user patterns and corrections.
        """

        user_lines = user_code.split("\n")
        ghost_lines = ghost_code.split("\n")

        differences = []

        for index, (user_line, ghost_line) in enumerate(
            zip(user_lines, ghost_lines)
        ):
            if user_line != ghost_line:
                differences.append({
                    "line": index + 1,
                    "user_line": user_line,
                    "ghost_line": ghost_line
                })

        # Store common mistakes
        for correction in corrections:
            if correction not in self.common_mistakes:
                self.common_mistakes.append(correction)

        # Update mastery level
        if len(corrections) == 0:
            self.mastery_level = min(5, self.mastery_level + 0.5)

        elif len(corrections) > 3:
            self.mastery_level = max(0, self.mastery_level - 0.5)

        # Store learning history
        self.learning_patterns["user_code"].append(user_code)
        self.learning_patterns["ghost_code"].append(ghost_code)
        self.learning_patterns["diff"].append(differences)

        return {
            "learned": True,
            "mastery_level": self.mastery_level,
            "common_mistakes": self.common_mistakes[:5],
            "difference_count": len(differences)
        }

    # =========================================================
    # EXPLANATION ENGINE
    # =========================================================

    def explain_error(self, error):
        """
        Generate educational explanations for mistakes.
        """

        explanations = {
            "loop_range":
                "Bubble Sort should use range(n-i-1) because the largest "
                "elements are already sorted after each iteration.",

            "unused_variable":
                "The loop variable is unused. Use '_' to indicate it is ignored.",

            "indentation":
                "Python requires indentation inside loops, conditions, and functions."
        }

        return explanations.get(
            error.get("type", ""),
            "A coding issue was detected."
        )

    # =========================================================
    # FUTURE CODE GENERATOR
    # =========================================================

    def generate_future_code(self):

        future_languages = [
            "rust",
            "go",
            "swift",
            "kotlin",
            "typescript"
        ]

        selected_language = random.choice(future_languages)

        templates = {

            "rust": """
fn bubble_sort<T: Ord>(arr: &mut [T]) {
    let mut n = arr.len();

    loop {
        let mut swapped = false;

        for i in 1..n {
            if arr[i - 1] > arr[i] {
                arr.swap(i - 1, i);
                swapped = true;
            }
        }

        if !swapped {
            break;
        }

        n -= 1;
    }
}
""",

            "go": """
func bubbleSort(arr []int) {
    n := len(arr)

    for i := 0; i < n-1; i++ {
        for j := 0; j < n-i-1; j++ {

            if arr[j] > arr[j+1] {
                arr[j], arr[j+1] = arr[j+1], arr[j]
            }
        }
    }
}
""",

            "swift": """
func bubbleSort(_ arr: inout [Int]) {

    for i in 0..<arr.count {

        for j in 0..<arr.count-i-1 {

            if arr[j] > arr[j+1] {
                arr.swapAt(j, j+1)
            }
        }
    }
}
"""
        }

        code = templates.get(
            selected_language,
            f"// Future language: {selected_language}"
        )

        return {
            "language": selected_language,
            "code": code,
            "message":
                f"You will soon learn {selected_language.upper()}!"
        }

    # =========================================================
    # GHOST ROOM
    # =========================================================

    def get_ghost_room(self):

        return {
            "room_name": "Ghost Room",
            "description":
                "A private learning space with no competition.",
            "mastery_level": self.mastery_level,
            "common_mistakes": self.common_mistakes[:3],
            "encouragement": self.get_encouragement_message()
        }

    # =========================================================
    # ENCOURAGEMENT SYSTEM
    # =========================================================

    def get_encouragement_message(self):

        messages = {
            0: "Every expert started as a beginner.",
            1: "You're improving steadily.",
            2: "Great progress. Keep going.",
            3: "Excellent work. Your skills are growing fast.",
            4: "You're close to mastery.",
            5: "You are now an independent programmer."
        }

        return messages.get(
            self.mastery_level,
            "Keep coding and never stop learning."
        )


# =============================================================
# EXAMPLE USAGE
# =============================================================

if __name__ == "__main__":

    ghost = GhostCoderEngine(user_id="azzam")

    sample_code = """
for i in range(n):
for j in range(n-1):
    print(j)
"""

    analysis = ghost.generate_ghost_code(sample_code)

    print("=== Ghost Corrected Code ===")
    print(analysis["ghost_code"])

    print("\n=== Suggestions ===")
    for suggestion in analysis["suggestions"]:
        print("-", suggestion["explanation"])

    print("\n=== Future Code ===")
    future = ghost.generate_future_code()
    print(future["message"])
    print(future["code"])