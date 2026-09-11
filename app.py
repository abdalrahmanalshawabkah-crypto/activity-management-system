import os
import sqlite3
import traceback
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'shafiee_secure_key_2026')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

# =====================================================================
# تهيئة وتحديث قاعدة البيانات بأمان تام
# =====================================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            activity_name TEXT NOT NULL,
            branch_location TEXT NOT NULL,
            activity_date TEXT NOT NULL,
            supervisor_name TEXT,
            gender TEXT DEFAULT 'ذكور',
            age_groups TEXT DEFAULT '7-17',
            location_map_url TEXT DEFAULT '',
            sharia_teacher_name TEXT DEFAULT '',
            sharia_lesson_duration TEXT DEFAULT '',
            sharia_lesson_topic TEXT DEFAULT '',
            description TEXT DEFAULT '',
            evaluation_rating INTEGER DEFAULT NULL,
            evaluation_pros TEXT DEFAULT '',
            evaluation_cons TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            gender TEXT DEFAULT 'الجميع'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT
        )
    ''')

    # المستخدمون الافتراضيون
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, display_name, role) VALUES ('admin', 'admin123', 'مسؤول الأنشطة والمركز', 'admin')")
        cursor.execute("INSERT INTO users (username, password, display_name, role) VALUES ('supervisor', '123456', 'مشرف النشاط الميداني', 'user')")

    # إضافة أنشطة ومواد افتراضية
    cursor.execute("SELECT COUNT(*) FROM ideas")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO ideas (title, description, gender) VALUES ('دورة أصول التجويد وحفظ الجزرية', 'دورة مكثفة للطلبة لإتقان مخارج الحروف والصفات', 'ذكور')")
        cursor.execute("INSERT INTO ideas (title, description, gender) VALUES ('رحلة الهمة والمعرفة', 'نشاط ميداني وتربوي ومسابقات قرآنية', 'الجميع')")

    cursor.execute("SELECT COUNT(*) FROM materials")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO materials (title, description) VALUES ('منهاج فقه الصلاة الميسر', 'حقيبة تعليمية ملخصة لشرح أحكام الطهارة والصلاة')")
        cursor.execute("INSERT INTO materials (title, description) VALUES ('كتيب الأربعين النووية', 'متن الأربعين النووية مع الشرح الميسر للناشئة')")

    conn.commit()
    conn.close()

init_db()

# حارس الأخطاء: إذا حصل أي خطأ يظهر سببه بوضوح بدلاً من Internal Server Error
@app.errorhandler(Exception)
def handle_exception(e):
    return f"""
    <div dir="rtl" style="font-family: sans-serif; padding: 25px; background: #fff5f5; color: #991b1b; border: 2px solid #f87171; border-radius: 12px; max-width: 800px; margin: 30px auto; line-height: 1.6;">
        <h2 style="margin-top:0;">تنبيه: حدث خطأ أثناء تشغيل الطلب</h2>
        <p><strong>السبب:</strong> {str(e)}</p>
        <details style="margin-top: 15px;">
            <summary style="cursor: pointer; font-weight: bold; color: #b91c1c;">تفاصيل الخطأ الفنية (Traceback)</summary>
            <pre style="direction: ltr; background: #1e293b; color: #f8fafc; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 12px; margin-top: 10px;">{traceback.format_exc()}</pre>
        </details>
        <div style="margin-top: 20px;">
            <a href="/" style="background: #1e293b; color: #fff; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 13px;">العودة للرئيسية</a>
        </div>
    </div>
    """, 500

# حارس تسجيل الدخول
@app.before_request
def require_login():
    public_endpoints = ['login', 'static']
    if request.endpoint and request.endpoint not in public_endpoints and 'user_id' not in session:
        return redirect(url_for('login'))

# =====================================================================
# قوالب HTML مدمجة ومباشرة (خفيفة وسريعة ولا تحتاج أي ملفات خارجية)
# =====================================================================
BASE_LAYOUT = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مركز الإمام الشافعي</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Cairo', sans-serif; }</style>
</head>
<body class="bg-[#fbf9f5] text-slate-800 min-h-screen flex flex-col">
    <header class="bg-[#163629] text-white border-b border-[#d4af37]/40 shadow-xs sticky top-0 z-40">
        <div class="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
            <a href="{{ url_for('index') }}" class="font-bold text-sm text-[#e5c158]">مركز الإمام الشافعي</a>
            <div class="flex items-center gap-2">
                <a href="{{ url_for('create_activity') }}" class="px-3 py-1 bg-[#1b4332] hover:bg-[#143224] text-white rounded-lg text-xs font-bold">+ نشاط جديد</a>
                <span class="text-xs bg-white/10 px-2 py-1 rounded text-amber-200 hidden sm:inline">{{ session.get('display_name') }}</span>
                <a href="{{ url_for('logout') }}" class="text-xs bg-red-800/80 hover:bg-red-700 px-2.5 py-1 rounded">خروج</a>
            </div>
        </div>
    </header>
    <main class="max-w-5xl w-full mx-auto p-4 flex-1">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for msg in messages %}
                    <div class="mb-4 p-3 bg-emerald-100 border border-emerald-300 text-emerald-800 rounded-xl text-xs font-bold">{{ msg }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {{ content | safe }}
    </main>
    <footer class="bg-white border-t border-slate-200 py-3 text-center text-xs text-slate-400">
        مركز الإمام الشافعي لتدريس القرءان الكريم والعلوم الشرعية
    </footer>
</body>
</html>
'''

# =====================================================================
# المسارات (Routes)
# =====================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['display_name'] = user['display_name']
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة')

    login_html = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>تسجيل الدخول - مركز الإمام الشافعي</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Cairo', sans-serif; }</style>
    </head>
    <body class="bg-[#163629] min-h-screen flex items-center justify-center p-4">
        <div class="bg-white w-full max-w-sm rounded-2xl p-6 border-t-4 border-[#d4af37] shadow-xl">
            <h1 class="text-xl font-bold text-[#163629] text-center mb-1">مركز الإمام الشافعي</h1>
            <p class="text-xs text-slate-500 text-center mb-5">منظومة متابعة الأنشطة والدروس الشرعية</p>
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    {% for msg in messages %}
                        <div class="mb-3 p-2 bg-red-100 text-red-700 text-xs rounded-lg">{{ msg }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="POST" class="space-y-3 text-xs">
                <div>
                    <label class="block font-bold text-slate-700 mb-1">اسم المستخدم</label>
                    <input type="text" name="username" required placeholder="admin أو supervisor" class="w-full p-2.5 border border-slate-300 rounded-xl outline-none focus:ring-2 focus:ring-[#163629]">
                </div>
                <div>
                    <label class="block font-bold text-slate-700 mb-1">كلمة المرور</label>
                    <input type="password" name="password" required placeholder="••••••" class="w-full p-2.5 border border-slate-300 rounded-xl outline-none focus:ring-2 focus:ring-[#163629]">
                </div>
                <button type="submit" class="w-full py-2.5 bg-[#163629] hover:bg-[#0f241c] text-[#f3e5ab] font-bold rounded-xl transition">تسجيل الدخول</button>
            </form>
            <div class="mt-4 pt-3 border-t text-center text-[11px] text-slate-400">
                admin / admin123 أو supervisor / 123456
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(login_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    conn = get_db()
    if session.get('role') == 'admin':
        activities = conn.execute("SELECT * FROM activities ORDER BY id DESC").fetchall()
    else:
        activities = conn.execute("SELECT * FROM activities WHERE user_id = ? ORDER BY id DESC", (session['user_id'],)).fetchall()
    ideas = conn.execute("SELECT * FROM ideas").fetchall()
    materials = conn.execute("SELECT * FROM materials").fetchall()
    conn.close()

    body = f'''
    <!-- كرت توجيهات المشايخ -->
    <div class="bg-white rounded-2xl p-4 border border-[#e5decb] shadow-xs mb-5">
        <div class="flex items-center justify-between border-b pb-2 mb-2">
            <span class="text-xs font-bold text-[#1b4332]">درر في طلب العلم • الإمام الشافعي رحمه الله</span>
            <span class="text-[11px] text-[#b8860b]">مركز الإمام الشافعي</span>
        </div>
        <p class="text-xs text-slate-700 leading-relaxed">
            "أَخي لَن تَنالَ العِلمَ إِلّا بِسِتَّةٍ • سَأُنبيكَ عَن تَفصيلِها بِبَيانِ: ذَكاءٌ وَحِرصٌ وَاِجتِهادٌ وَبُلغَةٌ • وَصُحبَةُ أُستاذٍ وَطولُ زَمانِ"
        </p>
    </div>

    <!-- أزرار العمليات الرئيسية الواضحة -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <a href="/activities/new" class="bg-[#1b4332] hover:bg-[#143224] text-white p-4 rounded-xl text-center shadow-xs">
            <div class="text-lg font-bold mb-1">+</div>
            <div class="text-xs font-bold">تسجيل نشاط جديد</div>
        </a>
        <a href="#activities-list" class="bg-white hover:border-[#1b4332] border border-slate-200 p-4 rounded-xl text-center shadow-xs">
            <div class="text-lg font-bold text-[#1b4332] mb-1">{len(activities)}</div>
            <div class="text-xs font-bold text-slate-700">الأنشطة المسجلة</div>
        </a>
        <a href="/ideas" class="bg-white hover:border-amber-500 border border-slate-200 p-4 rounded-xl text-center shadow-xs">
            <div class="text-lg font-bold text-amber-700 mb-1">{len(ideas)}</div>
            <div class="text-xs font-bold text-slate-700">أنشطة مقترحة</div>
        </a>
        <a href="/materials" class="bg-white hover:border-teal-500 border border-slate-200 p-4 rounded-xl text-center shadow-xs">
            <div class="text-lg font-bold text-teal-700 mb-1">{len(materials)}</div>
            <div class="text-xs font-bold text-slate-700">مواد ودروس شرعية</div>
        </a>
    </div>

    <!-- سجل الأنشطة -->
    <div id="activities-list" class="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
        <div class="flex justify-between items-center pb-3 mb-3 border-b">
            <h2 class="text-sm font-bold text-[#163629]">سجل الفعاليات والدروس الشرعية</h2>
            <a href="/activities/new" class="text-xs text-[#1b4332] font-bold">+ نشاط جديد</a>
        </div>
        <div class="space-y-3">
    '''

    if len(activities) > 0:
        for act in activities:
            eval_badge = '<span class="text-[11px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-bold">تم التقييم</span>' if act['evaluation_rating'] else f'<a href="/activities/{act["id"]}/evaluate" class="text-[11px] bg-amber-100 text-amber-900 px-2.5 py-1 rounded font-bold hover:bg-amber-200">تقييم النشاط</a>'
            lesson_info = f'<span class="text-slate-600 mr-2">• الدرس: {act["sharia_lesson_topic"]} ({act["sharia_teacher_name"]})</span>' if act['sharia_lesson_topic'] else ''
            
            body += f'''
            <div class="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 text-xs">
                <div>
                    <h3 class="font-bold text-sm text-[#163629]">{act['activity_name']}</h3>
                    <p class="text-slate-500 mt-1">فرع {act['branch_location']} • التاريخ: {act['activity_date']} • المشرف: {act['supervisor_name']} {lesson_info}</p>
                </div>
                <div class="flex items-center gap-2 self-end sm:self-auto">
                    {eval_badge}
                    <a href="/activities/{act['id']}/print" target="_blank" class="bg-[#1b4332] text-white px-3 py-1 rounded font-bold hover:bg-[#143224]">طباعة تقرير</a>
                </div>
            </div>
            '''
    else:
        body += '<p class="text-center py-6 text-slate-400 text-xs">لا توجد أنشطة مسجلة بعد. اضغط على "+ تسجيل نشاط جديد" للبدء.</p>'

    body += '</div></div>'
    return render_template_string(BASE_LAYOUT.replace('{{ content | safe }}', body))

@app.route('/activities/new', methods=['GET', 'POST'])
def create_activity():
    conn = get_db()
    if request.method == 'POST':
        name = request.form.get('activity_name', '').strip()
        branch = request.form.get('branch_location', '').strip()
        date = request.form.get('activity_date', '')
        supervisor = request.form.get('supervisor_name', '').strip()
        gender = request.form.get('gender', 'ذكور')
        teacher = request.form.get('sharia_teacher_name', '').strip()
        duration = request.form.get('sharia_lesson_duration', '').strip()
        topic = request.form.get('sharia_lesson_topic', '').strip()
        desc = request.form.get('description', '').strip()

        conn.execute('''
            INSERT INTO activities (
                user_id, user_name, activity_name, branch_location, activity_date,
                supervisor_name, gender, sharia_teacher_name, sharia_lesson_duration,
                sharia_lesson_topic, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'], session['username'], name, branch, date,
            supervisor, gender, teacher, duration, topic, desc
        ))
        conn.commit()
        conn.close()
        flash('تم تسجيل النشاط والحصة الشرعية بنجاح!')
        return redirect(url_for('index'))

    ideas = conn.execute("SELECT * FROM ideas").fetchall()
    conn.close()

    options = "".join([f'<option value="{i["title"]}">{i["title"]}</option>' for i in ideas])
    form_html = f'''
    <div class="max-w-2xl mx-auto bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <h2 class="text-base font-bold text-[#163629] mb-4 border-b pb-2">تسجيل نشاط ميداني وحصة شرعية مرافقة</h2>
        <form method="POST" class="space-y-3 text-xs">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="font-bold block mb-1">اسم النشاط *</label>
                    <input type="text" name="activity_name" required placeholder="مثال: رحلة تربوية" class="w-full p-2 border rounded-lg bg-slate-50">
                </div>
                <div>
                    <label class="font-bold block mb-1">الفرع / المكان *</label>
                    <input type="text" name="branch_location" required placeholder="مثال: فرع الصويفية" class="w-full p-2 border rounded-lg bg-slate-50">
                </div>
                <div>
                    <label class="font-bold block mb-1">تاريخ النشاط *</label>
                    <input type="date" name="activity_date" required class="w-full p-2 border rounded-lg bg-slate-50">
                </div>
                <div>
                    <label class="font-bold block mb-1">المشرف المسؤول</label>
                    <input type="text" name="supervisor_name" value="{session.get('display_name')}" class="w-full p-2 border rounded-lg bg-slate-50">
                </div>
            </div>

            <div class="p-3 bg-[#fbf9f5] border border-amber-200 rounded-xl space-y-2.5">
                <h3 class="font-bold text-[#163629]">الحصة والدرس الشرعي المرافق</h3>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <div>
                        <label class="font-bold block mb-1">اسم المدرس</label>
                        <input type="text" name="sharia_teacher_name" placeholder="اسم الشيخ" class="w-full p-2 border rounded-lg bg-white">
                    </div>
                    <div>
                        <label class="font-bold block mb-1">مدة الدرس</label>
                        <input type="text" name="sharia_lesson_duration" value="45 دقيقة" class="w-full p-2 border rounded-lg bg-white">
                    </div>
                    <div>
                        <label class="font-bold block mb-1">موضوع الدرس</label>
                        <select name="sharia_lesson_topic" class="w-full p-2 border rounded-lg bg-white">
                            <option value="">-- اختر موضوعاً --</option>
                            {options}
                        </select>
                    </div>
                </div>
            </div>

            <div>
                <label class="font-bold block mb-1">وصف النشاط</label>
                <textarea name="description" rows="2" placeholder="ملاحظات أو أهداف..." class="w-full p-2 border rounded-lg bg-slate-50"></textarea>
            </div>

            <button type="submit" class="w-full py-2.5 bg-[#1b4332] text-white font-bold rounded-xl hover:bg-[#143224]">
                حفظ واعتماد النشاط
            </button>
        </form>
    </div>
    '''
    return render_template_string(BASE_LAYOUT.replace('{{ content | safe }}', form_html))

@app.route('/ideas')
def ideas():
    conn = get_db()
    ideas_list = conn.execute("SELECT * FROM ideas").fetchall()
    conn.close()
    items = "".join([f'<div class="p-4 bg-white border border-slate-200 rounded-xl shadow-xs"><h3 class="font-bold text-sm text-[#1b4332] mb-1">{i["title"]}</h3><p class="text-xs text-slate-600">{i["description"]}</p></div>' for i in ideas_list])
    html = f'<div class="space-y-4"><h2 class="text-base font-bold text-[#163629]">الأنشطة والفعاليات المقترحة</h2><div class="grid grid-cols-1 sm:grid-cols-2 gap-3">{items}</div></div>'
    return render_template_string(BASE_LAYOUT.replace('{{ content | safe }}', html))

@app.route('/materials')
def materials():
    conn = get_db()
    mats_list = conn.execute("SELECT * FROM materials").fetchall()
    conn.close()
    items = "".join([f'<div class="p-4 bg-white border border-slate-200 rounded-xl shadow-xs flex justify-between items-center"><h3 class="font-bold text-sm text-slate-800">{m["title"]}</h3><span class="text-xs bg-emerald-100 text-emerald-800 font-bold px-2 py-1 rounded">معتمد</span></div>' for m in mats_list])
    html = f'<div class="space-y-4"><h2 class="text-base font-bold text-[#163629]">المواد والدروس الشرعية المعتمدة</h2><div class="grid grid-cols-1 sm:grid-cols-2 gap-3">{items}</div></div>'
    return render_template_string(BASE_LAYOUT.replace('{{ content | safe }}', html))

@app.route('/activities/<int:act_id>/evaluate', methods=['GET', 'POST'])
def evaluate(act_id):
    conn = get_db()
    act = conn.execute("SELECT * FROM activities WHERE id = ?", (act_id,)).fetchone()
    if request.method == 'POST':
        rating = int(request.form.get('rating', 5))
        pros = request.form.get('pros', '')
        cons = request.form.get('cons', '')
        conn.execute("UPDATE activities SET evaluation_rating = ?, evaluation_pros = ?, evaluation_cons = ? WHERE id = ?", (rating, pros, cons, act_id))
        conn.commit()
        conn.close()
        flash('تم حفظ تقييم النشاط بنجاح!')
        return redirect(url_for('index'))
    conn.close()

    html = f'''
    <div class="max-w-md mx-auto bg-white p-5 rounded-2xl border border-slate-200 shadow-xs text-xs">
        <h2 class="text-sm font-bold text-[#163629] mb-3">تقييم نشاط: {act['activity_name']}</h2>
        <form method="POST" class="space-y-3">
            <div>
                <label class="font-bold block mb-1">التقييم (من 5 نجوم)</label>
                <input type="number" name="rating" min="1" max="5" value="5" class="w-full p-2 border rounded-lg">
            </div>
            <div>
                <label class="font-bold block mb-1">الإيجابيات</label>
                <textarea name="pros" rows="2" class="w-full p-2 border rounded-lg"></textarea>
            </div>
            <div>
                <label class="font-bold block mb-1">ملاحظات التحسين</label>
                <textarea name="cons" rows="2" class="w-full p-2 border rounded-lg"></textarea>
            </div>
            <button type="submit" class="w-full py-2 bg-[#1b4332] text-white font-bold rounded-xl hover:bg-[#143224]">حفظ التقييم</button>
        </form>
    </div>
    '''
    return render_template_string(BASE_LAYOUT.replace('{{ content | safe }}', html))

# صفحة طباعة التقرير الرسمية بنقرة واحدة (تحفظ كـ PDF فوراً بدون مكتبات خارجية)
@app.route('/activities/<int:act_id>/print')
def print_report(act_id):
    conn = get_db()
    act = conn.execute("SELECT * FROM activities WHERE id = ?", (act_id,)).fetchone()
    conn.close()
    if not act:
        return "النشاط غير موجود", 404

    return f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تقرير نشاط: {act['activity_name']}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Cairo', sans-serif; }}
            @media print {{
                .no-print {{ display: none !important; }}
                body {{ padding: 0; background: white; }}
            }}
        </style>
    </head>
    <body class="bg-slate-100 p-4 sm:p-8">
        <div class="max-w-2xl mx-auto bg-white p-8 rounded-2xl border border-slate-300 shadow-sm print:border-none print:shadow-none">
            <div class="no-print mb-6 flex justify-between items-center bg-amber-50 p-3 rounded-xl border border-amber-200">
                <span class="text-xs text-amber-800 font-bold">جاهز للطباعة أو الحفظ كـ PDF:</span>
                <button onclick="window.print()" class="bg-[#1b4332] text-white px-4 py-1.5 rounded-lg text-xs font-bold cursor-pointer hover:bg-[#143224]">طباعة / حفظ كـ PDF</button>
            </div>

            <div class="border-b-2 border-[#163629] pb-4 mb-6 text-center">
                <h1 class="text-xl font-bold text-[#163629]">مركز الإمام الشافعي</h1>
                <p class="text-xs text-slate-500">تقرير نشاط رسمي وحصة شرعية مرافقة</p>
            </div>

            <table class="w-full text-xs text-right mb-6 border-collapse">
                <tr class="border-b"><th class="py-2 text-slate-500 font-bold w-1/3">اسم النشاط:</th><td class="py-2 font-bold text-slate-900">{act['activity_name']}</td></tr>
                <tr class="border-b"><th class="py-2 text-slate-500 font-bold">الفرع:</th><td class="py-2">{act['branch_location']}</td></tr>
                <tr class="border-b"><th class="py-2 text-slate-500 font-bold">تاريخ الإقامة:</th><td class="py-2">{act['activity_date']}</td></tr>
                <tr class="border-b"><th class="py-2 text-slate-500 font-bold">المشرف المسؤول:</th><td class="py-2">{act['supervisor_name']}</td></tr>
                <tr class="border-b"><th class="py-2 text-slate-500 font-bold">موضوع الدرس الشرعي:</th><td class="py-2 font-bold text-[#1b4332]">{act['sharia_lesson_topic'] or 'لا يوجد'}</td></tr>
                <tr class="border-b"><th class="py-2 text-slate-500 font-bold">مدرس الحصة:</th><td class="py-2">{act['sharia_teacher_name'] or 'لا يوجد'} ({act['sharia_lesson_duration']})</td></tr>
                <tr class="border-b"><th class="py-2 text-slate-500 font-bold">وصف النشاط:</th><td class="py-2 text-slate-700">{act['description'] or 'لا يوجد'}</td></tr>
            </table>

            <div class="border-t pt-8 mt-12 flex justify-between text-xs text-slate-600 text-center">
                <div>توقيع مشرف النشاط: ________________</div>
                <div>اعتماد إدارة المركز: ________________</div>
            </div>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)