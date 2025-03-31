from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
import uuid

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Maksimum 16 MB

# Veri klasörü oluşturma
DB_FOLDER = 'db'
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# JSON dosya yolları
EVENTS_FILE = os.path.join(DB_FOLDER, 'events.json')
COMMENTS_FILE = os.path.join(DB_FOLDER, 'comments.json')

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

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/')
def home():
    return render_template('index.html', events=events)

@app.route('/upload', methods=['GET', 'POST'])
def upload_event():
    if request.method == 'POST':
        event_name = request.form['event_name']
        event_description = request.form['event_description']
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
                'image': unique_filename,
                'date': event_date
            }
            
            events.append(new_event)
            save_json_file(EVENTS_FILE, events)
            return redirect(url_for('home'))
    return render_template('upload.html')

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = next((e for e in events if e['id'] == event_id), None)
    if event:
        # Etkinliğe ait yorumları filtrele
        event_comments = [c for c in comments if c['event_id'] == event_id]
        return render_template('event_detail.html', event=event, comments=event_comments)
    else:
        return "Etkinlik bulunamadı!", 404

@app.route('/event/<int:event_id>/comment', methods=['POST'])
def add_comment(event_id):
    comment_author = request.form['author']
    comment_text = request.form['comment']
    
    event = next((e for e in events if e['id'] == event_id), None)
    if event:
        comment_id = len(comments) + 1
        new_comment = {
            'id': comment_id,
            'event_id': event_id,
            'author': comment_author,
            'text': comment_text,
            'likes': 0,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        comments.append(new_comment)
        save_json_file(COMMENTS_FILE, comments)
        return redirect(url_for('event_detail', event_id=event_id))
    else:
        return "Etkinlik bulunamadı!", 404

@app.route('/event/<int:event_id>/like/<int:comment_id>', methods=['POST'])
def like_comment(event_id, comment_id):
    comment = next((c for c in comments if c['id'] == comment_id and c['event_id'] == event_id), None)
    if comment:
        comment['likes'] += 1
        save_json_file(COMMENTS_FILE, comments)
    return redirect(url_for('event_detail', event_id=event_id))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
