import json
import os

from config import log_to_file


def load_json_data(filepath, default_data):
    try:
        if not os.path.exists(filepath):
            # 如果文件不存在，自动创建默认文件
            save_json_data(filepath, default_data)
            return default_data
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log_to_file(f"Load JSON Warning ({filepath}): {e}", "WARNING")
        return default_data


def save_json_data(filepath, data):
    try:
        # 确保目录存在
        directory = os.path.dirname(filepath)
        if not os.path.exists(directory):
            os.makedirs(directory)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        log_to_file(f"Save JSON Error ({filepath}): {e}", "ERROR")


def calculate_total_success(history_data):
    c = 0
    for r in history_data:
        for i in r.get("items", []):
            if i.get("status") == "success": c += 1
    return c