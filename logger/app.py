from flask import Flask, render_template, send_file, jsonify, request
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Пути к логам
LOGS_DIR = "/app/logs"
APP_LOG = os.path.join(LOGS_DIR, "app.log")
WORKER_LOG = os.path.join(LOGS_DIR, "worker.log")


def read_log_file(filepath, lines=200):
    """Читает последние N строк лог-файла"""
    if not os.path.exists(filepath):
        return ["Файл логов не найден"]

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception as e:
        return [f"Ошибка чтения файла: {str(e)}"]


def get_log_stats(filepath):
    """Получает статистику по лог-файлу"""
    if not os.path.exists(filepath):
        return {"exists": False, "size": 0, "lines": 0}

    try:
        size = os.path.getsize(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = sum(1 for _ in f)
        return {"exists": True, "size": size, "lines": lines}
    except:
        return {"exists": False, "size": 0, "lines": 0}


@app.route('/')
def index():
    """Главная страница логов"""
    app_stats = get_log_stats(APP_LOG)
    worker_stats = get_log_stats(WORKER_LOG)

    app_logs = read_log_file(APP_LOG, 200) if app_stats["exists"] else []
    worker_logs = read_log_file(WORKER_LOG, 200) if worker_stats["exists"] else []

    return render_template('dashboard.html',
                           app_logs=app_logs,
                           worker_logs=worker_logs,
                           app_stats=app_stats,
                           worker_stats=worker_stats)


@app.route('/api/logs/<log_type>')
def get_logs(log_type):
    """API для получения логов"""
    if log_type == 'app':
        filepath = APP_LOG
    elif log_type == 'worker':
        filepath = WORKER_LOG
    else:
        return jsonify({'error': 'Invalid log type'}), 400

    lines = request.args.get('lines', 200, type=int)
    log_lines = read_log_file(filepath, lines)

    return jsonify({
        'type': log_type,
        'lines': len(log_lines),
        'content': log_lines
    })


@app.route('/download/<log_type>')
def download_log(log_type):
    """Скачивание лог-файла"""
    if log_type == 'app':
        filepath = APP_LOG
        filename = 'app.log'
    elif log_type == 'worker':
        filepath = WORKER_LOG
        filename = 'worker.log'
    else:
        return jsonify({'error': 'Invalid log type'}), 400

    if not os.path.exists(filepath):
        return jsonify({'error': 'Log file not found'}), 404

    return send_file(filepath,
                     as_attachment=True,
                     download_name=filename,
                     mimetype='text/plain')


@app.route('/clear/<log_type>', methods=['POST'])
def clear_log(log_type):
    """Очистка лог-файла"""
    if log_type == 'app':
        filepath = APP_LOG
    elif log_type == 'worker':
        filepath = WORKER_LOG
    else:
        return jsonify({'error': 'Invalid log type'}), 400

    try:
        # Создаем пустой файл
        open(filepath, 'w').close()
        return jsonify({'success': True, 'message': f'Log {log_type} cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)