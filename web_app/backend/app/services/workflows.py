from __future__ import annotations

import os
import uuid

import config
import utils
from core import api_client

from .prompt_builders import build_face_swap_prompt, build_replacement_prompt
from .history_service import write_result_metadata
from .request_parsers import WebGenerationSettings


def _runtime_dir(settings: WebGenerationSettings) -> str:
    path = os.path.join(config.DEFAULT_OUTPUT_DIR, "web_runtime", "sessions", settings.session_id, "runs", uuid.uuid4().hex[:12])
    os.makedirs(path, exist_ok=True)
    return path


def _ensure_subdir(runtime_dir: str, name: str) -> str:
    path = os.path.join(runtime_dir, name)
    os.makedirs(path, exist_ok=True)
    return path


def _validate_image_count(image_count: int, model_name: str) -> None:
    model_config = config.IMAGE_MODELS.get(model_name, {})
    max_input_images = model_config.get("max_input_images")
    if max_input_images and image_count > int(max_input_images):
        raise ValueError(f"{model_name} 最多支持 {max_input_images} 张输入图，当前请求共 {image_count} 张。")


def _public_result(path: str, title: str, prompt: str, source_name: str = "") -> dict:
    runtime_base = os.path.join(config.DEFAULT_OUTPUT_DIR, "web_runtime")
    relative_path = os.path.relpath(path, runtime_base).replace("\\", "/")
    write_result_metadata(path, title, prompt, source_name)
    return {
        "title": title,
        "prompt": prompt,
        "path": path,
        "url": f"/generated/{relative_path}",
        "source_name": source_name,
        "file_name": os.path.basename(path),
    }


def _prepare_scene_source(image_path: str, runtime_dir: str) -> str | list[str]:
    smart_png_dir = _ensure_subdir(runtime_dir, "smart_png")
    extracted = utils.extract_smart_png(image_path, smart_png_dir)
    return extracted if extracted else image_path


def analyze_style_web(settings: WebGenerationSettings, source_image_path: str, style_names: list[str]) -> dict:
    if not settings.llm_key.strip():
        raise ValueError("缺少默认语言模型 Key，请先在 data/config.json 中配置 llm_key。")
    return api_client.api_analyze_style(settings.llm_key.strip(), source_image_path, style_names)


def generate_scene_prompts_web(settings: WebGenerationSettings, source_image_path: str, payload: dict) -> list[str]:
    if not settings.llm_key.strip():
        raise ValueError("缺少默认语言模型 Key，请先在 data/config.json 中配置 llm_key。")
    return api_client.api_generate_prompts(
        settings.llm_key.strip(),
        source_image_path,
        payload["template_name"],
        payload["raw_template"],
        payload["style_name"],
        payload["style_desc"],
        payload["extra_info"],
    )


def generate_scene_images_web(
    settings: WebGenerationSettings,
    source_image_path: str,
    prompts: list[str],
) -> list[dict]:
    clean_prompts = [item.strip() for item in prompts if item and item.strip()]
    if not clean_prompts:
        raise ValueError("请先提供至少一条 Prompt。")

    runtime_dir = _runtime_dir(settings)
    output_dir = _ensure_subdir(runtime_dir, "scene_results")
    source_input = _prepare_scene_source(source_image_path, runtime_dir)
    results: list[dict] = []

    for index, prompt in enumerate(clean_prompts, start=1):
        image_path = api_client.api_generate_image(
            prompt=prompt,
            key=settings.effective_image_key,
            ratio=settings.ratio_value,
            source_img_path=source_input,
            save_directory=output_dir,
            file_prefix=f"scene_{index}",
            compress_enabled=settings.compress_enabled,
            compress_target=settings.compress_target,
            image_size=settings.image_resolution,
            api_url=settings.model_config,
        )
        results.append(_public_result(image_path, f"场景图 {index}", prompt))

    return results


def run_product_replacement_web(
    settings: WebGenerationSettings,
    scene_paths: list[str],
    product_reference_paths: list[str],
    manual_text: str,
) -> list[dict]:
    if not scene_paths:
        raise ValueError("请先上传模特图或场景图。")
    if not product_reference_paths:
        raise ValueError("请先上传产品参考图。")

    _validate_image_count(1 + len(product_reference_paths), settings.image_model)
    runtime_dir = _runtime_dir(settings)
    output_dir = _ensure_subdir(runtime_dir, "replacement_results")
    prompt = build_replacement_prompt(manual_text)
    results: list[dict] = []

    for index, scene_path in enumerate(scene_paths, start=1):
        image_path = api_client.api_generate_image(
            prompt=prompt,
            key=settings.effective_image_key,
            ratio=settings.ratio_value,
            source_img_path=[scene_path, *product_reference_paths],
            save_directory=output_dir,
            file_prefix=f"replacement_{index}",
            compress_enabled=settings.compress_enabled,
            compress_target=settings.compress_target,
            image_size=settings.image_resolution,
            api_url=settings.model_config,
        )
        results.append(_public_result(image_path, f"爆款替换 {index}", prompt, os.path.basename(scene_path)))

    return results


def run_multi_reference_generation_web(
    settings: WebGenerationSettings,
    reference_paths: list[str],
    prompt: str,
) -> dict:
    if not prompt.strip():
        raise ValueError("请输入提示词。")

    supports_text_only = bool(settings.model_config.get("supports_text_only_generation", False))
    if not reference_paths and not supports_text_only:
        raise ValueError(f"{settings.image_model} 需要至少上传 1 张参考图。")

    _validate_image_count(len(reference_paths), settings.image_model)
    runtime_dir = _runtime_dir(settings)
    output_dir = _ensure_subdir(runtime_dir, "multi_reference_results")
    source_input = reference_paths if reference_paths else None
    image_path = api_client.api_generate_image(
        prompt=prompt,
        key=settings.effective_image_key,
        ratio=settings.ratio_value,
        source_img_path=source_input,
        save_directory=output_dir,
        file_prefix="multi_reference",
        compress_enabled=settings.compress_enabled,
        compress_target=settings.compress_target,
        image_size=settings.image_resolution,
        api_url=settings.model_config,
    )
    return _public_result(image_path, "多参考图结果", prompt)


def run_face_swap_generation_web(
    settings: WebGenerationSettings,
    target_paths: list[str],
    head_reference_paths: list[str],
    accessory_paths: list[str],
    manual_text: str,
) -> list[dict]:
    if not target_paths:
        raise ValueError("请先上传模特图。")
    if not head_reference_paths:
        raise ValueError("请先上传头部参考图。")

    _validate_image_count(1 + len(head_reference_paths) + len(accessory_paths), settings.image_model)
    runtime_dir = _runtime_dir(settings)
    output_dir = _ensure_subdir(runtime_dir, "face_swap_results")
    prompt = build_face_swap_prompt(len(head_reference_paths), len(accessory_paths), manual_text)
    results: list[dict] = []

    for index, target_path in enumerate(target_paths, start=1):
        image_path = api_client.api_generate_image(
            prompt=prompt,
            key=settings.effective_image_key,
            ratio=settings.ratio_value,
            source_img_path=[target_path, *head_reference_paths, *accessory_paths],
            save_directory=output_dir,
            file_prefix=f"face_swap_{index}",
            compress_enabled=settings.compress_enabled,
            compress_target=settings.compress_target,
            image_size=settings.image_resolution,
            api_url=settings.model_config,
        )
        results.append(_public_result(image_path, f"换脸结果 {index}", prompt, os.path.basename(target_path)))

    return results
