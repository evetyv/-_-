

import sqlite3
import feedparser
import re
from flask import Flask, request, render_template, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logfile.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Создание базы данных и таблиц (если еще не созданы)
conn = sqlite3.connect('news_monitor.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    url TEXT NOT NULL UNIQUE
)
''')



cursor.execute('''
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    link TEXT,
    source_id INTEGER,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(source_id) REFERENCES sources(id)
)
''')

conn.commit()
conn.close()


def fetch_and_process():
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()

    # Получаем все источники
    cursor.execute("SELECT id, url FROM sources")
    sources = cursor.fetchall()

    # Получаем все ключевые слова
    cursor.execute("SELECT word FROM keywords")
    keywords = [row[0].lower() for row in cursor.fetchall()]

    logging.info(f"Starting to process sources : {len(sources)} items.")
    
    for source_id, url in sources:
        logging.info(f"Processing: {url}")
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get('title', '')
            description = entry.get('description', '')
            link = entry.get('link', '')

            combined_text = (title + ' ' + description).lower()
            if any(re.search(r'\b' + re.escape(word) + r'\b', combined_text) for word in keywords):
                cursor.execute("SELECT id FROM news WHERE link=?", (link,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        "INSERT INTO news (title, description, link, source_id) VALUES (?, ?, ?, ?)",
                        (title, description, link, source_id)
                    )
                    conn.commit()
                    logging.info(f"Added a news item: {title} ({link})")
        logging.info(f"Processing completed for the source: {url}")
    
    conn.close()

app = Flask(__name__)


@app.route('/')
def index():
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM news")
    news_list = cursor.fetchall()
    conn.close()
    return render_template('index.html', news=news_list)

@app.route('/add_source', methods=['GET', 'POST'])
def add_source():
    if request.method == 'POST':
        name = request.form['name']
        url = request.form['url']
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO sources (name, url) VALUES (?, ?)", (name, url))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
        return redirect(url_for('index'))
    
    return render_template('add_source.html')

@app.route('/add_keyword', methods=['GET', 'POST'])
def add_keyword():
    if request.method == 'POST':
        word = request.form['word']
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO keywords (word) VALUES (?)", (word,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        return redirect(url_for('index'))
    
    return render_template('add_keyword.html')


@app.route('/delete_all_sources', methods=['POST'])
def delete_all_sources():
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sources")
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_source', methods=['POST'])
def delete_source():
    source_id = request.form.get('source_id')
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sources WHERE id=?", (source_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage'))

@app.route('/delete_all_keywords', methods=['POST'])
def delete_all_keywords():
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keywords")
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_keyword', methods=['POST'])
def delete_keyword():
    keyword_id = request.form.get('keyword_id')
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keywords WHERE id=?", (keyword_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage'))

@app.route('/manage')
def manage():
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()

    # Получаем все источники с id и url
    cursor.execute("SELECT id, name, url FROM sources")
    sources = cursor.fetchall()

    # Получаем все ключевые слова с id и word
    cursor.execute("SELECT id, word FROM keywords")
    keywords = cursor.fetchall()

    conn.close()
    
    return render_template('manage.html', sources=sources, keywords=keywords)

@app.route('/delete_all_news', methods=['POST'])
def delete_all_news():
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM news")
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Запускаем планировщик перед запуском сервера
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_process, 'interval', minutes=10)
    scheduler.start()

    # Запуск Flask приложения
    app.run(debug=True, use_reloader=False)
    
    
    