import sqlglot
from sqlglot import expressions as exp
from graphviz import Digraph
import uuid

COLOR_MAP = {
    'Relation': '#AED6F1',    # light blue
    'Selection': '#F9E79F',   # light yellow
    'Projection': '#ABEBC6',  # light green
    'Join': '#F5B7B1',        # light red
    'Subquery': '#D7BDE2',    # light purple
}

# Define basic RA node classes
class RANode:
    def to_dot(self, dot=None, parent_id=None):
        if dot is None:
            dot = Digraph()
            dot.attr(rankdir='BT')  # Bottom-to-top layout

        node_id = str(uuid.uuid4())
        node_type = self.__class__.__name__
        fillcolor = COLOR_MAP.get(node_type, '#ffffff')

        # Base node styling with type-based color
        dot.node(
            node_id,
            self._dot_label(),
            shape='box',
            style='rounded,filled',
            fillcolor=fillcolor,
            fontname='Helvetica'
        )

        if parent_id is not None:
            dot.edge(node_id, parent_id)

        # Recursively process children
        if hasattr(self, 'child'):
            self.child.to_dot(dot, node_id)
        if hasattr(self, 'left'):
            self.left.to_dot(dot, node_id)
        if hasattr(self, 'right'):
            self.right.to_dot(dot, node_id)

        return dot

    def __repr__(self):
        return self.__str__()


class Relation(RANode):
    def __init__(self, table_name, alias=None):
        self.table_name = table_name
        self.alias = alias

    def _dot_label(self):
        if self.alias:
            return f"Table: {self.table_name} AS {self.alias}"
        return f"Table: {self.table_name}"

    def __str__(self):
        if self.alias:
            return f'Relation("{self.table_name} AS {self.alias}")'
        return f'Relation("{self.table_name}")'


class Selection(RANode):
    def __init__(self, condition, child):
        self.condition = condition  # A string representing the condition
        self.child = child

    def _dot_label(self):
        cond = self.condition if len(self.condition) <= 50 else self.condition[:50] + '...'
        return f"σ\n{cond}"

    def __str__(self):
        return f'Selection("{self.condition}", {self.child})'


class Projection(RANode):
    def __init__(self, columns, child):
        self.columns = columns  # A list of projection columns as strings
        self.child = child

    def _dot_label(self):
        cols = '\n'.join([f'• {col}' for col in self.columns[:3]])
        if len(self.columns) > 30:
            cols += '\n...'
        return f"π\n{cols}"

    def __str__(self):
        return f"Projection({self.columns}, {self.child})"


class Join(RANode):
    def __init__(self, left, right, condition):
        self.left = left
        self.right = right
        self.condition = condition  # A string representing the join condition

    def _dot_label(self):
        cond = self.condition if len(self.condition) <= 50 else self.condition[:50] + '...'
        return f"Join({cond})"

    def __str__(self):
        return f'Join({self.left}, {self.right}, "{self.condition}")'


class Subquery(RANode):
    def __init__(self, alias, child):
        self.alias = alias
        self.child = child

    def _dot_label(self):
        return f"Subquery: {self.alias or ''}"

    def __str__(self):
        return f'Subquery("{self.alias}", {self.child})'

# Helper function to build a Relation or Subquery node from a table, alias, or subquery node
def build_table(node):
    # Direct table reference, preserve alias if present
    if isinstance(node, exp.Table):
        table_name = node.this.name
        alias_name = node.alias if node.alias else None
        return Relation(table_name, alias_name)

    # Aliased table or subquery
    if isinstance(node, exp.Alias):
        child = node.this
        alias_name = node.alias
        # Underlying table alias
        if isinstance(child, exp.Table):
            return Relation(child.name, alias_name)
        # Subquery alias
        if isinstance(child, exp.Subquery):
            sub_sql = child.this.sql()
            sub_ra = build_ra_tree(sub_sql)
            return Subquery(alias_name, sub_ra)

    # Inline subquery without explicit Alias (rare)
    if isinstance(node, exp.Subquery):
        alias_expr = node.args.get("alias")
        alias_name = alias_expr.name if alias_expr else None
        sub_sql = node.this.sql()
        sub_ra = build_ra_tree(sub_sql)
        return Subquery(alias_name, sub_ra)

    raise ValueError(f"Unhandled node type in FROM clause: {node}")


# Main function to construct the RA tree from a SQL query (handling subqueries)
def build_ra_tree(query):
    ast = sqlglot.parse_one(query)
    from_expr = ast.args.get("from")
    if not from_expr:
        raise ValueError("No FROM clause found in query")

    # Build base relation or subquery
    ra_node = build_table(from_expr.this)

    # Process explicit JOINs
    for join in ast.args.get("joins", []):
        right = build_table(join.this)
        condition = join.args.get("on").sql() if join.args.get("on") else "TRUE"
        ra_node = Join(ra_node, right, condition)

    # Apply WHERE and then SELECT
    if where := ast.args.get("where"):
        ra_node = Selection(where.sql(), ra_node)
    if select := ast.args.get("expressions"):
        ra_node = Projection([expr.sql() for expr in select], ra_node)

    return ra_node


def visualize_ra_tree(ra_root, format='png', view=False):
    """Generate and display a visual representation of the RA tree"""
    try:
        from graphviz import Digraph
    except ImportError:
        raise RuntimeError("Please install graphviz: pip install graphviz")

    dot = ra_root.to_dot()
    dot.format = format

    if view:
        dot.view(cleanup=True)
    return dot

# Example usage with a subquery in FROM
# query = """
# SELECT sq.a, t1.b
# FROM (
#     SELECT a, id FROM table_sub WHERE a > 10
# ) AS sq
# JOIN table1 t1 ON sq.id = t1.id
# WHERE t1.b < 5
# """
# ra_tree = build_ra_tree(query)
# visualize_ra_tree(ra_tree).render('ra_tree_subquery')
# print(ra_tree)

# query = """
# SELECT O.ORDERKEY, L.QUANTITY, S.SUPPKEY, C.CUSTKEY
# FROM ORDERS O
# JOIN CUSTOMER C ON O.CUSTKEY = C.CUSTKEY
# JOIN LINEITEM L ON O.ORDERKEY = L.ORDERKEY
# JOIN SUPPLIER S ON S.SUPPKEY = L.SUPPKEY
# JOIN (SELECT N.NATIONKEY, N.NAME FROM NATION N) TMP1 ON TMP1.NATIONKEY = C.NATIONKEY
# JOIN (SELECT N.NATIONKEY, N.NAME FROM NATION N) TMP2 ON TMP2.NATIONKEY = S.NATIONKEY
# """
# ra_tree = build_ra_tree(query)
# visualize_ra_tree(ra_tree).render('ra_tree')
# print(ra_tree)

query = """
SELECT PS.PARTKEY, PS.SUPPLYKEY
FROM PARTSUPP AS PS
JOIN SUPPLIER AS S ON PS.SUPPLYKEY = S.SUPPLYKEY
JOIN LINEITEM AS L ON PS.SUPPLYKEY = L.SUPPLYKEY
JOIN (SELECT P.NAME, P.BRAND FROM PART P) AS TMP1 ON TMP1.PARTKEY = PS.PARTKEY
JOIN (SELECT P.NAME, P.BRAND FROM PART P JOIN AMOGH A WHERE P.Q > 100) AS TMP2 ON TMP2.PARTKEY = L.PARTKEY
WHERE PS.AVAILQTY > 10 AND S.ACCTBAL > 1000
"""
ra_tree = build_ra_tree(query)
visualize_ra_tree(ra_tree).render('ra_tree_part')
print(ra_tree)

# query = "SELECT a, b FROM table1 JOIN table2 ON table1.id = table2.id WHERE b > 5"
# ra_tree = build_ra_tree(query)
# visualize_ra_tree(ra_tree).render('ra_tree1')
# print(ra_tree)

# query = """SELECT table_a.id, table_b.id
# FROM table_a
# JOIN table_b ON table_b.join_key_ab = table_a.join_key_ab
# JOIN table_c ON table_c.join_key_bc = table_b.join_key_ab
# WHERE table_b.id > 1"""
# ra_tree = build_ra_tree(query)
# visualize_ra_tree(ra_tree).render('ra_tree2')
# print(ra_tree)

# query = """
# SELECT S.S_NAME, N.N_NAME, L.L_EXTENDEDPRICE, O.O_ORDERDATE
# FROM SUPPLIER S
# JOIN NATION N ON S.S_NATIONKEY = N.N_NATIONKEY
# JOIN LINEITEM L ON S.S_SUPPKEY = L.L_SUPPKEY
# JOIN ORDERS O ON L.L_ORDERKEY = O.O_ORDERKEY
# WHERE L.L_DISCOUNT > 0.05;
# """
# ra_tree = build_ra_tree(query)
# visualize_ra_tree(ra_tree).render('ra_tree3')
# print(ra_tree)

