from parse import RANode, Relation, Selection, Projection, Join, Subquery
from graphviz import Digraph

def estimate_cost(node: RANode, table_stats: dict):
    """
    Recursively computes the cost of each node in the RA tree using pre-fetched table statistics.
    Annotates the cost at each node for visualization.
    """

    print(f"Estimating cost for node: {node}")

    if isinstance(node, Relation):
        # Get the size of the relation from the pre-fetched statistics
        table_name = node.table_name.lower()  # Use the string method `.lower()`
        print(f"Table name: {table_name}")
        row_count = table_stats.get(table_name, 0)
        node.cost = row_count
        print(f"Relation {table_name} has {row_count} rows.")
        return row_count

    elif isinstance(node, Selection):
        # Estimate the size of the selection (assume a selectivity factor)
        child_cost = estimate_cost(node.child, table_stats)
        selectivity_factor = 0.1  # Assume 10% of rows are selected
        filtered_count = (child_cost * selectivity_factor)
        node.cost = filtered_count
        # print(f"Selection on {node.condition} reduces rows from {child_cost} to {filtered_count}.")
        return filtered_count

    elif isinstance(node, Projection):
        # Projection does not change the row count
        child_cost = estimate_cost(node.child, table_stats)
        node.cost = child_cost
        # print(f"Projection on {node.columns} keeps {child_cost} rows.")
        return child_cost

    elif isinstance(node, Join):
        # Estimate the size of the join (assume a join selectivity factor)
        left_cost = estimate_cost(node.left, table_stats)
        right_cost = estimate_cost(node.right, table_stats)
        join_selectivity_factor = 0.01  # Assume 1% of the Cartesian product
        join_count = int(left_cost * right_cost * join_selectivity_factor)
        node.cost = join_count
        # print(f"Join on {node.condition} results in {join_count} rows from {left_cost} and {right_cost}.")
        return join_count

    elif isinstance(node, Subquery):
        # Estimate the cost of the subquery
        child_cost = estimate_cost(node.child, table_stats)
        node.cost = child_cost
        # print(f"Subquery {node.alias} has {child_cost} rows.")
        return child_cost

    else:
        node.cost = 0
        return 0

def visualize_costs(ra_tree: RANode):
    """
    Generates an SVG visualization of the RA tree with costs annotated at each node.
    Returns the SVG content as a string.
    """
    dot = Digraph()

    def add_node(dot, node):
        if isinstance(node, Relation):
            label = f"Relation: {node.table_name}\nCost: {node.cost}"
        elif isinstance(node, Selection):
            label = f"Selection: {node.condition}\nCost: {node.cost}"
        elif isinstance(node, Projection):
            label = f"Projection: {', '.join(node.columns)}\nCost: {node.cost}"
        elif isinstance(node, Join):
            label = f"Join: {node.condition}\nCost: {node.cost}"
        elif isinstance(node, Subquery):
            label = f"Subquery: {node.alias}\nCost: {node.cost}"
        else:
            label = f"Unknown Node\nCost: {node.cost}"

        node_id = str(id(node))
        dot.node(node_id, label)

        if hasattr(node, 'child') and node.child:
            child_id = str(id(node.child))
            add_node(dot, node.child)
            dot.edge(node_id, child_id)

        if hasattr(node, 'left') and node.left:
            left_id = str(id(node.left))
            add_node(dot, node.left)
            dot.edge(node_id, left_id)

        if hasattr(node, 'right') and node.right:
            right_id = str(id(node.right))
            add_node(dot, node.right)
            dot.edge(node_id, right_id)

    add_node(dot, ra_tree)
    dot = ra_tree.to_dot()  # Use the `to_dot` method from the RANode class
    return dot.pipe(format='svg').decode('utf-8')