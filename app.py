import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'Velo_Key_2025')

if os.environ.get('RENDER'):
    db_path = "/tmp/velo.db"
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'velo.db')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.String(200), default="Usando Velo")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, nullable=False)
    receiver_id = db.Column(db.Integer, nullable=False)
    msg = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    msg_type = db.Column(db.String(20), default="text") # text, image, audio, video
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('login'))
        all_users = User.query.filter(User.id != user.id).all()
        return render_template('chat.html', user=user, contacts=all_users)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            session['user_id'] = user.id
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        if not User.query.filter_by(username=username).first():
            new_user = User(username=username, password=request.form['password'])
            db.session.add(new_user)
            db.session.commit()
            # Mensaje de Bienvenida (Cifrado)
            welcome = Message(sender_id=0, receiver_id=new_user.id, 
                             msg="U2FsdGVkX1+L6OqI8k1vS/M0yI5F8YpUvj7j9qY=") 
            db.session.add(welcome)
            db.session.commit()
            session['user_id'] = new_user.id
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/history/<int:other_id>')
def history(other_id):
    my_id = session['user_id']
    msgs = Message.query.filter(
        ((Message.sender_id == my_id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == my_id))
    ).order_by(Message.timestamp.asc()).all()
    # Marcar como leídos al abrir chat
    for m in msgs:
        if m.receiver_id == my_id: m.read = True
    db.session.commit()
    return jsonify([{'msg': m.msg, 'sender_id': m.sender_id, 'hora': m.timestamp.strftime('%H:%M'), 'read': m.read, 'type': m.msg_type} for m in msgs])

@socketio.on('message')
def handle_message(data):
    sender_id = session.get('user_id')
    new_msg = Message(sender_id=sender_id, receiver_id=data['target_id'], msg=data['msg'], msg_type=data.get('type', 'text'))
    db.session.add(new_msg)
    db.session.commit()
    emit('new_msg', {
        'msg': data['msg'], 'sender_id': sender_id, 'target_id': data['target_id'],
        'hora': datetime.now().strftime('%H:%M'), 'type': data.get('type', 'text')
    }, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)
