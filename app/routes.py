from flask import Blueprint, render_template, request, redirect, url_for, session, send_from_directory, flash
from app import db
from app.models import User, Task
from werkzeug.utils import secure_filename
import os
from flask import current_app
from flask import send_file

auth_bp = Blueprint('auth', __name__)
tasks_bp = Blueprint('tasks', __name__)

# Функция получения текущего пользователя
def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None

# Страница задач
@tasks_bp.route('/')
def index():
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему.', 'warning')
        return redirect(url_for('auth.login'))
    search = request.args.get('search', '')
    if search:
        tasks = Task.query.filter(Task.title.ilike(f'%{search}%'), Task.user_id == user.id).all()
    else:
        tasks = Task.query.filter_by(user_id=user.id).all()
    return render_template('tasks.html', tasks=tasks, search=search)

# Создание новой задачи
@tasks_bp.route('/task/new', methods=['GET', 'POST'])
def new_task():
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему.', 'warning')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        file = request.files.get('file')
        file_path = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            file_path = f'app/uploads/{filename}'  # Путь для базы данных
        task = Task(title=title, description=description, file_path=file_path, user_id=user.id)
        db.session.add(task)
        db.session.commit()
        flash('Новая задача успешно создана.', 'success')
        return redirect(url_for('tasks.index'))
    return render_template('task_form.html', task=None)

# Редактирование задачи
@tasks_bp.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
def edit_task(task_id):
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему.', 'warning')
        return redirect(url_for('auth.login'))
    task = Task.query.get(task_id)
    if task.user_id != user.id:
        flash('Нет прав на редактирование этой задачи.', 'danger')
        return redirect(url_for('tasks.index'))
    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form['description']
        task.status = 'status' in request.form
        file = request.files.get('file')
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            task.file_path = f'app/uploads/{filename}'
        db.session.commit()
        flash('Задача успешно обновлена.', 'success')
        return redirect(url_for('tasks.index'))
    return render_template('task_form.html', task=task)

# Удаление задачи
@tasks_bp.route('/task/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему.', 'warning')
        return redirect(url_for('auth.login'))
    task = Task.query.get(task_id)
    if task.user_id != user.id:
        flash('Нет прав на удаление этой задачи.', 'danger')
        return redirect(url_for('tasks.index'))
    db.session.delete(task)
    db.session.commit()
    flash('Задача успешно удалена.', 'warning')
    return redirect(url_for('tasks.index'))

# Загрузка файла
@tasks_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename)

# Регистрация нового пользователя
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует.', 'danger')
            return redirect(url_for('auth.register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация прошла успешно! Теперь войдите в систему.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

# Вход в систему
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('Успешный вход!', 'success')
            return redirect(url_for('tasks.index'))
        flash('Неверное имя пользователя или пароль.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('login.html')

# Выход из системы
@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))

# Скачать файл
@tasks_bp.route('/download/<filename>')
def download_file(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    full_path = os.path.join(upload_folder, filename)
    if not os.path.exists(full_path):
        flash('Файл не найден на сервере.', 'danger')
        return redirect(url_for('tasks.index'))
    return send_file(full_path, as_attachment=True)
