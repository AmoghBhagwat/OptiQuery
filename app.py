from flask import Flask, request, render_template, url_for
import sqlglot
from sqlglot import expressions as exp
import uuid

from parse import build_ra_tree, visualize_ra_tree
from pred_pushdown import pushdown_selections
from cost_estimator import estimate_cost, visualize_costs
import psycopg2

app = Flask(__name__)

ra_tree = None
optimized_tree = None

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
            ra_tree = build_ra_tree(sql)
            dot = visualize_ra_tree(ra_tree)
            # Provide raw DOT source for client-side rendering
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
        global optimized_tree
        optimized_tree = pushdown_selections(ra_tree)
        dot = visualize_ra_tree(optimized_tree)
        dot_src = dot.source
    except Exception as e:
        error = str(e)

    return render_template('index.html', sql=sql, dot_src=dot_src, error=error)

@app.route('/cost', methods=['POST'])
def compute_cost():
    sql = request.form.get('sql', '')
    error = None
    original_cost_svg = None
    optimized_cost_svg = None
    original_cumulative_cost = 0
    optimized_cumulative_cost = 0

    try:
        # Fetch table statistics
        # print("Fetching table statistics...")
        table_stats = fetch_table_statistics()

        # Compute costs for the original RA tree
        global ra_tree
        ra_tree_with_cost = ra_tree
        estimate_cost(ra_tree_with_cost, table_stats)
        original_cost_svg = visualize_costs(ra_tree_with_cost).source

        # Calculate cumulative cost for the original tree
        if hasattr(ra_tree_with_cost, 'cumulative_cost'):
            original_cumulative_cost = ra_tree_with_cost.cumulative_cost

        # Compute costs for the optimized RA tree
        global optimized_tree
        optimized_tree_with_cost = optimized_tree
        estimate_cost(optimized_tree_with_cost, table_stats)
        optimized_cost_svg = visualize_costs(optimized_tree_with_cost).source

        # Calculate cumulative cost for the optimized tree
        if hasattr(optimized_tree_with_cost, 'cumulative_cost'):
            optimized_cumulative_cost = optimized_tree_with_cost.cumulative_cost

    except Exception as e:
        error = str(e)

    return render_template(
        'index.html',
        sql=sql,
        error=error,
        original_cost_svg=original_cost_svg,
        optimized_cost_svg=optimized_cost_svg,
        original_cumulative_cost=original_cumulative_cost,
        optimized_cumulative_cost=optimized_cumulative_cost
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
