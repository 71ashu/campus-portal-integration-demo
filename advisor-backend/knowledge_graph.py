"""Prerequisite knowledge graph using NetworkX for course dependency analysis."""
import networkx as nx
from models import Course


def build_prerequisite_graph():
    """Build a directed acyclic graph from course prerequisites.
    Edges go from prerequisite -> dependent course.
    """
    G = nx.DiGraph()
    for course in Course.query.all():
        G.add_node(course.id, name=course.name)
        for prereq_id in (course.prerequisites or []):
            G.add_edge(prereq_id, course.id)
    return G


def get_reachable_courses(completed_ids):
    """Return set of course ids whose immediate prerequisites are all satisfied."""
    G = build_prerequisite_graph()
    completed = set(completed_ids)
    reachable = set()
    for node in G.nodes():
        if node in completed:
            continue
        required = set(G.predecessors(node))
        if required.issubset(completed):
            reachable.add(node)
    return reachable


def get_path_to_course(completed_ids, target_id):
    """Return the ordered list of courses a student still needs to unlock a target.
    Uses topological sort over the subgraph of missing ancestors.
    Returns empty list if the target is already reachable or completed.
    """
    G = build_prerequisite_graph()
    if target_id not in G:
        return []

    completed = set(completed_ids)
    if target_id in completed:
        return []

    all_ancestors = nx.ancestors(G, target_id)
    missing = [cid for cid in all_ancestors if cid not in completed]

    if not missing:
        return []

    subgraph = G.subgraph(missing + [target_id])
    return list(nx.topological_sort(subgraph))


def get_graph_depth(course_id):
    """Return the longest path length from any root to this course.
    Serves as a complexity/advancement indicator.
    """
    G = build_prerequisite_graph()
    if course_id not in G:
        return 0

    roots = [n for n in G.nodes() if G.in_degree(n) == 0]
    max_depth = 0
    for root in roots:
        try:
            for path in nx.all_simple_paths(G, root, course_id):
                max_depth = max(max_depth, len(path) - 1)
        except nx.NetworkXNoPath:
            continue
    return max_depth


def get_graph_summary():
    """Return a JSON-serializable summary of the prerequisite graph."""
    G = build_prerequisite_graph()
    return {
        'nodes': [
            {'id': n, 'name': G.nodes[n].get('name', n)}
            for n in G.nodes()
        ],
        'edges': [
            {'from': u, 'to': v}
            for u, v in G.edges()
        ],
        'total_courses': G.number_of_nodes(),
        'total_dependencies': G.number_of_edges(),
    }
