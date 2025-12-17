import os
import psycopg2
from flask import Flask, request, render_template_string, redirect, url_for
import pandas as pd

# Default QuestDB connection details
QUESTDB_HOST = os.environ.get("QUESTDB_HOST", "localhost")
QUESTDB_PORT = os.environ.get("QUESTDB_PORT", 8812)
QUESTDB_USER = os.environ.get("QUESTDB_USER", "admin")
QUESTDB_PASSWORD = os.environ.get("QUESTDB_PASSWORD", "quest")
QUESTDB_DB = os.environ.get("QUESTDB_DB", "auction_trading")

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QuestDB Query UI</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    .dataframe {
        width: 100%;
        border-collapse: collapse;
    }
    .dataframe th, .dataframe td {
        border: 1px solid #ddd;
        padding: 8px;
    }
    .dataframe th {
        background-color: #f2f2f2;
        text-align: left;
    }
  </style>
</head>
<body>
  <div class="container mt-4">
    <h1 class="mb-4">QuestDB Query UI</h1>

    <form method="post" action="{{ url_for('index') }}">
      <div class="mb-3">
        <label for="query" class="form-label">SQL Query</label>
        <textarea class="form-control" id="query" name="query" rows="5" required>{{ query }}</textarea>
      </div>
      <button type="submit" class="btn btn-primary">Execute</button>
    </form>

    {% if error %}
      <div class="alert alert-danger mt-4" role="alert">
        <strong>Error:</strong> {{ error }}
      </div>
    {% endif %}

    {% if results %}
      <h2 class="mt-5">Results</h2>
      <div class="table-responsive">
        {{ results|safe }}
      </div>
       <form method="post" action="{{ url_for('copy_results') }}">
         <input type="hidden" name="results_df" value="{{ results_df }}">
         <button type="submit" class="btn btn-secondary mt-3">Copy as CSV</button>
      </form>
    {% endif %}

  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=QUESTDB_HOST,
            port=QUESTDB_PORT,
            user=QUESTDB_USER,
            password=QUESTDB_PASSWORD,
            database=QUESTDB_DB
        )
        return conn
    except psycopg2.OperationalError as e:
        raise Exception(f"Could not connect to QuestDB: {e}")


@app.route('/', methods=['GET', 'POST'])
def index():
    query = ""
    results_html = None
    results_df_str = None
    error = None

    if request.method == 'POST':
        query = request.form['query']
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(query)
                if cur.description:
                    column_names = [desc[0] for desc in cur.description]
                    results = cur.fetchall()
                    df = pd.DataFrame(results, columns=column_names)
                    results_html = df.to_html(classes='table table-striped dataframe', index=False)
                    results_df_str = df.to_csv(index=False)
                else:
                    results_html = "<p>Query executed successfully, no results to display.</p>"

            conn.close()
        except Exception as e:
            error = str(e)

    return render_template_string(HTML_TEMPLATE, query=query, results=results_html, results_df=results_df_str, error=error)

@app.route('/copy', methods=['POST'])
def copy_results():
    results_df_str = request.form.get('results_df')
    # This is a bit of a trick to "copy to clipboard" from server-side.
    # In a real app, you'd use JavaScript on the client side.
    # For this example, we'll just display it in a textarea to be copied manually.
    return f"""
    <textarea rows="20" cols="120">{results_df_str}</textarea>
    <br>
    <a href="{url_for('index')}">Back</a>
    """

if __name__ == '__main__':
    app.run(debug=True, port=5001)
