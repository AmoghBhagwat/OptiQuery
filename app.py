from flask import Flask, request, render_template, url_for
import sqlglot
from sqlglot import expressions as exp
import uuid

from parse import build_ra_tree, visualize_ra_tree
from pred_pushdown import pushdown_selections
from cost_estimator import estimate_cost, visualize_costs
from join_optimization import join_optimize
import psycopg2

import copy
import sys

app = Flask(__name__)

ra_tree = None
ra_tree_with_cost = None
after_join = None
after_join_push = None
table_stats = None

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="tpch",  # Replace with your database name
            user="dabba",  # Replace with your username
            password="postgres",  # Replace with your password
            host="localhost",  # Replace with your host if not localhost
            port="5432"  # Replace with your port if not the default
        )
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        raise

def fetch_table_statistics():
    """
    Fetch row counts for all tables in the database using pg_stats_all_tables.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    table_stats = {}

    try:
        # Query pg_stats_all_tables for table statistics

        cursor.execute("""
            SELECT relname AS table_name, n_live_tup AS row_count
            FROM pg_stat_all_tables
            WHERE schemaname = 'public';
        """)
        stats = cursor.fetchall()

        cnt = 0
        for stat in stats:
            table_name, row_count = stat
            table_stats[table_name] = row_count
            cnt += row_count

        if(cnt == 0):
            cursor.execute("""
                ANALYZE;
            """)
            cursor.execute("""
                SELECT relname AS table_name, n_live_tup AS row_count
                FROM pg_stat_all_tables
                WHERE schemaname = 'public';
            """)

            stats = cursor.fetchall()

            cnt = 0
            for stat in stats:
                table_name, row_count = stat
                table_stats[table_name] = row_count
                cnt += row_count

        if(cnt == 0):
            print(f"Error: No tables found in the database.")

        # print(f"Fetched table statistics: {table_stats}")

    except Exception as e:
        print(f"Error fetching table statistics: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

    return table_stats

@app.route('/', methods=['GET', 'POST'])
def index():
    sql = ''
    dot_src = None
    error = None

    if request.method == 'POST':
        sql = request.form.get('sql', '')
        try:
            global ra_tree
            global table_stats
            global after_join
            global after_join_push

            table_stats = fetch_table_statistics()

            ra_tree = build_ra_tree(sql)
            after_join = build_ra_tree(sql)
            after_join_push = build_ra_tree(sql)

            estimate_cost(ra_tree, table_stats)

            estimate_cost(after_join, table_stats)
            join_optimize(after_join)
            estimate_cost(after_join, table_stats) 
            
            estimate_cost(after_join_push, table_stats)
            join_optimize(after_join_push)
            after_join_push = pushdown_selections(after_join_push)
            estimate_cost(after_join_push, table_stats)

            dot = visualize_ra_tree(ra_tree)
            dot_src = dot.source
        except Exception as e:
            error = str(e)

    return render_template('index.html', sql=sql, dot_src=dot_src, error=error)

@app.route('/joinopt', methods=['POST'])
def join_optimization():
    """
    Optimize the join order in the relational algebra tree.
    """
    sql = request.form.get('sql', '')
    dot_src = None
    error = None

    try:
        # Perform join optimization on the RA tree
        global after_join
       
        dot = visualize_ra_tree(after_join)  # Visualize the optimized tree
        dot_src = dot.source
    except Exception as e:
        error = str(e)

    return render_template('index.html', sql=sql, dot_src=dot_src, error=error)


@app.route('/pushdown', methods=['POST'])
def pushdown():
    sql = request.form.get('sql', '')
    dot_src = None
    error = None

    try:
        # ra_tree = build_ra_tree(sql)
        global after_join_push

        dot = visualize_ra_tree(after_join_push)
        dot_src = dot.source
    except Exception as e:
        error = str(e)

    return render_template('index.html', sql=sql, dot_src=dot_src, error=error)

@app.route('/cost', methods=['POST'])
def compute_cost():
    sql = request.form.get('sql', '')
    error = None
    ra_tree_cost_svg = None
    after_join_cost_svg = None
    after_join_push_cost_svg = None
    ra_tree_cost = 0
    after_join_cost = 0
    after_join_push_cost = 0
    
    try:
        ra_tree_cost_svg = visualize_ra_tree(ra_tree).source
        after_join_cost_svg = visualize_ra_tree(after_join).source
        after_join_push_cost_svg = visualize_ra_tree(after_join_push).source

        ra_tree_cost = ra_tree.cumulative_cost
        after_join_cost = after_join.cumulative_cost
        after_join_push_cost = after_join_push.cumulative_cost

    except Exception as e:
        error = str(e)
        print(f"Error in cost computation: {e}", file=sys.stderr)

    return render_template(
        'index.html',
        sql=sql,
        error=error,
        ra_tree_cost_svg=ra_tree_cost_svg,
        after_join_cost_svg=after_join_cost_svg,
        after_join_push_cost_svg=after_join_push_cost_svg,
        ra_tree_cost=ra_tree_cost,
        after_join_cost=after_join_cost,
        after_join_push_cost=after_join_push_cost
    )

@app.route('/schema', methods=['GET'])
def get_schema_graph():
    """
    Fetch the schema of the current database and return it in DOT format for visualization.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    dot_lines = [
        "digraph Schema {",
        "rankdir=LR;",  # Left-to-right graph layout
        "node [shape=box, style=filled, color=lightblue, fontname=Consolas];",  # Default node styling with monospace font
        "edge [fontname=Consolas, color=gray];"  # Default edge styling with monospace font
    ]

    # Mapping PostgreSQL data types to user-friendly formats
    data_type_mapping = {
        "integer": "INT",
        "character varying": "VARCHAR",
        "character": "CHAR",
        "text": "TEXT",
        "boolean": "BOOL",
        "timestamp without time zone": "TIMESTAMP",
        "timestamp with time zone": "TIMESTAMPTZ",
        "numeric": "NUMERIC",
        "real": "REAL",
        "double precision": "DOUBLE"
    }

    try:
        # Fetch table names and their columns
        cursor.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        columns = cursor.fetchall()

        # Add tables as nodes
        tables = {}
        for table_name, column_name, data_type in columns:
            # Map data type to user-friendly format
            friendly_data_type = data_type_mapping.get(data_type, data_type.upper())
            if table_name not in tables:
                tables[table_name] = []
            tables[table_name].append(f"{column_name} ({friendly_data_type})")

        for table_name, columns in tables.items():
            # Convert table name to uppercase and make it bold
            dot_lines.append(
                f'{table_name} [label=<<B>{table_name.upper()}</B><BR ALIGN="LEFT" />' +
                "<BR ALIGN=\"LEFT\" />".join(columns) +
                '>, fillcolor=lightyellow];'
            )

        # Fetch foreign key relationships
        cursor.execute("""
            SELECT
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column
            FROM
                information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY';
        """)
        relationships = cursor.fetchall()

        # Add relationships as edges
        for source_table, source_column, target_table, target_column in relationships:
            dot_lines.append(
                f'{source_table} -> {target_table} [label="{source_column} -> {target_column}", color=blue];'
            )

    except Exception as e:
        return f"Error fetching schema: {e}", 500
    finally:
        cursor.close()
        conn.close()

    dot_lines.append("}")
    return {"dot": "\n".join(dot_lines)}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
