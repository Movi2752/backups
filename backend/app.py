from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import shutil
import json
from datetime import datetime, timedelta, timezone
import logging
import pytz


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Московское время
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


# Логирование с московским временем
class MoscowTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, MOSCOW_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')


os.makedirs("logs", exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Файловый хендлер с московским временем
file_handler = logging.FileHandler("logs/app.log")
file_formatter = MoscowTimeFormatter('%(asctime)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Консольный хендлер
console_handler = logging.StreamHandler()
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)

# Директории
os.makedirs("uploads", exist_ok=True)
os.makedirs("backups", exist_ok=True)
os.makedirs("data", exist_ok=True)

FILES_JSON = "data/files.json"
if not os.path.exists(FILES_JSON):
    with open(FILES_JSON, "w") as f:
        json.dump([], f)


def get_moscow_time():
    """Возвращает текущее время в Москве"""
    return datetime.now(MOSCOW_TZ)


@app.get("/")
def home():
    return {"message": "Backup Platform API"}


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), period_value: int = 1, period_unit: str = "hours"):
    try:
        # Валидация минимального периода
        if period_unit == "seconds" and period_value < 30:
            return {"error": "Минимальный период для секунд: 30"}

        if period_value < 1:
            return {"error": "Период должен быть не менее 1"}

        # Сохраняем файл
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Читаем файлы
        with open(FILES_JSON, "r") as f:
            files = json.load(f)

        # Создаем запись
        file_id = len(files) + 1
        now = get_moscow_time()

        # Вычисляем время следующего бэкапа
        if period_unit == "seconds":
            next_backup = now + timedelta(seconds=period_value)
        elif period_unit == "minutes":
            next_backup = now + timedelta(minutes=period_value)
        elif period_unit == "hours":
            next_backup = now + timedelta(hours=period_value)
        elif period_unit == "days":
            next_backup = now + timedelta(days=period_value)
        else:
            next_backup = now + timedelta(hours=1)

        file_data = {
            "id": file_id,
            "filename": file.filename,
            "path": file_path,
            "upload_date": now.isoformat(),
            "period_value": period_value,
            "period_unit": period_unit,
            "next_backup": next_backup.isoformat(),
            "last_backup": None,
            "backup_count": 0,
            "backups_history": []
        }

        files.append(file_data)

        # Сохраняем
        with open(FILES_JSON, "w") as f:
            json.dump(files, f, indent=2)

        # Логируем
        logger.info(f"Файл загружен: {file.filename}, период: {period_value} {period_unit}")

        return {
            "message": "File uploaded",
            "id": file_id,
            "filename": file.filename
        }
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        return {"error": str(e)}


@app.get("/files/")
def get_files():
    try:
        with open(FILES_JSON, "r") as f:
            files = json.load(f)
        return files
    except:
        return []


@app.delete("/files/{file_id}")
def delete_file(file_id: int):
    try:
        with open(FILES_JSON, "r") as f:
            files = json.load(f)

        # Находим файл
        file_to_delete = None
        for f in files:
            if f["id"] == file_id:
                file_to_delete = f
                break

        if not file_to_delete:
            return {"error": "File not found"}

        # Удаляем файл
        if os.path.exists(file_to_delete["path"]):
            os.remove(file_to_delete["path"])

        # Удаляем из списка
        files = [f for f in files if f["id"] != file_id]

        # Сохраняем
        with open(FILES_JSON, "w") as f:
            json.dump(files, f, indent=2)

        logger.info(f"Файл удален: {file_to_delete['filename']}")
        return {"message": "File deleted"}
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        return {"error": str(e)}


@app.get("/backups/{date}/{filename}")
async def download_backup(date: str, filename: str):
    """Endpoint для скачивания бэкапов"""
    try:
        backup_path = f"backups/{date}/{filename}"
        if os.path.exists(backup_path):
            return FileResponse(
                backup_path,
                filename=filename,
                media_type='application/octet-stream'
            )
        else:
            raise HTTPException(status_code=404, detail="Backup not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}

