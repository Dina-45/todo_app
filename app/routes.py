from flask import Blueprint, render_template, request, redirect, url_for, session, send_from_directory, flash, current_app, send_file
from flask_wtf.csrf import CSRFProtect, generate_csrf
from app import db
from app.models import User, Task
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from transformers import pipeline
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    logger.info("Модель классификации успешно загружена.")
except Exception as e:
    logger.error(f"Ошибка загрузки модели: {str(e)}")
    classifier = None


categories = ["Учёба", "Работа", "Личные цели", "Медицина и здоровье", "Бытовые дела"]


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

auth_bp = Blueprint('auth', __name__)
tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash('Файл слишком большой! Максимальный размер: 5 МБ.', 'danger')
    return redirect(request.url)


def get_current_user():
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


@tasks_bp.route('/')
def index():
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему.', 'warning')
        return redirect(url_for('auth.login'))
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    query = Task.query.filter_by(user_id=user.id)
    if search:
        query = query.filter(Task.title.ilike(f'%{search}%'))
    if category:
        query = query.filter_by(category=category)
    tasks = query.all()
    return render_template('tasks.html', tasks=tasks, search=search, category=category, categories=categories)


@tasks_bp.route('/task/new', methods=['GET', 'POST'])
def new_task():
    user = get_current_user()
    if not user:
        flash('Пожалуйста, войдите в систему.', 'warning')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form.get('category')
        file = request.files.get('file')
        file_path = None
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Недопустимый тип файла! Разрешены: png, jpg, jpeg, gif, pdf.', 'danger')
                return redirect(url_for('tasks.new_task'))
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            file_path = f'app/uploads/{filename}'
        if not category:
            if classifier:
                try:
                    text = f"{title}. {description}" if description else title
                    result = classifier(text, candidate_labels=categories)
                    logger.info(f"Классификация для '{text}': {result['labels'][0]} (вероятность: {result['scores'][0]}), все вероятности: {dict(zip(result['labels'], result['scores']))}")
                    if result['labels'][0] == "Бытовые дела" and result['scores'][0] < 0.5:
                        category = result['labels'][1]
                    else:
                        category = result['labels'][0]
                except Exception as e:
                    logger.error(f"Ошибка классификации: {str(e)}")
                    category = "Не определено"
                    flash(f'Ошибка классификации: {str(e)}', 'warning')
            else:
                category = "Не определено"
                flash('Модель классификации недоступна.', 'warning')
        task = Task(title=title, description=description, file_path=file_path, user_id=user.id, category=category)
        db.session.add(task)
        db.session.commit()
        flash('Новая задача успешно создана.', 'success')
        return redirect(url_for('tasks.index'))
    return render_template('task_form.html', task=None, csrf_token=generate_csrf())

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
        category = request.form.get('category')
        file = request.files.get('file')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Недопустимый тип файла! Разрешены: png, jpg, jpeg, gif, pdf.', 'danger')
                return redirect(url_for('tasks.edit_task', task_id=task_id))
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            task.file_path = f'app/uploads/{filename}'
        if not category:
            if classifier:
                try:
                    text = f"{task.title}. {task.description}" if task.description else task.title
                    result = classifier(text, candidate_labels=categories)
                    logger.info(f"Классификация для '{text}': {result['labels'][0]} (вероятность: {result['scores'][0]}), все вероятности: {dict(zip(result['labels'], result['scores']))}")
                    if result['labels'][0] == "Бытовые дела" and result['scores'][0] < 0.5:
                        category = result['labels'][1]
                    else:
                        category = result['labels'][0]
                except Exception as e:
                    logger.error(f"Ошибка классификации: {str(e)}")
                    category = "Не определено"
                    flash(f'Ошибка классификации: {str(e)}', 'warning')
            else:
                category = "Не определено"
                flash('Модель классификации недоступна.', 'warning')
        task.category = category
        db.session.commit()
        flash('Задача успешно обновлена.', 'success')
        return redirect(url_for('tasks.index'))
    return render_template('task_form.html', task=task, csrf_token=generate_csrf())


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


@tasks_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename)


@tasks_bp.route('/download/<filename>')
def download_file(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    full_path = os.path.join(upload_folder, filename)
    if not os.path.exists(full_path):
        flash('Файл не найден на сервере.', 'danger')
        return redirect(url_for('tasks.index'))
    return send_file(full_path, as_attachment=True)


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
    return render_template('register.html', csrf_token=generate_csrf())

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
    return render_template('login.html', csrf_token=generate_csrf())


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))
