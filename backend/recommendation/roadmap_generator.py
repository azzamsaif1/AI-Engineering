# backend/recommendation/roadmap_generator.py
"""Learning-roadmap generator.

Produces an ordered set of steps from discovered concepts. Estimated time is
derived from each concept's detected level/score rather than a hardcoded constant,
so the output adapts to the input instead of always reporting "2 hours".
"""

# Base study time (minutes) per detected difficulty level.
_LEVEL_MINUTES = {
    "beginner": 45,
    "intermediate": 90,
    "advanced": 150,
}
_DEFAULT_MINUTES = 60


class RoadmapGenerator:
    def generate_roadmap(self, concepts, target_concept=None):
        if not concepts:
            return []

        roadmap = []
        for i, concept in enumerate(concepts):
            if isinstance(concept, dict):
                name = concept.get('text', concept.get('name', str(concept)))
                level = (concept.get('level') or '').lower()
                score = concept.get('score') or concept.get('relevance')
            else:
                name = str(concept)
                level = ''
                score = None

            minutes = _LEVEL_MINUTES.get(level, _DEFAULT_MINUTES)
            # Higher-relevance concepts warrant a little more depth.
            if isinstance(score, (int, float)):
                minutes = int(minutes * (1.0 + min(max(score, 0.0), 1.0) * 0.5))

            roadmap.append({
                'step': i + 1,
                'concept': name,
                'estimated_minutes': minutes,
                'estimated_time': self._humanize(minutes),
            })

        return roadmap

    @staticmethod
    def _humanize(minutes):
        if minutes < 60:
            return f"{minutes} min"
        hours = minutes / 60
        if hours == int(hours):
            return f"{int(hours)} hour" + ("s" if hours != 1 else "")
        return f"{hours:.1f} hours"
