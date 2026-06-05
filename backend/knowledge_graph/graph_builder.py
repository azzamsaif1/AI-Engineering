# backend/knowledge_graph/graph_builder.py
from neo4j import GraphDatabase

class KnowledgeGraphBuilder:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def add_concept(self, name, category, level='beginner'):
        with self.driver.session() as session:
            session.run(
                "MERGE (c:Concept {name: $name}) "
                "SET c.category = $category, c.level = $level",
                name=name, category=category, level=level
            )
    
    def add_relation(self, concept1, concept2, relation_type):
        with self.driver.session() as session:
            session.run(
                f"MATCH (a:Concept {{name: $c1}}), (b:Concept {{name: $c2}}) "
                f"MERGE (a)-[:{relation_type}]->(b)",
                c1=concept1, c2=concept2
            )
    
    def get_learning_path(self, target_concept):
        with self.driver.session() as session:
            result = session.run(
                "MATCH path = shortestPath((start)-[:REQUIRES*]->(end {name: $target})) "
                "RETURN [node in nodes(path) | node.name] as path",
                target=target_concept
            )
            record = result.single()
            return record['path'] if record else []
    
    def close(self):
        self.driver.close()