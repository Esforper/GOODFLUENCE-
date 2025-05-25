from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime
import uuid
from functools import wraps

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Maksimum 16 MB
app.secret_key = 'your-secret-key-here'  # Değiştirin!

# Veri klasörü oluşturma
DB_FOLDER = 'db'
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# JSON dosya yolları
EVENTS_FILE = os.path.join(DB_FOLDER, 'events.json')
COMMENTS_FILE = os.path.join(DB_FOLDER, 'comments.json')
USERS_FILE = os.path.join(DB_FOLDER, 'users.json')
FOLLOWS_FILE = os.path.join(DB_FOLDER, 'follows.json')
ATTENDEES_FILE = os.path.join(DB_FOLDER, 'attendees.json')

# Etkinlik kategorileri
CATEGORIES = [
    'Teknoloji', 'Spor', 'Sanat', 'Müzik', 'Eğitim', 
    'İş', 'Sosyal', 'Kültür', 'Sağlık', 'Diğer'
]

# JSON dosyalarını yükleme fonksiyonu
def load_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# JSON dosyalarına kaydetme fonksiyonu
def save_json_file(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Başlangıçta verileri yükle
events = load_json_file(EVENTS_FILE)
comments = load_json_file(COMMENTS_FILE)
users = load_json_file(USERS_FILE)
follows = load_json_file(FOLLOWS_FILE)
attendees = load_json_file(ATTENDEES_FILE)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Login gerekli decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Kullanıcı bilgilerini alma
def get_current_user():
    if 'user_id' in session:
        return next((u for u in users if u['id'] == session['user_id']), None)
    return None

@app.route('/')
def home():
    # Filtreleme parametreleri
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    
    filtered_events = events
    
    # Kategori filtresi
    if category:
        filtered_events = [e for e in filtered_events if e.get('category') == category]
    
    # Arama filtresi
    if search:
        search_lower = search.lower()
        filtered_events = [e for e in filtered_events if 
                         search_lower in e['name'].lower() or 
                         search_lower in e['description'].lower()]
    
    # Her etkinlik için takip bilgisi ekle
    current_user = get_current_user()
    for event in filtered_events:
        event['is_following'] = False
        event['attendee_count'] = len([a for a in attendees if a['event_id'] == event['id']])
        event['is_attending'] = False
        
        if current_user:
            # Takip kontrolü
            event['is_following'] = any(f['user_id'] == current_user['id'] and 
                                      f['event_id'] == event['id'] for f in follows)
            # Katılım kontrolü
            event['is_attending'] = any(a['user_id'] == current_user['id'] and 
                                      a['event_id'] == event['id'] for a in attendees)
    
    return render_template('index.html', 
                         events=filtered_events, 
                         categories=CATEGORIES,
                         selected_category=category,
                         search=search,
                         current_user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Kullanıcı adı kontrolü
        if any(u['username'] == username for u in users):
            flash('Bu kullanıcı adı zaten kullanılıyor!', 'danger')
            return render_template('register.html')
        
        # Email kontrolü
        if any(u['email'] == email for u in users):
            flash('Bu email adresi zaten kullanılıyor!', 'danger')
            return render_template('register.html')
        
        # Yeni kullanıcı oluştur
        user_id = len(users) + 1
        new_user = {
            'id': user_id,
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        users.append(new_user)
        save_json_file(USERS_FILE, users)
        
        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = next((u for u in users if u['username'] == username), None)
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Hoş geldiniz, {user["username"]}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('home'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_event():
    if request.method == 'POST':
        event_name = request.form['event_name']
        event_description = request.form['event_description']
        event_category = request.form['event_category']
        event_image = request.files['event_image']

        if event_image:
            # Benzersiz dosya adı oluştur
            file_extension = os.path.splitext(event_image.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            event_image.save(image_path)

            # Etkinlik bilgilerini oluştur
            event_id = len(events) + 1
            event_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_event = {
                'id': event_id,
                'name': event_name,
                'description': event_description,
                'category': event_category,
                'image': unique_filename,
                'date': event_date,
                'creator_id': session['user_id']
            }
            
            events.append(new_event)
            save_json_file(EVENTS_FILE, events)
            flash('Etkinlik başarıyla oluşturuldu!', 'success')
            return redirect(url_for('home'))
    
    return render_template('upload.html', categories=CATEGORIES)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = next((e for e in events if e['id'] == event_id), None)
    if event:
        # Etkinliğe ait yorumları filtrele
        event_comments = [c for c in comments if c['event_id'] == event_id]
        
        # Etkinlik sahibi bilgisi
        creator = next((u for u in users if u['id'] == event.get('creator_id')), None)
        event['creator_name'] = creator['username'] if creator else 'Bilinmiyor'
        
        # Takip ve katılım bilgileri
        current_user = get_current_user()
        event['is_following'] = False
        event['is_attending'] = False
        event['attendee_count'] = len([a for a in attendees if a['event_id'] == event_id])
        
        if current_user:
            event['is_following'] = any(f['user_id'] == current_user['id'] and 
                                      f['event_id'] == event_id for f in follows)
            event['is_attending'] = any(a['user_id'] == current_user['id'] and 
                                      a['event_id'] == event_id for a in attendees)
        
        return render_template('event_detail.html', 
                             event=event, 
                             comments=event_comments,
                             current_user=current_user)
    else:
        flash('Etkinlik bulunamadı!', 'danger')
        return redirect(url_for('home'))

@app.route('/event/<int:event_id>/comment', methods=['POST'])
@login_required
def add_comment(event_id):
    comment_text = request.form['comment']
    current_user = get_current_user()
    
    event = next((e for e in events if e['id'] == event_id), None)
    if event:
        comment_id = len(comments) + 1
        new_comment = {
            'id': comment_id,
            'event_id': event_id,
            'author': current_user['username'],
            'user_id': current_user['id'],
            'text': comment_text,
            'likes': 0,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        comments.append(new_comment)
        save_json_file(COMMENTS_FILE, comments)
        flash('Yorumunuz eklendi!', 'success')
        return redirect(url_for('event_detail', event_id=event_id))
    else:
        flash('Etkinlik bulunamadı!', 'danger')
        return redirect(url_for('home'))

@app.route('/event/<int:event_id>/like/<int:comment_id>', methods=['POST'])
@login_required
def like_comment(event_id, comment_id):
    comment = next((c for c in comments if c['id'] == comment_id and c['event_id'] == event_id), None)
    if comment:
        comment['likes'] += 1
        save_json_file(COMMENTS_FILE, comments)
        flash('Yorum beğenildi!', 'success')
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/event/<int:event_id>/follow', methods=['POST'])
@login_required
def follow_event(event_id):
    current_user = get_current_user()
    
    # Zaten takip edip etmediğini kontrol et
    existing_follow = next((f for f in follows if f['user_id'] == current_user['id'] and 
                          f['event_id'] == event_id), None)
    
    if not existing_follow:
        follow_id = len(follows) + 1
        new_follow = {
            'id': follow_id,
            'user_id': current_user['id'],
            'event_id': event_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        follows.append(new_follow)
        save_json_file(FOLLOWS_FILE, follows)
        flash('Etkinlik takip listesine eklendi!', 'success')
    else:
        flash('Bu etkinliği zaten takip ediyorsunuz!', 'info')
    
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/event/<int:event_id>/unfollow', methods=['POST'])
@login_required
def unfollow_event(event_id):
    current_user = get_current_user()
    
    # Takibi kaldır
    global follows
    follows = [f for f in follows if not (f['user_id'] == current_user['id'] and 
                                        f['event_id'] == event_id)]
    save_json_file(FOLLOWS_FILE, follows)
    flash('Etkinlik takip listesinden çıkarıldı!', 'info')
    
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/event/<int:event_id>/attend', methods=['POST'])
@login_required
def attend_event(event_id):
    current_user = get_current_user()
    
    # Zaten katılım onayı verip vermediğini kontrol et
    existing_attendee = next((a for a in attendees if a['user_id'] == current_user['id'] and 
                            a['event_id'] == event_id), None)
    
    if not existing_attendee:
        attendee_id = len(attendees) + 1
        new_attendee = {
            'id': attendee_id,
            'user_id': current_user['id'],
            'event_id': event_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        attendees.append(new_attendee)
        save_json_file(ATTENDEES_FILE, attendees)
        flash('Etkinliğe katılacağınızı onayladınız!', 'success')
    else:
        flash('Bu etkinliğe zaten katılım onayı verdiniz!', 'info')
    
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/event/<int:event_id>/unattend', methods=['POST'])
@login_required
def unattend_event(event_id):
    current_user = get_current_user()
    
    # Katılım onayını kaldır
    global attendees
    attendees = [a for a in attendees if not (a['user_id'] == current_user['id'] and 
                                            a['event_id'] == event_id)]
    save_json_file(ATTENDEES_FILE, attendees)
    flash('Etkinlik katılımınız iptal edildi!', 'info')
    
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/my-events')
@login_required
def my_events():
    current_user = get_current_user()
    
    # Kullanıcının takip ettiği etkinlikler
    followed_event_ids = [f['event_id'] for f in follows if f['user_id'] == current_user['id']]
    followed_events = [e for e in events if e['id'] in followed_event_ids]
    
    # Kullanıcının katılacağı etkinlikler
    attending_event_ids = [a['event_id'] for a in attendees if a['user_id'] == current_user['id']]
    attending_events = [e for e in events if e['id'] in attending_event_ids]
    
    # Kullanıcının oluşturduğu etkinlikler
    created_events = [e for e in events if e.get('creator_id') == current_user['id']]
    
    return render_template('my_events.html', 
                         followed_events=followed_events,
                         attending_events=attending_events,
                         created_events=created_events,
                         current_user=current_user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)