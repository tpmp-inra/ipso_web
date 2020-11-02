import os
import json
import logging

import pandas as pd

import plotly.express as px

logger = logging.getLogger(__name__)

from flask import flash

from app import cache, celery

import pandas as pd

from ipapi.base.pipeline_processor import PipelineProcessor
from ipapi.base.ipt_loose_pipeline import LoosePipeline
from ipapi.file_handlers.fh_base import file_handler_factory
from ipapi.database.base import DbInfo
from ipapi.database.db_factory import db_info_to_database


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
    if "Pipeline" in data:
        return dict(
            csv_file_name="data.csv",
            overwrite_existing=False,
            script=data,
            generate_series_id=False,
            series_id_time_delta=0,
            thread_count=1,
            build_annotation_csv=False,
            sub_folder_name="",
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
    data["current_user"] = kwargs.get("current_user")
    data["database_info"] = kwargs.get("database_info")
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
    dbi = DbInfo.from_json(
        json_data=json.loads(kwargs["database_info"].replace("'", '"'))
    )
    pp = PipelineProcessor(
        dst_path=output_folder,
        overwrite=kwargs["overwrite_existing"],
        seed_output=False,
        group_by_series=kwargs["generate_series_id"],
        store_images=False,
        database=db_info_to_database(dbi),
    )
    pp.progress_callback = progress_callback
    pp.abort_callback = abort_callback
    pp.ensure_root_output_folder()
    pp.grab_files_from_data_base(experiment=dbi.display_name.lower())
    pp.script = LoosePipeline.from_json(json_data=kwargs["script"])
    if not pp.accepted_files:
        return {
            "current": 100,
            "total": 100,
            "status": "No images in task!",
            "result": 42,
        }

    try:
        pp.multi_thread = int(kwargs.get("thread_count", 1))
    except:
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
    dbi = DbInfo.from_json(json_data=json.loads(data["database_info"].replace("'", '"')))
    tmp_db = db_info_to_database(dbi)
    tmp_db.connect()
    count, desc_lines, fig = get_experiment_digest(tmp_db.dataframe)
    return {
        "pipeline_title": data.get("script", {}).get("title", ""),
        "pipeline_desc": data.get("script", {}).get("description", ""),
        "csv_file_name": data.get("csv_file_name", ""),
        "overwrite_existing": data.get("overwrite_existing", ""),
        "generate_series_id": data.get("generate_series_id", ""),
        "series_id_time_delta": data.get("series_id_time_delta", ""),
        "thread_count": data.get("thread_count", ""),
        "build_annotation_csv": data.get("build_annotation_csv", ""),
        "experiment": dbi.display_name,
        "obs_count": count,
        "desc_lines": desc_lines,
        "fig": fig,
    }


def get_experiment_digest(experiment: pd.DataFrame):
    df = experiment.copy()

    if df.shape[0] > 0:
        temp_date_time = pd.DatetimeIndex(df["date_time"])
        df.insert(loc=4, column="time", value=temp_date_time.time)
        df.insert(loc=4, column="date", value=temp_date_time.date)

        df["hour"] = pd.to_numeric(
            df.time.astype("str").str.split(pat=":", expand=True).iloc[:, 0]
        ).to_list()

        count = df.shape[0]

        desc_lines = {
            f"{col.replace('_', ' ').capitalize()}s": f"{len(list(df[col].unique()))} unique"
            for col in ["Plant", "date", "Camera", "view_option"]
        }

        fig = px.density_heatmap(
            title="Observations per day and hour",
            data_frame=df,
            x="date",
            y="hour",
            height=400,
        )
        fig.update_yaxes(tick0=-0.5)
    else:
        count = 0
        desc_lines = {col: "None" for col in ["plant", "date", "camera", "view_option"]}
        fig = None

    return count, desc_lines, fig
