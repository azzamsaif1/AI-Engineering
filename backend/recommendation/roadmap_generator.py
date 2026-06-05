# backend/recommendation/roadmap_generator.py
class RoadmapGenerator:
    def generate_roadmap(self, concepts, target_concept=None):
        if not concepts:
            return []
        
        # خريطة تعلم بسيطة
        roadmap = []
        for i, concept in enumerate(concepts[:10]):
            roadmap.append({
                'step': i + 1,
                'concept': concept.get('text', str(concept)),
                'estimated_time': '2 hours'
            })
        
        return roadmap