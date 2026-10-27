from docusense.schemas import Hit
from docusense.syllabus import (COVERED, NOT_FOUND, PARTIAL, assign_topic,
                                classify, parse_topics)


def hit(text, d=0.4, src="n.pdf", page=1):
    return Hit(text, src, page, d)


def test_parse_topics_handles_bullets_units_and_dupes():
    text = """Unit 1: Sorting, Searching; Hashing
- Binary Trees
2. Graph Traversal
binary trees

x"""
    assert parse_topics(text) == [
        "Sorting", "Searching", "Hashing", "Binary Trees", "Graph Traversal"]


def test_covered_needs_two_strong_chunks():
    hits = [hit("Binary search tree insertion and binary tree traversal"),
            hit("A binary tree has nodes; binary tree height")]
    assert classify("Binary Trees", hits).status == COVERED


def test_partial_with_one_chunk():
    c = classify("Binary Trees", [hit("binary trees are covered briefly here")])
    assert c.status == PARTIAL and c.files == ["n.pdf"]


def test_similar_but_no_shared_terms_is_not_found():
    assert classify("Binary Trees", [hit("Cooking pasta with tomato sauce", d=0.3)]).status == NOT_FOUND


def test_far_chunks_ignored_and_empty():
    assert classify("Binary Trees", [hit("binary trees", d=0.9)]).status == NOT_FOUND
    assert classify("Binary Trees", []).status == NOT_FOUND


def test_assign_topic():
    topics = ["Binary Trees", "Graph Traversal"]
    assert assign_topic("Which traversal is used for a graph in BFS?", topics) == "Graph Traversal"
    assert assign_topic("What is the capital of France?", topics) is None
