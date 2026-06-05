"""
Prediction & Correction Engine
An intelligent engine that predicts user input,
corrects mistakes before they happen,
and learns from coding behavior.
"""

import json
from collections import defaultdict, Counter
from difflib import SequenceMatcher
from datetime import datetime


class PredictionEngine:

    def __init__(self, user_id):

        self.user_id = user_id

        self.typing_history = []
        self.common_patterns = defaultdict(int)
        self.muscle_memory = {}
        self.error_history = []

        self.load_user_history()

    # =========================================================
    # USER HISTORY
    # =========================================================

    def load_user_history(self):
        """Load previous user typing behavior."""

        self.muscle_memory = {
            "average_speed": 2.5,
            "common_typos": [],
            "preferred_keywords": []
        }

    # =========================================================
    # CHARACTER PREDICTION
    # =========================================================

    def predict_next_character(self, current_line, cursor_position):
        """
        Predict the next character before the user types it.
        """

        if not current_line:
            return None

        patterns = {
            "def ": "function definition",
            "for ": "for loop",
            "if ": "if statement",
            "while ": "while loop",
            "return ": "return statement",
            "import ": "import statement",
            "from ": "from import statement",
            "class ": "class definition",
            "try:": "try block",
            "except:": "exception block",
            "else:": "else block"
        }

        # Detect matching coding patterns
        for pattern, description in patterns.items():

            if (
                current_line.endswith(pattern[:-1])
                or pattern.startswith(current_line[-3:])
            ):

                next_char = (
                    pattern[len(current_line)][0]
                    if len(pattern) > len(current_line)
                    else " "
                )

                return {
                    "predicted_char": next_char,
                    "confidence": 0.85,
                    "description": description
                }

        # Auto-close brackets and quotes
        auto_pairs = {
            "(": ")",
            "[": "]",
            "{": "}",
            '"': '"',
            "'": "'"
        }

        for opener, closer in auto_pairs.items():

            if current_line.endswith(opener):

                if opener in ['"', "'"]:
                    if current_line.count(opener) % 2 == 1:
                        return {
                            "predicted_char": closer,
                            "confidence": 0.88,
                            "description": "Closing quote"
                        }

                else:
                    return {
                        "predicted_char": closer,
                        "confidence": 0.92,
                        "description": "Closing bracket"
                    }

        return None

    # =========================================================
    # CHARACTER COMPARISON
    # =========================================================

    def compare_character(self, expected_char, actual_char):
        """
        Compare predicted character with actual typed character.
        """

        if expected_char == actual_char:

            return {
                "match": True,
                "message": None
            }

        return {
            "match": False,
            "message":
                f'Expected "{expected_char}" '
                f'but received "{actual_char}"',
            "suggestion":
                f'Did you mean "{expected_char}"?'
        }

    # =========================================================
    # LINE COMPARISON
    # =========================================================

    def compare_line(self, user_line, expected_line):
        """
        Compare a full line with the predicted line.
        """

        similarity = SequenceMatcher(
            None,
            user_line,
            expected_line
        ).ratio()

        differences = []

        if similarity < 0.9:

            import difflib

            diff = difflib.ndiff(user_line, expected_line)

            for item in diff:

                if item.startswith("- "):
                    differences.append({
                        "type": "missing",
                        "text": item[2:]
                    })

                elif item.startswith("+ "):
                    differences.append({
                        "type": "extra",
                        "text": item[2:]
                    })

        return {
            "similarity": round(similarity, 2),
            "is_correct": similarity > 0.8,
            "differences": differences[:5],
            "suggestion":
                expected_line if similarity < 0.7 else None
        }

    # =========================================================
    # RECORD USER TYPING
    # =========================================================

    def record_typing(self, line, time_taken, was_correct):
        """
        Store typing behavior and build digital muscle memory.
        """

        self.typing_history.append({
            "line": line,
            "time": time_taken,
            "correct": was_correct,
            "timestamp": datetime.now().isoformat()
        })

        # Update average typing speed
        recent_times = [
            item["time"]
            for item in self.typing_history[-50:]
        ]

        if recent_times:
            self.muscle_memory["average_speed"] = (
                sum(recent_times) / len(recent_times)
            )

        # Store typo patterns
        if not was_correct:

            words = line.split()

            for word in words:
                if len(word) > 3:
                    self.muscle_memory["common_typos"].append(word)

    # =========================================================
    # PREEMPTIVE CORRECTION
    # =========================================================

    def preemptive_correction(self, current_line, cursor_position):
        """
        Detect and correct mistakes before they happen.
        """

        prediction = self.predict_next_character(
            current_line,
            cursor_position
        )

        if not prediction:
            return None

        common_errors = {

            "range(n-1)": "range(n-i-1)",

            "for j in range(n)":
                "for j in range(n-i-1)",

            "if a = b":
                "if a == b",

            "while true":
                "while True",

            "print x":
                "print(x)"
        }

        for error, correction in common_errors.items():

            if error in current_line:

                return {
                    "detected": True,
                    "error": error,
                    "correction": correction,
                    "message":
                        f'⚠️ Common mistake detected: '
                        f'"{error}" → "{correction}"',
                    "preemptive": True
                }

        return {
            "detected": False,
            "prediction": prediction,
            "message": None
        }

    # =========================================================
    # REVERSE LEARNING
    # =========================================================

    def reverse_learning(
        self,
        user_code,
        ghost_code,
        user_understood
    ):
        """
        Learn from user corrections and understanding.
        """

        if not user_understood:

            return {
                "learned": False,
                "message":
                    "Correction not understood yet. "
                    "The system will explain it later."
            }

        user_lines = user_code.split("\n")
        ghost_lines = ghost_code.split("\n")

        corrections_made = []

        for index, (user_line, ghost_line) in enumerate(
            zip(user_lines, ghost_lines)
        ):

            if (
                user_line != ghost_line
                and user_line.strip()
                and ghost_line.strip()
            ):

                corrections_made.append({
                    "line": index + 1,
                    "from": user_line,
                    "to": ghost_line
                })

        if corrections_made:

            self.error_history.append({
                "timestamp": datetime.now().isoformat(),
                "corrections": corrections_made,
                "user_understood": user_understood
            })

        return {
            "learned": True,
            "corrections_count": len(corrections_made),
            "total_errors": len(self.error_history),
            "message":
                f"✅ Learned from "
                f"{len(corrections_made)} corrections."
        }

    # =========================================================
    # LEARNING SUMMARY
    # =========================================================

    def get_learning_summary(self):
        """
        Return a summary of user learning progress.
        """

        total_attempts = len(self.typing_history)

        correct_attempts = len([
            item
            for item in self.typing_history
            if item["correct"]
        ])

        accuracy = (
            correct_attempts / total_attempts * 100
            if total_attempts > 0
            else 0
        )

        common_typos = self.muscle_memory.get(
            "common_typos",
            []
        )

        typo_stats = Counter(common_typos).most_common(5)

        return {

            "total_attempts": total_attempts,

            "accuracy": round(accuracy, 1),

            "average_speed":
                round(
                    self.muscle_memory["average_speed"],
                    2
                ),

            "common_mistakes": [
                {
                    "word": word,
                    "count": count
                }
                for word, count in typo_stats
            ],

            "total_errors":
                len(self.error_history),

            "learning_progress":
                min(100, total_attempts * 2)
        }


# =============================================================
# EXAMPLE USAGE
# =============================================================

if __name__ == "__main__":

    engine = PredictionEngine(user_id="azzam")

    line = "for "

    prediction = engine.predict_next_character(line, len(line))

    print("Prediction:")
    print(prediction)

    correction = engine.preemptive_correction(
        "if a = b",
        8
    )

    print("\nPreemptive Correction:")
    print(correction)

    engine.record_typing(
        line="print(x)",
        time_taken=1.8,
        was_correct=True
    )

    summary = engine.get_learning_summary()

    print("\nLearning Summary:")
    print(summary)