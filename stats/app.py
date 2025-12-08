from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

app = FastAPI(title="Stats Dashboard")

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")

# Константы
MOSCOW_TZ_OFFSET = timedelta(hours=3)  # Москва UTC+3
UPLOADS_DIR = "/app/uploads"  # Будем монтировать volume
BACKUPS_DIR = "/app/backups"  # Будем монтировать volume
DATA_DIR = "/app/data"  # Будем монтировать volume
LOGS_DIR = "/app/logs"  # Будем монтировать volume


def get_moscow_time() -> datetime:
    """Возвращает текущее время в Москве (UTC+3)"""
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(timezone(MOSCOW_TZ_OFFSET))


def moscow_to_datetime(dt_str: str) -> datetime:
    """Конвертирует строку времени в datetime с московской таймзоной"""
    if not dt_str:
        return None

    # Пробуем разные форматы дат
    for fmt in ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"]:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return dt.astimezone(timezone(MOSCOW_TZ_OFFSET))
        except ValueError:
            continue

    # Если не получилось с таймзоной, добавляем московскую таймзону
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.astimezone(timezone(MOSCOW_TZ_OFFSET))
    except:
        return None


def load_files_data() -> List[Dict]:
    """Загружает данные о файлах из files.json"""
    files_json_path = Path(DATA_DIR) / "files.json"

    if not files_json_path.exists():
        return []

    try:
        with open(files_json_path, 'r', encoding='utf-8') as f:
            files = json.load(f)
        return files
    except Exception as e:
        print(f"Ошибка загрузки files.json: {e}")
        return []


def count_backups_today(files: List[Dict]) -> int:
    """Считает количество бэкапов, созданных сегодня"""
    today = get_moscow_time().strftime("%Y-%m-%d")
    count = 0

    for file in files:
        if file.get("last_backup"):
            last_backup_dt = moscow_to_datetime(file["last_backup"])
            if last_backup_dt and last_backup_dt.strftime("%Y-%m-%d") == today:
                count += 1
        # Также считаем по истории бэкапов
        if file.get("backups_history"):
            for backup in file["backups_history"]:
                backup_dt = moscow_to_datetime(backup["time"])
                if backup_dt and backup_dt.strftime("%Y-%m-%d") == today:
                    count += 1

    return count


def count_files_uploaded_today(files: List[Dict]) -> int:
    """Считает количество файлов, загруженных сегодня"""
    today = get_moscow_time().strftime("%Y-%m-%d")
    count = 0

    for file in files:
        if file.get("upload_date"):
            upload_dt = moscow_to_datetime(file["upload_date"])
            if upload_dt and upload_dt.strftime("%Y-%m-%d") == today:
                count += 1

    return count


def get_total_backup_count(files: List[Dict]) -> int:
    """Общее количество созданных бэкапов"""
    total = 0
    for file in files:
        total += file.get("backup_count", 0)
    return total


def get_active_files_count(files: List[Dict]) -> int:
    """Количество активных файлов (у которых есть next_backup)"""
    count = 0
    now = get_moscow_time()

    for file in files:
        if file.get("next_backup"):
            next_backup_dt = moscow_to_datetime(file["next_backup"])
            if next_backup_dt and next_backup_dt > now:
                count += 1

    return count


def get_last_backup_time(files: List[Dict]) -> Optional[str]:
    """Время последнего бэкапа"""
    last_backup = None

    for file in files:
        if file.get("last_backup"):
            file_last_backup_dt = moscow_to_datetime(file["last_backup"])
            if file_last_backup_dt:
                if last_backup is None or file_last_backup_dt > last_backup:
                    last_backup = file_last_backup_dt

    return last_backup.isoformat() if last_backup else None


def get_system_uptime() -> str:
    """Получаем время работы системы (по времени создания первого лога)"""
    try:
        log_files = list(Path(LOGS_DIR).glob("*.log"))
        if log_files:
            oldest_log = min(log_files, key=lambda x: x.stat().st_ctime)
            uptime_seconds = datetime.now().timestamp() - oldest_log.stat().st_ctime

            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)

            if days > 0:
                return f"{days}д {hours}ч"
            elif hours > 0:
                return f"{hours}ч {minutes}м"
            else:
                return f"{minutes}м"
    except:
        pass

    return "N/A"


def get_storage_stats() -> Dict[str, float]:
    """Статистика использования хранилища"""
    stats = {
        "uploads_size_mb": 0.0,
        "backups_size_mb": 0.0,
        "total_size_mb": 0.0
    }

    try:
        # Размер uploads
        if Path(UPLOADS_DIR).exists():
            uploads_size = sum(f.stat().st_size for f in Path(UPLOADS_DIR).rglob('*') if f.is_file())
            stats["uploads_size_mb"] = round(uploads_size / 1024 / 1024, 2)

        # Размер backups
        if Path(BACKUPS_DIR).exists():
            backups_size = sum(f.stat().st_size for f in Path(BACKUPS_DIR).rglob('*') if f.is_file())
            stats["backups_size_mb"] = round(backups_size / 1024 / 1024, 2)

        stats["total_size_mb"] = round(stats["uploads_size_mb"] + stats["backups_size_mb"], 2)
    except:
        pass

    return stats


def get_daily_statistics(files: List[Dict], days: int = 7) -> Dict:
    """Статистика по дням"""
    now = get_moscow_time()
    result = {
        "labels": [],
        "backups": [],
        "uploads": [],
        "errors": []  # Пока не реализовано
    }

    for i in range(days - 1, -1, -1):
        date = now - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        result["labels"].append(date.strftime("%d.%m"))

        # Считаем бэкапы за этот день
        day_backups = 0
        for file in files:
            if file.get("backups_history"):
                for backup in file["backups_history"]:
                    backup_dt = moscow_to_datetime(backup["time"])
                    if backup_dt and backup_dt.strftime("%Y-%m-%d") == date_str:
                        day_backups += 1

        # Считаем загрузки файлов за этот день
        day_uploads = 0
        for file in files:
            if file.get("upload_date"):
                upload_dt = moscow_to_datetime(file["upload_date"])
                if upload_dt and upload_dt.strftime("%Y-%m-%d") == date_str:
                    day_uploads += 1

        result["backups"].append(day_backups)
        result["uploads"].append(day_uploads)
        result["errors"].append(0)  # Пока нет данных об ошибках

    return result


def get_hourly_statistics(files: List[Dict], hours: int = 24) -> Dict:
    """Статистика по часам"""
    now = get_moscow_time()
    result = {
        "labels": [],
        "backups": [],
        "uploads": []
    }

    for i in range(hours - 1, -1, -1):
        hour = now - timedelta(hours=i)
        hour_str = hour.strftime("%Y-%m-%d %H:00")
        result["labels"].append(hour.strftime("%H:00"))

        # Считаем бэкапы за этот час
        hour_backups = 0
        for file in files:
            if file.get("backups_history"):
                for backup in file["backups_history"]:
                    backup_dt = moscow_to_datetime(backup["time"])
                    if backup_dt and backup_dt.strftime("%Y-%m-%d %H:00") == hour_str:
                        hour_backups += 1

        # Считаем загрузки файлов за этот час
        hour_uploads = 0
        for file in files:
            if file.get("upload_date"):
                upload_dt = moscow_to_datetime(file["upload_date"])
                if upload_dt and upload_dt.strftime("%Y-%m-%d %H:00") == hour_str:
                    hour_uploads += 1

        result["backups"].append(hour_backups)
        result["uploads"].append(hour_uploads)

    return result


def get_top_files(files: List[Dict], limit: int = 10) -> List[Dict]:
    """Топ файлов по количеству бэкапов"""
    # Сортируем файлы по количеству бэкапов
    sorted_files = sorted(files, key=lambda x: x.get("backup_count", 0), reverse=True)

    result = []
    for i, file in enumerate(sorted_files[:limit]):
        result.append({
            "filename": file.get("filename", f"file_{i + 1}"),
            "backups": file.get("backup_count", 0),
            "last_backup": file.get("last_backup")
        })

    return result


def get_realtime_stats(files: List[Dict]) -> Dict:
    """Статистика в реальном времени"""
    now = get_moscow_time()

    # Файлы, готовые к бэкапу прямо сейчас
    pending_backups = 0
    for file in files:
        if file.get("next_backup"):
            next_backup_dt = moscow_to_datetime(file["next_backup"])
            if next_backup_dt and next_backup_dt <= now:
                pending_backups += 1

    # Файлы в процессе бэкапа (за последние 30 секунд)
    active_backups = 0
    thirty_seconds_ago = now - timedelta(seconds=30)
    for file in files:
        if file.get("last_backup"):
            last_backup_dt = moscow_to_datetime(file["last_backup"])
            if last_backup_dt and last_backup_dt >= thirty_seconds_ago:
                active_backups += 1

    return {
        "timestamp": now.strftime("%H:%M:%S"),
        "active_backups": active_backups,
        "queue_size": pending_backups,
        "redis_memory_mb": 0,
        "redis_connections": 0,
        "redis_ops_per_sec": 0
    }


# Главная страница
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "stats", "timestamp": get_moscow_time().isoformat()}


# API для общей статистики
@app.get("/api/stats/overview")
async def get_overview():
    files = load_files_data()
    storage_stats = get_storage_stats()

    return {
        "total_backups": get_total_backup_count(files),
        "total_files": len(files),
        "today_backups": count_backups_today(files),
        "today_files": count_files_uploaded_today(files),
        "active_files": get_active_files_count(files),
        "redis_connected": False,  # Мы не используем Redis
        "last_backup": get_last_backup_time(files),
        "uptime": get_system_uptime(),
        "storage": storage_stats
    }


# API для ежедневной статистики
@app.get("/api/stats/daily")
async def get_daily_stats(days: int = 7):
    files = load_files_data()
    return get_daily_statistics(files, days)


# API для почасовой статистики
@app.get("/api/stats/hourly")
async def get_hourly_stats(hours: int = 24):
    files = load_files_data()
    return get_hourly_statistics(files, hours)


# API для real-time статистики
@app.get("/api/stats/realtime")
async def get_realtime():
    files = load_files_data()
    return get_realtime_stats(files)


# API для топ файлов
@app.get("/api/stats/top-files")
async def get_top_files_api(limit: int = 10):
    files = load_files_data()
    return get_top_files(files, limit)


# API для получения списка всех файлов
@app.get("/api/files")
async def get_all_files():
    files = load_files_data()
    return files


# API для получения детальной информации о файле
@app.get("/api/files/{file_id}")
async def get_file(file_id: int):
    files = load_files_data()
    for file in files:
        if file.get("id") == file_id:
            return file
    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)