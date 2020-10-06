import os
import json
import logging

logger = logging.getLogger(__name__)

from flask import flash

from app import cache, celery

import pandas as pd

from ipapi.base.pipeline_processor import PipelineProcessor
from ipapi.base.ipt_loose_pipeline import LoosePipeline
from ipapi.file_handlers.fh_base import file_handler_factory


IS_USE_MULTI_THREAD = False


def get_user_path(user_name: str, key: str, extra: str = ""):
    return {
        "launch_conf": os.path.join(
            ".",
            "generated_files",
            f"{user_name}_launch_conf.json",
        ),
        "abort_touch": os.path.join(
            ".",
            "generated_files",
            f".{user_name}_abort",
        ),
        "analysis_folder": os.path.join(
            ".",
            "generated_files",
            f"{user_name}_analysis_{extra}",
            "",
        ),
        "src_image_folder": os.path.join(
            ".",
            "generated_files",
            f"{user_name}_analysis_{extra}",
            "src_images",
            "",
        ),
    }.get(key, "")


@cache.memoize(timeout=180)
def get_source_configuration(url: str):
    if not url or not os.path.isfile(url):
        return None
    with open(url, "r") as f:
        data = json.load(f)
    if "script" in data:  # All required data is present
        if not "build_annotation_csv" in data:
            data["build_annotation_csv"] = False
        data["standalone"] = True
        return data
    elif "Pipeline" in data:  # Additional data is required
        return dict(
            csv_file_name="data.csv",
            overwrite_existing=False,
            script=data,
            generate_series_id=False,
            series_id_time_delta=0,
            thread_count=1,
            build_annotation_csv=False,
            standalone=False,
            sub_folder_name="",
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


def prepare_process_muncher(progress_callback, abort_callback, **kwargs):
    output_folder = get_user_path(
        user_name=kwargs["current_user"],
        key="analysis_folder",
        extra=kwargs["sub_folder_name"],
    )
    pp = PipelineProcessor(
        dst_path=output_folder,
        overwrite=kwargs["overwrite_existing"],
        seed_output=False,
        group_by_series=kwargs["generate_series_id"],
        store_images=False,
    )
    pp.progress_callback = progress_callback
    pp.abort_callback = abort_callback
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

    if IS_USE_MULTI_THREAD and "thread_count" in kwargs:
        try:
            pp.multi_thread = int(kwargs["thread_count"])
        except:
            pp.multi_thread = False
    else:
        pp.multi_thread = False

    return {
        "pipeline_processor": pp,
        "output_folder": output_folder,
    }


def generate_annotation_csv(
    pipeline_processor,
    groups_to_process,
    output_folder,
    di_filename,
):

    try:
        if pipeline_processor.options.group_by_series:
            files, luids = map(list, zip(*groups_to_process))
            wrappers = [
                file_handler_factory(files[i])
                for i in [luids.index(x) for x in set(luids)]
            ]
        else:
            wrappers = [file_handler_factory(f) for f in groups_to_process]
        pd.DataFrame.from_dict(
            {
                "plant": [i.plant for i in wrappers],
                "date_time": [i.date_time for i in wrappers],
                "disease_index": "",
            }
        ).sort_values(
            by=["plant", "date_time"],
            axis=0,
            na_position="first",
            ascending=True,
        ).to_csv(
            di_filename,
            index=False,
        )
    except Exception as e:
        logger.exception(f"Unable to build disease index file")
    else:
        logger.info("Built disease index file")


@celery.task(bind=True)
def long_task(self, **kwargs):
    def progress_callback(step, total):
        self.update_state(
            state="PROGRESS",
            meta={
                "current": step,
                "total": total,
                "status": "Analysing images...",
            },
        )

    def abort_callback():
        return os.path.isfile(get_abort_file_path(kwargs["current_user"]))

    data = prepare_process_muncher(progress_callback, abort_callback, **kwargs)

    pp = data["pipeline_processor"]
    output_folder = data["output_folder"]
    groups_to_process = pp.prepare_groups(kwargs["series_id_time_delta"])

    # Generate annotation CSV
    if kwargs["build_annotation_csv"]:
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": "Building annotation CSV file...",
            },
        )
        generate_annotation_csv(
            pipeline_processor=pp,
            groups_to_process=groups_to_process,
            output_folder=output_folder,
            di_filename=os.path.join(
                output_folder,
                f"{kwargs['csv_file_name']}_diseaseindex.csv",
            ),
        )
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": "Building annotation CSV file... Done",
            },
        )

    groups_to_process_count = len(groups_to_process)
    if groups_to_process_count > 0:
        pp.process_groups(groups_list=groups_to_process)

    if os.path.isfile(get_abort_file_path(kwargs["current_user"])):
        return {"current": 100, "total": 100, "status": "Task aborted!", "result": 42}

    # Merge dataframe
    pp.merge_result_files(csv_file_name=kwargs["csv_file_name"] + ".csv")

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
