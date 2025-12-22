import eventlet
eventlet.monkey_patch()
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Sphere_2025_Secure'

# Configuración de Base de Datos compatible con Render
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'sphere.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

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
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user: return redirect(url_for('logout'))
    contacts = User.query.filter(User.id != user.id).all()
    return render_template('chat.html', user=user, contacts=contacts)

@app.route('/settings')
def settings():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('settings.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Usuario o contraseña no válidos.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Este usuario ya existe.')
        else:
            new_user = User(username=username, password=request.form['password'])
            db.session.add(new_user)
            db.session.commit()
            
            # Bienvenida (Texto plano para evitar errores de cifrado inicial)
            welcome = Message(sender_id=0, receiver_id=new_user.id, msg="U2FsdGVkX196v3M5Y9z6p7G1O9Z9Z9Z9") 
            db.session.add(welcome)
            db.session.commit()
            
            socketio.emit('new_user_event', {'id': new_user.id, 'username': new_user.username}, broadcast=True)
            session['user_id'] = new_user.id
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/history/<int:other_id>')
def history(other_id):
    my_id = session.get('user_id')
    if not my_id: return jsonify([])
    msgs = Message.query.filter(
        ((Message.sender_id == my_id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == my_id))
    ).order_by(Message.timestamp.asc()).all()
    return jsonify([{'msg': m.msg, 'sender_id': m.sender_id} for m in msgs])

@socketio.on('message')
def handle_message(data):
    my_id = session.get('user_id')
    if my_id:
        new_msg = Message(sender_id=my_id, receiver_id=data['target_id'], msg=data['msg'])
        db.session.add(new_msg)
        db.session.commit()
        emit('new_msg', {'msg': data['msg'], 'sender_id': my_id, 'target_id': data['target_id']}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)
