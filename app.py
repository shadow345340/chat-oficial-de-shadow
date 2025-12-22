import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chat_key_2025'

# Base de datos simplificada para evitar errores en Render/GitHub
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'chat.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80))
    receiver = db.Column(db.String(80))
    content = db.Column(db.Text)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    # Obtenemos todos los usuarios excepto nosotros mismos
    others = User.query.filter(User.username != session['user']).all()
    return render_template('chat.html', me=session['user'], users=others)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        user = User.query.filter_by(username=u, password=p).first()
        if user:
            session['user'] = user.username
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        if not User.query.filter_by(username=u).first():
            new_user = User(username=u, password=p)
            db.session.add(new_user)
            # Mensaje de Bienvenida del Sistema
            welcome = Message(sender="Sistema", receiver=u, content="¡Bienvenido a tu Chat personal!")
            db.session.add(welcome)
            db.session.commit()
            session['user'] = u
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/get_messages/<other>')
def get_messages(other):
    me = session.get('user')
    if not me: return jsonify([])
    msgs = Message.query.filter(
        ((Message.sender == me) & (Message.receiver == other)) |
        ((Message.sender == other) & (Message.receiver == me))
    ).all()
    return jsonify([{'s': m.sender, 'c': m.content} for m in msgs])

@socketio.on('send_msg')
def handle_msg(data):
    me = session.get('user')
    if me:
        new_m = Message(sender=me, receiver=data['to'], content=data['msg'])
        db.session.add(new_m)
        db.session.commit()
        emit('recv_msg', {'from': me, 'to': data['to'], 'msg': data['msg']}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)
