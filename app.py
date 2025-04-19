from flask import Flask, request, render_template_string
import sqlglot
from sqlglot import expressions as exp
import uuid

from parse import build_ra_tree, visualize_ra_tree

app = Flask(__name__)

# HTML template with Viz.js for interactive SVG rendering
TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OptiQuery</title>
  <!-- Bootstrap CSS -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://d3js.org/d3.v6.min.js"></script>
  <script src="https://unpkg.com/d3-graphviz/build/d3-graphviz.min.js"></script>
  <style>
    body { background-color: #f8f9fa; }
    .card { box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075); }
    #graph-container {
      width: 100%;
      height: 500px;
      overflow: auto;
      margin: 0 auto; /* Added for horizontal centering */
    }
    #graph svg {
      width: 100%;
      height: 100%;
      display: block; /* Ensures the SVG itself behaves as a block */
    }
  </style>
</head>
<body>
  <nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
    <div class="container-fluid">
      <a class="navbar-brand" href="#">OptiQuery</a>
    </div>
  </nav>
  <div class="container">
    <div class="row mb-4">
      <div class="col">
        <div class="card">
          <div class="card-body">
            <h5 class="card-title">Enter SQL Query</h5>
            <form method="post">
              <div class="mb-3">
                <textarea class="form-control" name="sql" rows="6" placeholder="SELECT * FROM table;">{{ sql }}</textarea>
              </div>
              <button type="submit" class="btn btn-primary">Generate Tree</button>
            </form>
            {% if error %}
              <div class="alert alert-danger mt-3">{{ error }}</div>
            {% endif %}
          </div>
        </div>
      </div>
    </div>
    {% if dot_src %}
    <div class="row">
      <div class="col">
        <div class="card">
          <div class="card-body" id="graph-container">
            <script>
              const dot = {{ dot_src | tojson }};
                d3.select('#graph-container')
                  .append('div')
                  .attr('id', 'graph')
                  .style('margin', '0 auto') // Dynamic centering
                  .graphviz({ useWorker: false })
                  .zoom(true)
                  .fit(true)
                  .renderDot(dot)
                  .on('end', function() {
                    // Additional post-rendering centering adjustments if needed
                  });

            </script>
          </div>
        </div>
      </div>
    </div>
    {% endif %}
  </div>
  <footer class="footer mt-4 py-3 bg-light">
    <div class="container text-center">
      <span class="text-muted">&copy; 2025 OptiQuery</span>
    </div>
  </footer>
  <!-- Bootstrap Bundle with Popper -->
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    sql = ''
    dot_src = None
    error = None

    if request.method == 'POST':
        sql = request.form.get('sql', '')
        try:
            ra_tree = build_ra_tree(sql)
            dot = visualize_ra_tree(ra_tree)
            # Provide raw DOT source for client-side rendering
            dot_src = dot.source
        except Exception as e:
            error = str(e)

    return render_template_string(TEMPLATE, sql=sql, dot_src=dot_src, error=error)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
