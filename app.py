import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'Shadow_Secret_2025')

if os.environ.get('RENDER'):
    db_path = "/tmp/chat.db"
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'chat.db')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    contacts = db.Column(db.String(500), default="")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, nullable=False)
    receiver_id = db.Column(db.Integer, nullable=False)
    msg = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        # PROTECCIÓN: Si el usuario ya no existe en la DB, cerramos sesión
        if user is None:
            session.pop('user_id', None)
            return redirect(url_for('login'))
            
        contact_ids = [int(i) for i in user.contacts.split(',') if i]
        contacts = User.query.filter(User.id.in_(contact_ids)).all()
        return render_template('chat.html', user=user, contacts=contacts)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    db.create_all()
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            session['user_id'] = user.id
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    db.create_all()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not User.query.filter_by(username=username).first():
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            session['user_id'] = new_user.id # ENTRA DIRECTO
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/search', methods=['POST'])
def search():
    query = request.json.get('query')
    users = User.query.filter(User.username.like(f'%{query}%')).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users if u.id != session.get('user_id')])

@app.route('/add_contact', methods=['POST'])
def add_contact():
    target_id = str(request.json.get('id'))
    user = User.query.get(session['user_id'])
    current_contacts = user.contacts.split(',')
    if target_id not in current_contacts:
        current_contacts.append(target_id)
        user.contacts = ','.join([c for c in current_contacts if c])
        db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/history/<int:other_id>')
def history(other_id):
    my_id = session['user_id']
    msgs = Message.query.filter(
        ((Message.sender_id == my_id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == my_id))
    ).order_by(Message.timestamp.asc()).all()
    return jsonify([{'msg': m.msg, 'sender_id': m.sender_id, 'hora': m.timestamp.strftime('%H:%M')} for m in msgs])

@socketio.on('message')
def handle_message(data):
    sender_id = session.get('user_id')
    new_msg = Message(sender_id=sender_id, receiver_id=data['target_id'], msg=data['msg'])
    db.session.add(new_msg)
    db.session.commit()
    emit('new_msg', {'msg': data['msg'], 'sender_id': sender_id, 'hora': datetime.now().strftime('%H:%M')}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)
    socketio.run(app)

