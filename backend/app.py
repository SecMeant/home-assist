import os
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Hello from Flask!"})

@app.route('/increment', methods=['POST'])
def increment():
    data = request.get_json()
    if not data or 'number' not in data:
        return jsonify({"error": "Please provide a 'number' in the JSON body"}), 400
    
    try:
        number = float(data['number'])
        return jsonify({"result": number + 1})
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid number provided"}), 400

if __name__ == '__main__':
    ssl_cert = os.environ.get('SSL_CERT_PATH')
    ssl_key = os.environ.get('SSL_KEY_PATH')

    if not ssl_cert:
        print('SSL_CERT_PATH is not set')
        exit(1)
    if not ssl_key:
        print('SSL_KEY_PATH is not set')
        exit(1)
    
    app.run(debug=False, host='10.0.0.1', port=9560, ssl_context=(ssl_cert, ssl_key))
