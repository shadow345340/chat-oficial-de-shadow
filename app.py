from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'familia_super_secreta_2025'
basedir = os.path.abspath(os.path.dirname(__file__))
# Busca esto y reemplázalo:
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/chat.db'
db = SQLAlchemy(app)
# Usamos gevent para máxima velocidad
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    contacts = db.Column(db.Text, default="")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, nullable=False)
    receiver_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

# --- RUTAS ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    contact_list = []
    if user.contacts:
        ids = [int(i) for i in user.contacts.split(',') if i]
        contact_list = User.query.filter(User.id.in_(ids)).all()
    return render_template('chat.html', user=user, contacts=contact_list)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('Ese nombre ya existe')
            return redirect(url_for('register'))
        new_user = User(username=request.form['username'], password=request.form['password'])
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/search', methods=['POST'])
def search():
    query = request.json.get('query', '').strip()
    if not query: return jsonify([])
    users = User.query.filter(User.username.like(f"%{query}%")).all()
    return jsonify([{"id": u.id, "username": u.username} for u in users if u.id != session.get('user_id')])

@app.route('/add_contact', methods=['POST'])
def add_contact():
    contact_id = str(request.json.get('id'))
    user = db.session.get(User, session['user_id'])
    current_contacts = user.contacts.split(',') if user.contacts else []
    if contact_id not in current_contacts:
        current_contacts.append(contact_id)
        user.contacts = ",".join(current_contacts)
        db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/history/<int:contact_id>')
def get_history(contact_id):
    my_id = session['user_id']
    messages = Message.query.filter(
        ((Message.sender_id == my_id) & (Message.receiver_id == contact_id)) |
        ((Message.sender_id == contact_id) & (Message.receiver_id == my_id))
    ).order_by(Message.timestamp).all()
    return jsonify([{
        'msg': m.content, 'sender_id': m.sender_id, 'hora': m.timestamp.strftime('%H:%M')
    } for m in messages])

# --- SOCKETS MEJORADOS ---
@socketio.on('connect')
def handle_connect():
    # Al conectarse, el usuario se une a SU PROPIA sala personal
    if 'user_id' in session:
        join_room(f"user_{session['user_id']}")
        print(f"Usuario {session['user_id']} conectado y listo para recibir.")

@socketio.on('message')
def handle_message(data):
    sender_id = int(session['user_id'])
    receiver_id = int(data['target_id'])
    msg_content = data['msg']
    
    # 1. Guardar en BD
    nuevo_mensaje = Message(sender_id=sender_id, receiver_id=receiver_id, content=msg_content)
    db.session.add(nuevo_mensaje)
    db.session.commit()
    
    # 2. Preparar datos
    hora = datetime.now().strftime('%H:%M')
    payload = {'msg': msg_content, 'sender_id': sender_id, 'hora': hora}
    
    # 3. Enviar al RECEPTOR (a su sala personal)
    emit('new_msg', payload, room=f"user_{receiver_id}")
    
    # 4. Enviar al EMISOR (a mi propia sala, para verlo en mi pantalla)
    emit('new_msg', payload, room=f"user_{sender_id}")

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)


