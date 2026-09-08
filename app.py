"""
نظام إدارة الأنشطة (Activity Management System)
Flask Web Application with SQLite, ReportLab PDF, RBAC, and Arabic RTL Bootstrap 5.
"""

import os
import sqlite3
import io
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ReportLab Imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except ImportError:
    HAS_ARABIC_SUPPORT = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'activity-system-secret-key-2026-islamic')

DATABASE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Dynamically creates the SQLite database and relational schema on first run"""
    conn = get_db()
    cursor = conn.cursor()

    # 1. users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user'))
        )
    ''')

    # 2. activities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_name TEXT NOT NULL,
            branch_location TEXT NOT NULL,
            activity_date TEXT NOT NULL,
            supervisor_name TEXT NOT NULL,
            manager_approval TEXT NOT NULL,
            gender TEXT NOT NULL,
            age_groups TEXT NOT NULL,
            location_map_url TEXT,
            phone TEXT,
            estimated_cost REAL DEFAULT 0,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # 3. staff table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            staff_name TEXT NOT NULL,
            role_description TEXT,
            FOREIGN KEY (activity_id) REFERENCES activities (id) ON DELETE CASCADE
        )
    ''')

    # 4. participants table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            participant_name TEXT NOT NULL,
            academic_level TEXT,
            FOREIGN KEY (activity_id) REFERENCES activities (id) ON DELETE CASCADE
        )
    ''')

    # 5. expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            item_cost REAL DEFAULT 0,
            FOREIGN KEY (activity_id) REFERENCES activities (id) ON DELETE CASCADE
        )
    ''')

    # 6. system_contents (Ideas & Instructions) table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            phone TEXT,
            cost REAL DEFAULT 0,
            image_path TEXT,
            location_map_url TEXT,
            gender TEXT,
            age_groups TEXT,
            type TEXT NOT NULL CHECK(type IN ('idea', 'instruction'))
        )
    ''')

    # 7. educational_materials table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS educational_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            pdf_filename TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 8. evaluations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            full_attendance TEXT NOT NULL,
            absent_names TEXT,
            uninvited_names TEXT,
            financial_plan_adhered TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (activity_id) REFERENCES activities (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    # Seed Default Users if empty
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            ('admin', generate_password_hash('admin123'), 'admin')
        )
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            ('user', generate_password_hash('user123'), 'user')
        )

        # Seed sample ideas & instructions
        cursor.execute('''
            INSERT INTO system_contents (title, description, phone, cost, image_path, location_map_url, gender, age_groups, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'مخيم الفتيان القرآني الربيعي',
            'برنامج تربوي قيمي يشتمل على مسابقات قرآنية، ورش مهارية، وفقرات رياضية في بيئة محفزة تعزز الأخوة والروح الإيمانية.',
            '0501234567',
            1500.0,
            '/static/img/camp.jpg',
            'https://maps.google.com/?q=24.7136,46.6753',
            'ذكور',
            '7-17, 18-29',
            'idea'
        ))

        cursor.execute('''
            INSERT INTO system_contents (title, description, phone, cost, image_path, location_map_url, gender, age_groups, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'ملتقى الزهرات الثقافي الإبداعي',
            'نشاط يهدف لتنمية الإبداع والمهارات اليدوية والأدبية لدى الفتيات، مع فقرات حوارية ومسابقات شيقة.',
            '0507654321',
            1200.0,
            '/static/img/creativity.jpg',
            'https://maps.google.com/?q=24.774265,46.738586',
            'إناث',
            '7-17',
            'idea'
        ))

        cursor.execute('''
            INSERT INTO system_contents (title, description, phone, cost, image_path, location_map_url, gender, age_groups, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'دليل السلامة وإجراءات الطوارئ للرحلات',
            'تعليمات صارمة للمشرفين بضرورة توفير حقيبة الإسعافات الأولية والتأكد من أرقام أولياء الأمور قبل انطلاق أي نشاط خارجي.',
            '0500000000',
            0.0,
            '',
            '',
            'الجميع',
            '7-17, 18-29, 30+',
            'instruction'
        ))

        # Seed sample educational material
        cursor.execute('''
            INSERT INTO educational_materials (title, description, pdf_filename)
            VALUES (?, ?, ?)
        ''', (
            'حقيبة المشرف التربوي الناجح',
            'دليل إرشادي شامل يغطي أساليب قيادة الأنشطة الشبابية، إدارة الأزمات، والتحفيز الإيجابي للمشاركين.',
            'sample_guide.pdf'
        ))

        # Seed sample activity
        cursor.execute('''
            INSERT INTO activities (user_id, activity_name, branch_location, activity_date, supervisor_name, manager_approval, gender, age_groups, location_map_url, phone, estimated_cost, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            1,
            'دورة الإلقاء والخطابة المؤثرة',
            'فرع الهدى - القاعة المركزية',
            datetime.now().strftime('%Y-%m-%d'),
            'أ. عبد الرحمن الشوابكة',
            'معتمد من الإدارة العامة',
            'ذكور',
            '18-29',
            'https://maps.google.com/?q=24.7136,46.6753',
            '0555123456',
            850.0,
            'دورة عملية تهدف إلى إكساب الشباب مهارات الوقوف أمام الجمهور وبناء المحتوى الخطابي بأسلوب واثق ومقنع.'
        ))
        act_id = cursor.lastrowid

        cursor.execute('INSERT INTO staff (activity_id, staff_name, role_description) VALUES (?, ?, ?)',
                       (act_id, 'أحمد المنصور', 'مدرب الدورة ومقدم الورشة'))
        cursor.execute('INSERT INTO staff (activity_id, staff_name, role_description) VALUES (?, ?, ?)',
                       (act_id, 'عمر الفاروق', 'مسؤول التجهيزات التقنية والتسجيل'))

        cursor.execute('INSERT INTO participants (activity_id, participant_name, academic_level) VALUES (?, ?, ?)',
                       (act_id, 'يوسف الخالد', 'جامعي'))
        cursor.execute('INSERT INTO participants (activity_id, participant_name, academic_level) VALUES (?, ?, ?)',
                       (act_id, 'بلال التميمي', 'ثانوي'))
        cursor.execute('INSERT INTO participants (activity_id, participant_name, academic_level) VALUES (?, ?, ?)',
                       (act_id, 'حمزة الراشد', 'جامعي'))

        cursor.execute('INSERT INTO expenses (activity_id, item_name, item_cost) VALUES (?, ?, ?)',
                       (act_id, 'ضيافة واستراحة القهوة', 350.0))
        cursor.execute('INSERT INTO expenses (activity_id, item_name, item_cost) VALUES (?, ?, ?)',
                       (act_id, 'شهادات تدريبية وحقائب للمشاركين', 500.0))

    conn.commit()
    conn.close()

# Run database setup
init_db()

# --- Security & Global Login Guard ---
@app.before_request
def global_login_guard():
    """Enforce strict authentication across all routes automatically."""
    allowed_endpoints = ['login', 'static']
    if request.endpoint is not None and request.endpoint not in allowed_endpoints:
        if 'user_id' not in session:
            flash('يرجى تسجيل الدخول أولاً للوصول إلى النظام.', 'warning')
            return redirect(url_for('login'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('عذراً، هذه الصفحة مخصصة لمدير النظام فقط.', 'danger')
            return redirect(url_for('my_activities'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor for templates
@app.context_processor
def inject_user():
    return {
        'current_user': {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role')
        }
    }

# Helper: fallback default values
def clean_val(val, default="لا يوجد"):
    if val is None or str(val).strip() == "":
        return default
    return str(val).strip()

def clean_num(val):
    try:
        if val is None or str(val).strip() == "":
            return 0.0
        return float(val)
    except ValueError:
        return 0.0

# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard' if session.get('role') == 'admin' else 'my_activities'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('يرجى ملء حقلي اسم المستخدم وكلمة المرور.', 'danger')
            return render_template('login.html')

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'مرحباً بك {user["username"]}، تم تسجيل الدخول بنجاح.', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('dashboard'))
            return redirect(url_for('my_activities'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    if session.get('role') == 'admin':
        return redirect(url_for('dashboard'))
    return redirect(url_for('my_activities'))

# --- Admin Dashboard ---
@app.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db()
    # Metrics
    total_activities = conn.execute('SELECT COUNT(*) FROM activities').fetchone()[0]
    total_expenses = conn.execute('SELECT COALESCE(SUM(item_cost), 0) FROM expenses').fetchone()[0]
    total_participants = conn.execute('SELECT COUNT(*) FROM participants').fetchone()[0]
    total_ideas = conn.execute("SELECT COUNT(*) FROM system_contents WHERE type = 'idea'").fetchone()[0]
    total_materials = conn.execute('SELECT COUNT(*) FROM educational_materials').fetchone()[0]

    # Branches stats
    branch_stats = conn.execute('''
        SELECT branch_location, COUNT(*) as count 
        FROM activities 
        GROUP BY branch_location 
        ORDER BY count DESC LIMIT 5
    ''').fetchall()

    # Staff counts breakdown
    staff_stats = conn.execute('''
        SELECT a.activity_name, COUNT(s.id) as staff_count
        FROM activities a
        LEFT JOIN staff s ON a.id = s.activity_id
        GROUP BY a.id
        ORDER BY staff_count DESC LIMIT 5
    ''').fetchall()

    # Gender breakdown
    gender_stats = conn.execute('''
        SELECT gender, COUNT(*) as count
        FROM activities
        GROUP BY gender
    ''').fetchall()

    # Recent activities
    recent_activities = conn.execute('''
        SELECT a.*, u.username 
        FROM activities a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.id DESC LIMIT 6
    ''').fetchall()

    conn.close()

    return render_template('dashboard.html',
        total_activities=total_activities,
        total_expenses=total_expenses,
        total_participants=total_participants,
        total_ideas=total_ideas,
        total_materials=total_materials,
        branch_stats=branch_stats,
        staff_stats=staff_stats,
        gender_stats=gender_stats,
        recent_activities=recent_activities
    )

# --- Activity Log (Admin View) ---
@app.route('/activities')
@admin_required
def activities():
    conn = get_db()
    acts = conn.execute('''
        SELECT a.*, u.username,
               (SELECT COUNT(*) FROM staff WHERE activity_id = a.id) as staff_count,
               (SELECT COUNT(*) FROM participants WHERE activity_id = a.id) as participant_count,
               (SELECT COALESCE(SUM(item_cost), 0) FROM expenses WHERE activity_id = a.id) as real_expenses,
               (SELECT COUNT(*) FROM evaluations WHERE activity_id = a.id) as evaluation_count
        FROM activities a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.id DESC
    ''').fetchall()
    conn.close()
    return render_template('activities.html', activities=acts)

# --- My Activities (Regular User View) ---
@app.route('/my_activities')
def my_activities():
    conn = get_db()
    acts = conn.execute('''
        SELECT a.*,
               (SELECT COUNT(*) FROM staff WHERE activity_id = a.id) as staff_count,
               (SELECT COUNT(*) FROM participants WHERE activity_id = a.id) as participant_count,
               (SELECT COALESCE(SUM(item_cost), 0) FROM expenses WHERE activity_id = a.id) as real_expenses,
               (SELECT COUNT(*) FROM evaluations WHERE activity_id = a.id) as evaluation_count
        FROM activities a
        WHERE a.user_id = ?
        ORDER BY a.id DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('my_activities.html', activities=acts)

# --- Create Activity (Form & Validation) ---
@app.route('/activities/create', methods=['GET', 'POST'])
def create_activity():
    if request.method == 'POST':
        # Retrieve and sanitize inputs with default fallbacks
        activity_name = clean_val(request.form.get('activity_name'))
        branch_location = clean_val(request.form.get('branch_location'))
        activity_date = clean_val(request.form.get('activity_date'), datetime.now().strftime('%Y-%m-%d'))
        supervisor_name = clean_val(request.form.get('supervisor_name'))
        manager_approval = clean_val(request.form.get('manager_approval'), 'قيد الانتظار')
        gender = clean_val(request.form.get('gender'), 'ذكور')
        
        # Age groups (Multi-select)
        age_groups_list = request.form.getlist('age_groups')
        age_groups = ", ".join(age_groups_list) if age_groups_list else "لا يوجد"

        location_map_url = clean_val(request.form.get('location_map_url'))
        phone = clean_val(request.form.get('phone'))
        estimated_cost = clean_num(request.form.get('estimated_cost'))
        description = clean_val(request.form.get('description'))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activities (
                user_id, activity_name, branch_location, activity_date, supervisor_name,
                manager_approval, gender, age_groups, location_map_url, phone,
                estimated_cost, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'], activity_name, branch_location, activity_date, supervisor_name,
            manager_approval, gender, age_groups, location_map_url, phone,
            estimated_cost, description
        ))
        activity_id = cursor.lastrowid

        # Staff items
        staff_names = request.form.getlist('staff_name[]')
        staff_roles = request.form.getlist('role_description[]')
        for s_name, s_role in zip(staff_names, staff_roles):
            s_name_clean = clean_val(s_name, "")
            if s_name_clean:
                cursor.execute(
                    'INSERT INTO staff (activity_id, staff_name, role_description) VALUES (?, ?, ?)',
                    (activity_id, s_name_clean, clean_val(s_role))
                )

        # Participants items
        part_names = request.form.getlist('participant_name[]')
        part_levels = request.form.getlist('academic_level[]')
        for p_name, p_lvl in zip(part_names, part_levels):
            p_name_clean = clean_val(p_name, "")
            if p_name_clean:
                cursor.execute(
                    'INSERT INTO participants (activity_id, participant_name, academic_level) VALUES (?, ?, ?)',
                    (activity_id, p_name_clean, clean_val(p_lvl))
                )

        # Expenses items
        exp_names = request.form.getlist('item_name[]')
        exp_costs = request.form.getlist('item_cost[]')
        for e_name, e_cost in zip(exp_names, exp_costs):
            e_name_clean = clean_val(e_name, "")
            if e_name_clean:
                cursor.execute(
                    'INSERT INTO expenses (activity_id, item_name, item_cost) VALUES (?, ?, ?)',
                    (activity_id, e_name_clean, clean_num(e_cost))
                )

        conn.commit()
        conn.close()

        flash('تم تسجيل النشاط بنجاح!', 'success')
        return redirect(url_for('my_activities' if session.get('role') != 'admin' else 'activities'))

    # GET Request: check if prefilled via "Adopt Idea"
    prefill = {
        'activity_name': request.args.get('activity_name', ''),
        'estimated_cost': request.args.get('estimated_cost', ''),
        'phone': request.args.get('phone', ''),
        'location_map_url': request.args.get('location_map_url', ''),
        'gender': request.args.get('gender', 'ذكور'),
        'age_groups': request.args.get('age_groups', ''),
        'description': request.args.get('description', '')
    }
    return render_template('create_activity.html', prefill=prefill)

# --- Ideas & Instructions Page ---
@app.route('/ideas')
def ideas():
    conn = get_db()
    ideas_list = conn.execute("SELECT * FROM system_contents WHERE type = 'idea' ORDER BY id DESC").fetchall()
    instructions_list = conn.execute("SELECT * FROM system_contents WHERE type = 'instruction' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('ideas.html', ideas=ideas_list, instructions=instructions_list)

@app.route('/ideas/create', methods=['POST'])
@admin_required
def create_idea():
    title = clean_val(request.form.get('title'))
    description = clean_val(request.form.get('description'))
    content_type = clean_val(request.form.get('type'), 'idea')
    phone = clean_val(request.form.get('phone'))
    cost = clean_num(request.form.get('cost'))
    location_map_url = clean_val(request.form.get('location_map_url'))
    gender = clean_val(request.form.get('gender'), 'الجميع')
    age_groups = clean_val(request.form.get('age_groups'), 'الجميع')
    image_path = clean_val(request.form.get('image_path'))

    conn = get_db()
    conn.execute('''
        INSERT INTO system_contents (title, description, phone, cost, image_path, location_map_url, gender, age_groups, type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, phone, cost, image_path, location_map_url, gender, age_groups, content_type))
    conn.commit()
    conn.close()
    flash('تم إضافة المحتوى بنجاح.', 'success')
    return redirect(url_for('ideas'))

# --- Educational Materials Hub ---
@app.route('/materials')
def materials():
    conn = get_db()
    items = conn.execute('SELECT * FROM educational_materials ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('materials.html', materials=items)

@app.route('/materials/create', methods=['POST'])
@admin_required
def create_material():
    title = clean_val(request.form.get('title'))
    description = clean_val(request.form.get('description'))
    
    file = request.files.get('pdf_file')
    filename = 'document.pdf'
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = get_db()
    conn.execute('''
        INSERT INTO educational_materials (title, description, pdf_filename)
        VALUES (?, ?, ?)
    ''', (title, description, filename))
    conn.commit()
    conn.close()

    flash('تمت إضافة المادة التعليمية بنجاح.', 'success')
    return redirect(url_for('materials'))

# --- Activity Evaluation Module ---
@app.route('/activities/<int:activity_id>/evaluate', methods=['GET', 'POST'])
def evaluate(activity_id):
    conn = get_db()
    act = conn.execute('SELECT * FROM activities WHERE id = ?', (activity_id,)).fetchone()
    if not act:
        conn.close()
        abort(404)

    # Check permission
    if session.get('role') != 'admin' and act['user_id'] != session.get('user_id'):
        conn.close()
        flash('غير مسموح لك بتقييم هذا النشاط.', 'danger')
        return redirect(url_for('my_activities'))

    if request.method == 'POST':
        full_attendance = clean_val(request.form.get('full_attendance'), 'نعم')
        absent_names = clean_val(request.form.get('absent_names'))
        uninvited_names = clean_val(request.form.get('uninvited_names'))
        financial_plan_adhered = clean_val(request.form.get('financial_plan_adhered'), 'نعم')
        notes = clean_val(request.form.get('notes'))

        conn.execute('''
            INSERT INTO evaluations (
                activity_id, user_id, full_attendance, absent_names, uninvited_names,
                financial_plan_adhered, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (activity_id, session['user_id'], full_attendance, absent_names, uninvited_names, financial_plan_adhered, notes))
        conn.commit()
        conn.close()

        flash('تم حفظ تقييم النشاط بنجاح للمساهمة في التقارير الإحصائية.', 'success')
        return redirect(url_for('my_activities' if session.get('role') != 'admin' else 'activities'))

    existing_eval = conn.execute('SELECT * FROM evaluations WHERE activity_id = ? ORDER BY id DESC', (activity_id,)).fetchone()
    conn.close()
    return render_template('evaluate.html', activity=act, evaluation=existing_eval)

# --- ReportLab PDF Generation Engine ---
def reshape_ar(text):
    """Reshape Arabic text and apply bidirectional algorithm for ReportLab compatibility"""
    if not text:
        return "لا يوجد"
    str_val = str(text)
    if HAS_ARABIC_SUPPORT:
        try:
            reshaped = arabic_reshaper.reshape(str_val)
            return get_display(reshaped)
        except Exception:
            return str_val
    return str_val

class NumberedCanvas(canvas.Canvas):
    """Custom canvas for drawing header, footer, and page numbers cleanly without clutter"""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        # Header Islamic geometric bar
        self.setFillColor(colors.HexColor('#064e3b'))
        self.rect(0, 830, 595.27, 12, fill=True, stroke=False)
        self.setFillColor(colors.HexColor('#d97706'))
        self.rect(0, 826, 595.27, 4, fill=True, stroke=False)

        # Footer
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(40, 35, 555, 35)
        
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#64748b'))
        self.drawString(40, 22, "نظام إدارة الأنشطة الرقمي - تقرير رسمي معتمد آلياً")
        page_str = f"صفحة {self._pageNumber} من {page_count}"
        self.drawRightString(555, 22, page_str)
        self.restoreState()

@app.route('/activities/<int:activity_id>/pdf')
def activity_pdf(activity_id):
    conn = get_db()
    act = conn.execute('SELECT a.*, u.username FROM activities a JOIN users u ON a.user_id = u.id WHERE a.id = ?', (activity_id,)).fetchone()
    if not act:
        conn.close()
        abort(404)

    # Permissions check
    if session.get('role') != 'admin' and act['user_id'] != session.get('user_id'):
        conn.close()
        flash('غير مصرح لك بتحميل هذا التقرير.', 'danger')
        return redirect(url_for('my_activities'))

    staff_list = conn.execute('SELECT * FROM staff WHERE activity_id = ?', (activity_id,)).fetchall()
    participants_list = conn.execute('SELECT * FROM participants WHERE activity_id = ?', (activity_id,)).fetchall()
    expenses_list = conn.execute('SELECT * FROM expenses WHERE activity_id = ?', (activity_id,)).fetchall()
    eval_record = conn.execute('SELECT * FROM evaluations WHERE activity_id = ? ORDER BY id DESC', (activity_id,)).fetchone()
    conn.close()

    # Data integrity check with strict fallbacks
    activity_name = clean_val(act['activity_name'])
    branch_location = clean_val(act['branch_location'])
    activity_date = clean_val(act['activity_date'])
    supervisor = clean_val(act['supervisor_name'])
    approval = clean_val(act['manager_approval'])
    gender = clean_val(act['gender'])
    age_groups = clean_val(act['age_groups'])
    phone = clean_val(act['phone'])
    map_url = clean_val(act['location_map_url'])
    cost = clean_num(act['estimated_cost'])
    description = clean_val(act['description'])

    total_actual_expenses = sum([clean_num(e['item_cost']) for e in expenses_list])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=48,
        bottomMargin=48
    )

    styles = getSampleStyleSheet()

    # Custom Clean Card Styles
    title_style = ParagraphStyle(
        'IslamicTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#064e3b'),
        alignment=1, # Center
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'IslamicSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#d97706'),
        alignment=1,
        spaceAfter=14
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#064e3b'),
        alignment=2, # Right aligned for RTL
        spaceBefore=8,
        spaceAfter=6
    )

    card_text = ParagraphStyle(
        'CardText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
        alignment=2
    )

    card_label = ParagraphStyle(
        'CardLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#0f766e'),
        alignment=2
    )

    story = []

    # 1. Header Card (Islamic architectural aesthetic banner)
    story.append(Paragraph(reshape_ar(f"تقرير نشاط: {activity_name}"), title_style))
    story.append(Paragraph(reshape_ar(f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d')} | الرقم التعريفي للنشاط: #{act['id']}"), subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#d97706'), spaceAfter=12))

    # 2. Key Metadata Cards (2-column layout in table format)
    meta_data = [
        [
            Paragraph(reshape_ar(f"<b>تاريخ التنفيذ:</b> {activity_date}"), card_text),
            Paragraph(reshape_ar(f"<b>الفرع / الناحية:</b> {branch_location}"), card_text),
        ],
        [
            Paragraph(reshape_ar(f"<b>المشرف المسؤول:</b> {supervisor}"), card_text),
            Paragraph(reshape_ar(f"<b>موافقة العريف / الإدارة:</b> {approval}"), card_text),
        ],
        [
            Paragraph(reshape_ar(f"<b>الفئة المستهدفة:</b> {gender}"), card_text),
            Paragraph(reshape_ar(f"<b>الفئات العمرية:</b> {age_groups}"), card_text),
        ],
        [
            Paragraph(reshape_ar(f"<b>رقم التواصل:</b> {phone}"), card_text),
            Paragraph(reshape_ar(f"<b>التكلفة المقدرة:</b> {cost:,.2f} د.أ"), card_text),
        ]
    ]

    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Location & Description Card
    desc_rows = [
        [Paragraph(reshape_ar("<b>وصف النشاط وأهدافه:</b>"), card_label)],
        [Paragraph(reshape_ar(description), card_text)],
        [Paragraph(reshape_ar(f"<b>الموقع الجغرافي (Google Maps):</b> {map_url}"), card_text)]
    ]
    desc_table = Table(desc_rows, colWidths=[520])
    desc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bbf7d0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(desc_table)
    story.append(Spacer(1, 12))

    # 4. Staff Section
    story.append(Paragraph(reshape_ar(f"فريق الكادر المشرف ({len(staff_list)})"), section_heading))
    if staff_list:
        staff_data = [[
            Paragraph(reshape_ar("الدور / الوصف"), card_label),
            Paragraph(reshape_ar("اسم الكادر"), card_label),
            Paragraph(reshape_ar("#"), card_label)
        ]]
        for idx, s in enumerate(staff_list, 1):
            staff_data.append([
                Paragraph(reshape_ar(clean_val(s['role_description'])), card_text),
                Paragraph(reshape_ar(clean_val(s['staff_name'])), card_text),
                Paragraph(str(idx), card_text)
            ])
        s_table = Table(staff_data, colWidths=[260, 220, 40])
        s_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#064e3b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#064e3b')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ]))
        story.append(s_table)
    else:
        story.append(Paragraph(reshape_ar("لا يوجد كادر مسجل."), card_text))
    story.append(Spacer(1, 10))

    # 5. Participants Section
    story.append(Paragraph(reshape_ar(f"المشاركون المسجلون ({len(participants_list)})"), section_heading))
    if participants_list:
        part_data = [[
            Paragraph(reshape_ar("المرحلة الدراسية"), card_label),
            Paragraph(reshape_ar("اسم المشارك"), card_label),
            Paragraph(reshape_ar("#"), card_label)
        ]]
        for idx, p in enumerate(participants_list, 1):
            part_data.append([
                Paragraph(reshape_ar(clean_val(p['academic_level'])), card_text),
                Paragraph(reshape_ar(clean_val(p['participant_name'])), card_text),
                Paragraph(str(idx), card_text)
            ])
        p_table = Table(part_data, colWidths=[260, 220, 40])
        p_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#047857')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#047857')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ]))
        story.append(p_table)
    else:
        story.append(Paragraph(reshape_ar("لا يوجد مشاركون مسجلون."), card_text))
    story.append(Spacer(1, 10))

    # 6. Expenses Section
    story.append(Paragraph(reshape_ar(f"المصاريف الفعلية (المجموع: {total_actual_expenses:,.2f} د.أ)"), section_heading))
    if expenses_list:
        exp_data = [[
            Paragraph(reshape_ar("التكلفة (د.أ)"), card_label),
            Paragraph(reshape_ar("البند"), card_label),
            Paragraph(reshape_ar("#"), card_label)
        ]]
        for idx, e in enumerate(expenses_list, 1):
            exp_data.append([
                Paragraph(f"{clean_num(e['item_cost']):,.2f}", card_text),
                Paragraph(reshape_ar(clean_val(e['item_name'])), card_text),
                Paragraph(str(idx), card_text)
            ])
        exp_data.append([
            Paragraph(f"<b>{total_actual_expenses:,.2f}</b>", card_text),
            Paragraph(reshape_ar("<b>المجموع الكلي</b>"), card_text),
            Paragraph("-", card_text)
        ])
        e_table = Table(exp_data, colWidths=[160, 320, 40])
        e_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d97706')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fef3c7')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#d97706')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ]))
        story.append(e_table)
    else:
        story.append(Paragraph(reshape_ar("لا توجد مصاريف مسجلة."), card_text))
    story.append(Spacer(1, 10))

    # 7. Evaluation Details (if available)
    if eval_record:
        story.append(Paragraph(reshape_ar("نتائج التقييم الإداري والميداني"), section_heading))
        eval_data = [
            [
                Paragraph(reshape_ar(f"<b>هل حضر الجميع؟</b> {eval_record['full_attendance']}"), card_text),
                Paragraph(reshape_ar(f"<b>الالتزام بالخطة المالية:</b> {eval_record['financial_plan_adhered']}"), card_text),
            ],
            [
                Paragraph(reshape_ar(f"<b>المتغيبون:</b> {clean_val(eval_record['absent_names'])}"), card_text),
                Paragraph(reshape_ar(f"<b>حضور غير مدعوين:</b> {clean_val(eval_record['uninvited_names'])}"), card_text),
            ],
            [
                Paragraph(reshape_ar(f"<b>ملاحظات إضافية:</b> {clean_val(eval_record['notes'])}"), card_text),
                Paragraph(reshape_ar(f"<b>تاريخ التقييم:</b> {eval_record['created_at'][:10]}"), card_text),
            ]
        ]
        eval_table = Table(eval_data, colWidths=[260, 260])
        eval_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(eval_table)

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)

    filename = f"activity_report_{activity_id}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    # Binds to 0.0.0.0 and port 5000 or PORT env var for local/cloud deployment
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
