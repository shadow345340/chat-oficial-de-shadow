import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'shadow_key_2025'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Máximo 16MB

# Asegurar que la carpeta de fotos existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    is_image = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    others = User.query.filter(User.username != session['user']).all()
    return render_template('chat.html', me=session['user'], users=others)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        user = User.query.filter_by(username=u, password=p).first()
        if user:
            session['user'] = user.username
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        if not User.query.filter_by(username=u).first():
            db.session.add(User(username=u, password=p))
            db.session.add(Message(sender="Sistema", receiver=u, content="Bienvenido al Chat Oficial."))
            db.session.commit()
            session['user'] = u
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/h/<other>')
def history(other):
    me = session.get('user')
    msgs = Message.query.filter(((Message.sender==me)&(Message.receiver==other))|((Message.sender==other)&(Message.receiver==me))).all()
    return jsonify([{'s': m.sender, 'c': m.content, 'img': m.is_image} for m in msgs])

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return "No file", 400
    file = request.files['file']
    target = request.form.get('target')
    if file.filename == '': return "No filename", 400
    
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    
    # Guardar referencia en la DB
    new_m = Message(sender=session['user'], receiver=target, content=filename, is_image=True)
    db.session.add(new_m)
    db.session.commit()
    
    socketio.emit('recv_msg', {'from': session['user'], 'to': target, 'msg': filename, 'img': True}, broadcast=True)
    return "OK", 200

@socketio.on('send_msg')
def handle_msg(data):
    me = session.get('user')
    if me:
        db.session.add(Message(sender=me, receiver=data['to'], content=data['msg'], is_image=False))
        db.session.commit()
        emit('recv_msg', {'from': me, 'to': data['to'], 'msg': data['msg'], 'img': False}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)
