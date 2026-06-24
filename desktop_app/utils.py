import os
import sys
import subprocess
import json
import base64
import time
from PIL import Image, PngImagePlugin, ImageOps


# =========================================================================
#  系统与通用工具
# =========================================================================

def open_file_system(path):
    """打开文件或系统默认看图软件"""
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])


def open_folder_select(path):
    """打开文件夹并高亮选中文件"""
    if sys.platform == "win32":
        subprocess.call(f'explorer /select,"{os.path.normpath(path)}"')
    elif sys.platform == "darwin":
        subprocess.call(["open", "-R", path])
    else:
        subprocess.call(["xdg-open", os.path.dirname(path)])


def compress_image_smart(input_path, target_mb, output_path):
    """智能压缩图片到目标大小以下"""
    target_bytes = target_mb * 1024 * 1024
    if os.path.getsize(input_path) <= target_bytes:
        if input_path != output_path:
            import shutil
            shutil.copy2(input_path, output_path)
        return output_path

    img = Image.open(input_path)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    quality = 95
    while quality > 10:
        img.save(output_path, "JPEG", quality=quality)
        if os.path.getsize(output_path) <= target_bytes:
            break
        quality -= 5
    return output_path


# =========================================================================
#  多图拼合与隐写术 (Smart PNG) 核心算法
# =========================================================================

def compose_images_hero(image_paths, target_size=(2048, 2048), bg_color=(255, 255, 255)):
    """【电商视觉模式】: 1大 (左) + N小 (右)"""
    if not image_paths: return None
    canvas = Image.new("RGB", target_size, bg_color)

    if len(image_paths) == 1:
        img = Image.open(image_paths[0]).convert("RGB")
        img = ImageOps.pad(img, target_size, color=bg_color)
        canvas.paste(img, (0, 0))
        return canvas

    # 主图占左半边
    hero_img = Image.open(image_paths[0]).convert("RGB")
    hero_box = (target_size[0] // 2, target_size[1])
    hero_img = ImageOps.pad(hero_img, hero_box, color=bg_color)
    canvas.paste(hero_img, (0, 0))

    # 细节图占右半边
    details = image_paths[1:4]
    num_details = len(details)
    detail_h = target_size[1] // num_details
    detail_box = (target_size[0] // 2, detail_h)

    for i, path in enumerate(details):
        det_img = Image.open(path).convert("RGB")
        det_img = ImageOps.pad(det_img, detail_box, color=bg_color)
        canvas.paste(det_img, (target_size[0] // 2, i * detail_h))

    return canvas


def compose_images_grid(image_paths, target_size=(2048, 2048), bg_color=(255, 255, 255)):
    """【AI 参考模式】: 严格无缝网格 (1x2, 1x3, 2x2)"""
    if not image_paths: return None
    canvas = Image.new("RGB", target_size, bg_color)
    count = min(len(image_paths), 4)

    if count == 1:
        img = Image.open(image_paths[0]).convert("RGB")
        img = ImageOps.pad(img, target_size, color=bg_color)
        canvas.paste(img, (0, 0))
    elif count == 2:
        box = (target_size[0] // 2, target_size[1])
        for i in range(2):
            img = ImageOps.pad(Image.open(image_paths[i]).convert("RGB"), box, color=bg_color)
            canvas.paste(img, (i * box[0], 0))
    elif count == 3:
        box = (target_size[0] // 3, target_size[1])
        for i in range(3):
            img = ImageOps.pad(Image.open(image_paths[i]).convert("RGB"), box, color=bg_color)
            canvas.paste(img, (i * box[0], 0))
    else:
        box = (target_size[0] // 2, target_size[1] // 2)
        positions = [(0, 0), (box[0], 0), (0, box[1]), (box[0], box[1])]
        for i in range(4):
            img = ImageOps.pad(Image.open(image_paths[i]).convert("RGB"), box, color=bg_color)
            canvas.paste(img, positions[i])

    return canvas


def save_smart_png(composed_pil, original_paths, output_path):
    """将多张高清原图转化为 Base64，作为隐形元数据注入 PNG"""
    metadata = PngImagePlugin.PngInfo()
    b64_list = []
    for path in original_paths:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            b64_list.append(b64)

    metadata.add_text("smart_ecommerce_data", json.dumps(b64_list))
    composed_pil.save(output_path, "PNG", pnginfo=metadata)
    return output_path


def extract_smart_png(image_path, temp_output_dir):
    """解包魔法图，还原高清数组"""
    try:
        img = Image.open(image_path)
        if "smart_ecommerce_data" in img.info:
            b64_list = json.loads(img.info["smart_ecommerce_data"])
            if not os.path.exists(temp_output_dir):
                os.makedirs(temp_output_dir)

            extracted_paths = []
            for i, b64 in enumerate(b64_list):
                out_p = os.path.join(temp_output_dir, f"unpacked_{int(time.time())}_{i}.png")
                with open(out_p, "wb") as f:
                    f.write(base64.b64decode(b64))
                extracted_paths.append(out_p)
            return extracted_paths
    except Exception as e:
        print(f"提取智能图片失败: {e}")
    return None