from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)

# سر أفضل: في الإنتاج استخدمي os.environ.get('SECRET_KEY')
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key-please-change-this-123456789'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kodak.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ======================================
#               Models
# ======================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    progress = db.relationship('Progress', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100))
    html_file = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lessons = db.relationship('Lesson', backref='course', lazy='dynamic')

    def __repr__(self):
        return f"<Course {self.title}>"


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(500))
    order = db.Column(db.Integer, default=0)

    progress = db.relationship('Progress', backref='lesson', lazy='dynamic')

    def __repr__(self):
        return f"<Lesson {self.title}>"


class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'lesson_id', name='unique_user_lesson'),
    )

    def __repr__(self):
        return f"<Progress user:{self.user_id} lesson:{self.lesson_id}>"


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Message from {self.name}>"


# ======================================
#      Login Required Decorator
# ======================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ======================================
#               Routes
# ======================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not name or not email or not password:
            flash('كل الحقول مطلوبة', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('الإيميل موجود بالفعل', 'error')
            return redirect(url_for('register'))

        user = User(name=name, email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('تم التسجيل بنجاح! يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('index'))

        flash('الإيميل أو كلمة المرور خاطئة', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('index'))


@app.route('/test-db')
def test_db():
    return jsonify({
        "status": "Database OK",
        "users_count": User.query.count(),
        "courses_count": Course.query.count(),
        "lessons_count": Lesson.query.count(),
        "progress_count": Progress.query.count(),
        "messages_count": Message.query.count()
    })


# مثال على صفحة محمية (يمكنك تعديلها أو حذفها لاحقًا)
@app.route('/profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)
@app.route('/courses')
def courses():
    all_courses = Course.query.all()
    return render_template('courses.html', courses=all_courses)


# ======================================
#      Create tables (only once)
# ======================================
with app.app_context():
    db.create_all()

# ────────────────────────────────────────────────
#           Seed Data (بيانات تجريبية)
# ────────────────────────────────────────────────
def seed_data():
    if Course.query.count() == 0:
        print("بدء إضافة البيانات التجريبية...")

        # كورس 1
        course1 = Course(
            title="أساسيات البرمجة بـ Python",
            description="تعلم Python من الصفر للمبتدئين، خطوة بخطوة.",
            category="برمجة",
            html_file=None
        )
        db.session.add(course1)
        db.session.flush()  # يحفظ الكورس مؤقتًا ويعطيه ID

        lessons1 = [
            Lesson(course_id=course1.id, title="مقدمة في Python والبيئة", video_url="https://www.youtube.com/embed/rfscVS0vtbw", order=1),
            Lesson(course_id=course1.id, title="المتغيرات وأنواع البيانات", video_url="https://www.youtube.com/embed/_uQrJ0TkZlc", order=2),
            Lesson(course_id=course1.id, title="الشروط والحلقات (If & Loops)", video_url="https://www.youtube.com/embed/6iF8Xb7Z3wQ", order=3),
        ]
        db.session.add_all(lessons1)

        # كورس 2
        course2 = Course(
            title="تطوير ويب بـ Flask",
            description="بناء تطبيقات ويب سريعة وآمنة باستخدام Flask.",
            category="ويب ديفلوبر",
            html_file=None
        )
        db.session.add(course2)
        db.session.flush()

        lessons2 = [
            Lesson(course_id=course2.id, title="إنشاء أول مشروع Flask", video_url="https://www.youtube.com/embed/Z1RJmh_OqeA", order=1),
            Lesson(course_id=course2.id, title="Routing و Templates في Flask", video_url="https://www.youtube.com/embed/MwZwr5Tvyxo", order=2),
        ]
        db.session.add_all(lessons2)

        db.session.commit()
        print("تم إضافة 2 كورس و 5 دروس بنجاح!")
    else:
        print("البيانات التجريبية موجودة بالفعل، مش هتتضاف تاني.")

# شغليها مرة واحدة
with app.app_context():
    seed_data() 
if __name__ == '__main__':
    app.run(debug=True)