import os
import json
import random
import time
import logging

logger = logging.getLogger(__name__)

from flask import flash, session

from app import cache, celery

from ipapi.base.pipeline_processor import PipelineProcessor
from ipapi.base.ipt_loose_pipeline import LoosePipeline


def get_user_path(user_name: str, key: str):
    return {
        "launch_conf": os.path.join(
            ".", "generated_files", f"{user_name}_launch_conf.json"
        ),
        "abort_touch": os.path.join(".", "generated_files", f".{user_name}_abort"),
        "analysis_folder": os.path.join(
            ".", "generated_files", f"{user_name}_analysis", ""
        ),
    }.get(key, "")


@cache.memoize(timeout=180)
def get_source_configuration(url: str):
    if not url or not os.path.isfile(url):
        return None
    with open(url, "r") as f:
        data = json.load(f)
    if "script" in data:
        if not "build_annotation_csv" in data:
            data["build_annotation_csv"] = False
        data["standalone"] = True
        return data
    elif "Pipeline" in data:
        return dict(
            csv_file_name="data.csv",
            overwrite_existing=False,
            script=data,
            generate_series_id=False,
            series_id_time_delta=0,
            thread_count=1,
            build_annotation_csv=False,
            standalone=False,
            images=[],
        )
    else:
        return None


def get_launch_config_path(user_name: str) -> str:
    return get_user_path(user_name=user_name, key="launch_conf")


def get_abort_file_path(user_name: str) -> str:
    return get_user_path(user_name=user_name, key="abort_touch")


def get_launch_configuration(user_name: str):
    launch_conf_path = get_launch_config_path(user_name=user_name)
    if os.path.isfile(launch_conf_path):
        try:
            with open(launch_conf_path, "r") as f:
                return json.load(f)
        except Exception as e:
            flash(repr(e), category="error")
            logger.exception(repr(e))
    else:
        return {}


def set_launch_configuration(user_name: str, data: dict, **kwargs):
    data["csv_file_name"] = kwargs.get("csv_file_name")
    data["overwrite_existing"] = kwargs.get("overwrite_existing")
    data["generate_series_id"] = kwargs.get("generate_series_id")
    data["series_id_time_delta"] = kwargs.get("series_id_time_delta")
    data["thread_count"] = kwargs.get("thread_count")
    data["build_annotation_csv"] = kwargs.get("build_annotation_csv")
    data["images"] = kwargs.get("images")
    data["current_user"] = kwargs.get("current_user")
    launch_conf_path = get_launch_config_path(user_name=user_name)
    if os.path.isfile(launch_conf_path):
        os.remove(launch_conf_path)
    with open(launch_conf_path, "w") as f:
        json.dump(data, f, indent=2)


@celery.task(bind=True)
def long_task(self, **kwargs):
    def progress_callback(error_level, message, step, total):
        self.update_state(
            state="PROGRESS",
            meta={
                "current": step,
                "total": total,
                "status": message,
            },
        )

    pp = PipelineProcessor(
        dst_path=get_user_path(user_name=kwargs["current_user"], key="analysis_folder"),
        overwrite=kwargs["overwrite_existing"],
        seed_output=False,
        group_by_series=kwargs["generate_series_id"],
        store_images=False,
    )
    pp.progress_and_log_callback = progress_callback
    pp.ensure_root_output_folder()
    pp.accepted_files = kwargs.get("images", [])
    pp.script = LoosePipeline.from_json(json_data=kwargs["script"])
    if not pp.accepted_files:
        return {
            "current": 100,
            "total": 100,
            "status": "No images in task!",
            "result": 42,
        }

    total = len(images)
    for i, image in enumerate(images):
        time.sleep(random.random())
        self.update_state(
            state="PROGRESS",
            meta={
                "current": i,
                "total": total,
                "status": image,
            },
        )
        if os.path.isfile(get_abort_file_path(kwargs["current_user"])):
            return {"current": 100, "total": 100, "status": "Task aborted!", "result": 42}
    return {"current": 100, "total": 100, "status": "Task completed!", "result": 42}


def get_process_info(data: dict) -> dict:
    return {
        "pipeline_title": data.get("script", {}).get("title", ""),
        "pipeline_desc": data.get("script", {}).get("description", ""),
        "csv_file_name": data.get("csv_file_name", ""),
        "overwrite_existing": data.get("overwrite_existing", ""),
        "generate_series_id": data.get("generate_series_id", ""),
        "series_id_time_delta": data.get("series_id_time_delta", ""),
        "thread_count": data.get("thread_count", ""),
        "build_annotation_csv": data.get("build_annotation_csv", ""),
        "images": len(data.get("images", [])),
    }
