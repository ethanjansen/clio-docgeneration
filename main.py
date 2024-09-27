# Main for docGeneration/main.py:
from flask import Flask, render_template, request
from waitress import serve

#### Flask & Functions ####
app = Flask(__name__)

# Root Index
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/authorize')
def authorize():
    return "Authorizing..."

@app.route('/generate')
def generate():
    return "Generating..."


#### Main ####
if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=80)