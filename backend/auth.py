from flask import Flask,request

app = Flask(__name__)

@app.route('/singup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    gmail=data.get('gmail')
    password = data.get('password')


    return {'message': f'User {username} signed up successfully!'}, 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    gmail = data.get('gmail')
    password = data.get('password')

    return {'message': f'User {username} logged in successfully!'}, 200
