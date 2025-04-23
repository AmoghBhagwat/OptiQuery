from flask import Flask, request, render_template, url_for
import sqlglot
from sqlglot import expressions as exp
import uuid

from parse import build_ra_tree, visualize_ra_tree
from pred_pushdown import pushdown_selections
from cost_estimator import estimate_cost, visualize_costs
from join_optimization import join_optimize
import psycopg2

app = Flask(__name__)

table_stats = None
current_tree = None

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="tpch",
            user="dabba",
            password="postgres",
            host="localhost",
            port="5432"
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
            # Parse the SQL query and build the RA tree

            global table_stats
            global current_tree

            table_stats = fetch_table_statistics()

            current_tree = build_ra_tree(sql)
            estimate_cost(current_tree, table_stats)

            dot_src = visualize_ra_tree(current_tree).source
        except Exception as e:
            error = str(e)

    return render_template('index.html', sql=sql, dot_src=dot_src, error=error)

@app.route('/joinopt', methods=['POST'])
def joinopt():
    """
    Optimize the join order in the relational algebra tree.
    """
    sql = request.form.get('sql', '')
    dot_src = None
    error = None

    try:
        # Perform join optimization on the RA tree

        global table_stats
        global current_tree
    
        estimate_cost(current_tree, table_stats)
        current_tree = join_optimize(current_tree)
        estimate_cost(current_tree, table_stats)

        dot_src = visualize_ra_tree(current_tree).source
    except Exception as e:
        error = str(e)

    return render_template('index.html', sql=sql, dot_src=dot_src, error=error)


@app.route('/pushdown', methods=['POST'])
def pushdown():
    sql = request.form.get('sql', '')
    dot_src = None
    error = None

    try:
        # push down selections in the RA tree
        global table_stats
        global current_tree

        estimate_cost(current_tree, table_stats)
        current_tree = pushdown_selections(current_tree)
        estimate_cost(current_tree, table_stats)

        dot_src = visualize_ra_tree(current_tree).source
    except Exception as e:
        error = str(e)

    return render_template('index.html', sql=sql, dot_src=dot_src, error=error)

@app.route('/cost', methods=['POST'])
def cost():
    sql = request.form.get('sql', '')
    error = None
    ra_tree_svg = None
    ra_tree_cost = 0
    current_tree_svg = None
    current_tree_cost = 0
    comparison_message = None
    comparison_class = None
    
    try:
        global table_stats
        global current_tree
        
        ra_tree = build_ra_tree(sql)

        estimate_cost(ra_tree, table_stats)
        ra_tree_svg = visualize_ra_tree(ra_tree).source
        ra_tree_cost = ra_tree.cumulative_cost

        estimate_cost(current_tree, table_stats)
        current_tree_svg = visualize_ra_tree(current_tree).source
        current_tree_cost = current_tree.cumulative_cost

        if ra_tree_cost > (1.001 * current_tree_cost):
            comparison_message = "The optimized tree has a lower cumulative cost!"
            comparison_class = "text-success"
        elif (ra_tree_cost * 1.001) < current_tree_cost:
            comparison_message = "The optimized tree has a higher cumulative cost!"
            comparison_class = "text-danger"
        else:
            comparison_message = "Both trees have almost the same cumulative cost."
            comparison_class = "text-warning"

    except Exception as e:
        error = str(e)


    return render_template(
        'index.html',
        sql=sql,
        error=error,
        ra_tree_svg=ra_tree_svg,
        current_tree_svg=current_tree_svg,
        ra_tree_cost=ra_tree_cost,
        current_tree_cost=current_tree_cost,
        comparison_message=comparison_message,
        comparison_class=comparison_class
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
        "rankdir=LR;", 
        "node [shape=box, style=filled, color=lightblue, fontname=Consolas];",  
        "edge [fontname=Consolas, color=gray];" 
    ]

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

    dbname = conn.get_dsn_parameters()['dbname']
    
    try:
        cursor.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        columns = cursor.fetchall()

        tables = {}
        for table_name, column_name, data_type in columns:
            friendly_data_type = data_type_mapping.get(data_type, data_type.upper())
            if table_name not in tables:
                tables[table_name] = []
            tables[table_name].append(f"{column_name} ({friendly_data_type})")

        for table_name, columns in tables.items():
            dot_lines.append(
                f'{table_name} [label=<<B>{table_name.upper()}</B><BR ALIGN="LEFT" />' +
                "<BR ALIGN=\"LEFT\" />".join(columns) +
                '>, fillcolor=lightyellow];'
            )

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
    return {"dot": "\n".join(dot_lines), "dbname": dbname}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
