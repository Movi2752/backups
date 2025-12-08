import time
import os
import shutil
import json
from datetime import datetime, timedelta
import pytz
import schedule

# Московское время
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Логирование
os.makedirs("logs", exist_ok=True)


def get_moscow_time():
    """Возвращает текущее время в Москве"""
    return datetime.now(MOSCOW_TZ)


def log_message(message):
    timestamp = get_moscow_time().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {message}"
    print(log_entry)
    with open("logs/worker.log", "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")


def check_backups():
    try:
        if not os.path.exists("data/files.json"):
            return

        with open("data/files.json", "r", encoding="utf-8") as f:
            files = json.load(f)

        updated = False
        current_time = get_moscow_time()

        for file in files:
            # Пропускаем если нет следующего бэкапа
            if not file.get("next_backup"):
                continue

            try:
                next_backup = datetime.fromisoformat(file["next_backup"]).astimezone(MOSCOW_TZ)

                # Если время пришло
                if current_time >= next_backup:
                    file_path = file["path"]
                    filename = file["filename"]

                    if os.path.exists(file_path):
                        # Создаем папку для бэкапа
                        backup_date = current_time.strftime("%Y-%m-%d")
                        backup_dir = f"backups/{backup_date}"
                        os.makedirs(backup_dir, exist_ok=True)

                        # Копируем файл
                        timestamp = current_time.strftime("%H-%M-%S")
                        original_name = os.path.splitext(filename)[0]
                        extension = os.path.splitext(filename)[1]
                        backup_name = f"{original_name}_{timestamp}{extension}"
                        dst = f"{backup_dir}/{backup_name}"
                        shutil.copy2(file_path, dst)

                        # Обновляем статистику
                        file["last_backup"] = current_time.isoformat()
                        file["backup_count"] = file.get("backup_count", 0) + 1

                        # Добавляем в историю
                        if "backups_history" not in file:
                            file["backups_history"] = []

                        file["backups_history"].append({
                            "time": current_time.isoformat(),
                            "filename": backup_name,
                            "date": backup_date
                        })

                        # Обновляем следующее время бэкапа
                        period_value = file.get("period_value", 1)
                        period_unit = file.get("period_unit", "hours")

                        if period_unit == "seconds":
                            next_time = current_time + timedelta(seconds=period_value)
                        elif period_unit == "minutes":
                            next_time = current_time + timedelta(minutes=period_value)
                        elif period_unit == "hours":
                            next_time = current_time + timedelta(hours=period_value)
                        elif period_unit == "days":
                            next_time = current_time + timedelta(days=period_value)
                        else:
                            next_time = current_time + timedelta(hours=1)

                        file["next_backup"] = next_time.isoformat()

                        log_message(f"✅ Создан бэкап: {filename}")
                        updated = True
                    else:
                        log_message(f"⚠️ Файл не найден: {filename}")

            except Exception as e:
                log_message(f"❌ Ошибка обработки файла {file.get('filename', 'unknown')}: {e}")
                continue

        if updated:
            with open("data/files.json", "w", encoding="utf-8") as f:
                json.dump(files, f, indent=2, ensure_ascii=False)

    except Exception as e:
        log_message(f"❌ Ошибка проверки бэкапов: {e}")


def main():
    log_message("🚀 Worker запущен")

    # Проверяем каждые 10 секунд (чаще для точности)
    schedule.every(10).seconds.do(check_backups)

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)  # Проверяем планировщик каждую секунду
        except Exception as e:
            log_message(f"❌ Ошибка в главном цикле: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()