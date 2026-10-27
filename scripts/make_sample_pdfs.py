"""Create synthetic demo PDFs in data/samples/ (no private data)."""
from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parent.parent / "data" / "samples"
OUT.mkdir(parents=True, exist_ok=True)


def make(name: str, pages: list[str]) -> None:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 790), text, fontsize=11)
    doc.save(OUT / name)
    doc.close()


make("ds_notes.pdf", [
    "Binary Trees\nA binary tree is a tree data structure in which each node has at most two "
    "children, called left and right. A binary search tree keeps left < node < right, which "
    "makes search, insertion and deletion O(log n) on average. Tree traversal can be inorder, "
    "preorder or postorder.",
    "Graph Traversal\nBreadth-first search (BFS) visits graph vertices level by level using a "
    "queue. Depth-first search (DFS) uses a stack or recursion. Graph traversal runs in "
    "O(V + E) time.",
])
make("ds_slides.pdf", [
    "Sorting algorithms\nQuick sort picks a pivot and partitions the array. Average time is "
    "O(n log n). Merge sort divides the array and merges sorted halves, always O(n log n). "
    "Binary trees can also be used for sorting (tree sort).",
])
make("ds_quiz.pdf", [
    "Data Structures Quiz\n"
    "Q1. Which traversal of a binary search tree gives sorted order?\n"
    "(A) Preorder\n(B) Inorder\n(C) Postorder\n(D) Level order\n"
    "Q2. Which data structure does BFS use?\n"
    "(A) Stack\n(B) Queue\n(C) Heap\n(D) Tree\n"
    "Q3. Average time complexity of quick sort?\n"
    "(A) O(n)\n(B) O(n^2)\n(C) O(n log n)\n(D) O(log n)\n",
    "Q4. Which structure does DFS use?\n(A) Queue\n(B) Stack\n(C) Array\n(D) Set\n"
    "Answer Key\n1. B\n2. B\n3. C\n4. B\n",
])
make("syllabus.pdf", [
    "Unit 1: Binary Trees, Graph Traversal\nUnit 2: Sorting; Hashing\nQuantum Computing",
])
print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))
