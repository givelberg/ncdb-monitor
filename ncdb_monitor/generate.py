import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

import os
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from datetime import datetime, time
import re
import json
from ncdb.api.database import Database
from ncdb_monitor.config import WEBSITE_DATA_FILE


def safe_name(name: str) -> str:
    """
    Convert a variable/obsspace name into a filesystem-safe filename.
    Example: "ObsValue/seaSurfaceTemperature" -> "ObsValue_seaSurfaceTemperature"
    """
    # replace path separators and spaces
    name = name.replace("/", "_").replace(" ", "_")

    # remove anything that is not alphanumeric, underscore, dot, or dash
    name = re.sub(r"[^a-zA-Z0-9_.-]", "", name)

    # collapse repeated underscores
    name = re.sub(r"_+", "_", name)

    return name.strip("_")


def load_latest_run(website_dir):

    runs_dir = Path(website_dir) / "runs"

    if not runs_dir.exists():
        return None

    run_files = sorted(runs_dir.glob("*.json"))

    if not run_files:
        return None

    with open(run_files[-1]) as f:
        return json.load(f)


def get_preview_variable(obsspace, obsspace_info):
    for var in obsspace_info["variables"]:
        if "nobs" in var["metrics"]:
            return var
    return None


def generate_time_series_plots(
    obsspace,
    metric_name,
    plot_dir
):

    plots = []

    obsspace_name = obsspace.name

    variables = obsspace.list_variables(
        group="ObsValue"
    )

    for var in variables:

        try:

            field = obsspace.field(var)

            metric = getattr(
                field,
                metric_name
            )

        except Exception as e:

            logger.debug(
                f"Skipping "
                f"{obsspace_name}:{var} "
                f"metric={metric_name} "
                f"due to {e}"
            )

            continue

        out_file = (
            safe_name(var)
            + ".png"
        )

        plot_path = os.path.join(
            plot_dir,
            out_file
        )

        logger.info(
            f"Generating "
            f"{metric_name} plot "
            f"{plot_path}"
        )

        try:

            metric.plot(plot_path)

        except Exception as e:

            logger.debug(
                f"Failed plotting "
                f"{obsspace_name}:{var} "
                f"metric={metric_name} "
                f"due to {e}"
            )

            continue

        plots.append({

            "variable": var,

            "path": out_file
        })

    return plots

def generate_snapshot_plots(
    field,
    plot_dir,
    n_latest_cycles=4
):

    plots = []

    try:

        cycles = field.cycles()

    except Exception as e:

        logger.debug(
            f"Could not get cycles "
            f"due to {e}"
        )

        return plots

    latest_cycles = cycles[-n_latest_cycles:]

    for t in latest_cycles:

        try:

            value = field[t]

        except Exception as e:

            logger.debug(
                f"Skipping snapshot "
                f"time={t} "
                f"due to {e}"
            )

            continue

        cycle_string = (
            t.strftime("%Y%m%d%H")
        )

        out_file = (
            safe_name(
                cycle_string
            )
            + ".png"
        )

        plot_path = os.path.join(
            plot_dir,
            out_file
        )

        logger.info(
            f"Generating snapshot "
            f"{plot_path}"
        )

        try:

            value.plot(plot_path)

        except Exception as e:

            logger.debug(
                f"Failed plotting "
                f"time={t} "
                f"due to {e}"
            )

            continue

        plots.append({

            "cycle": (
                t.strftime(
                    "%Y-%m-%d %H:%M"
                )
            ),

            "path": out_file
        })

    return plots

def generate_obsspace_data(
    dataset_name,
    obsspace,
    dataset_dir,
    metric_names
):

    obsspace_name = obsspace.name

    logger.info(
        f"Processing obsspace "
        f"{obsspace_name}"
    )

    obsspace_safe_name = safe_name(
        obsspace_name
    )

    obsspace_dir = os.path.join(
        dataset_dir,
        obsspace_safe_name
    )

    os.makedirs(
        obsspace_dir,
        exist_ok=True
    )

    obsspace_info = {
        "name": obsspace_name,
        "safe_name": obsspace_safe_name,
        "variables": []
    }

    #
    # generate all time-series plots
    #

    metric_plots = {}

    for metric_name in metric_names:

        metric_dir = os.path.join(
            obsspace_dir,
            metric_name
        )

        os.makedirs(
            metric_dir,
            exist_ok=True
        )

        metric_plots[metric_name] = (
            generate_time_series_plots(
                obsspace,
                metric_name,
                metric_dir
            )
        )

    #
    # per-variable organization
    #

    variables = obsspace.list_variables(
        group="ObsValue"
    )

    for var in variables:

        logger.info(
            f"Processing variable "
            f"{obsspace_name}:{var}"
        )

        variable_info = {

            "name": var,

            "metrics": {},

            "snapshots": []
        }

        #
        # attach metric plots
        #

        for metric_name in metric_names:

            for plot in metric_plots[
                metric_name
            ]:

                if plot["variable"] != var:
                    continue

                variable_info["metrics"][
                    metric_name
                ] = {

                    "path": (
                        f"{dataset_name}/"
                        f"{obsspace_safe_name}/"
                        f"{metric_name}/"
                        f"{plot['path']}"
                    ),

                    "local_path": (
                        f"{metric_name}/"
                        f"{plot['path']}"
                    )
                }

        #
        # generate snapshot plots
        #

        try:

            field = obsspace.field(var)

        except Exception as e:

            logger.debug(
                f"Skipping field "
                f"{obsspace_name}:{var} "
                f"due to {e}"
            )

            continue

        snapshots_dir = os.path.join(
            obsspace_dir,
            "snapshots",
            safe_name(var)
        )

        os.makedirs(
            snapshots_dir,
            exist_ok=True
        )

        snapshot_plots = (
            generate_snapshot_plots(
                field,
                snapshots_dir
            )
        )

        for plot in snapshot_plots:

            variable_info[
                "snapshots"
            ].append({

                "cycle": plot["cycle"],

                "path": (
                    f"{dataset_name}/"
                    f"{obsspace_safe_name}/"
                    f"snapshots/"
                    f"{safe_name(var)}/"
                    f"{plot['path']}"
                ),

                "local_path": (
                    f"snapshots/"
                    f"{safe_name(var)}/"
                    f"{plot['path']}"
                )
            })

        obsspace_info[
            "variables"
        ].append(variable_info)

    preview_var = get_preview_variable(obsspace, obsspace_info)
    obsspace_info["preview_variable"] = preview_var

    return obsspace_info


def generate_website_data(db, website_dir):

    website_data = {
        "meta": {
            "generated_at": (
                datetime.utcnow()
                .strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
            ),
            "database_file": str(db.path),
        },

        "run": load_latest_run(website_dir),

        "datasets": []
    }

    metric_names = [
        "nobs",
        "mean",
    ]

    for dataset in db.datasets():

        dataset_name = dataset.name

        logger.info(
            f"Processing dataset "
            f"{dataset_name}"
        )

        dataset_dir = os.path.join(
            website_dir,
            dataset_name
        )

        os.makedirs(
            dataset_dir,
            exist_ok=True
        )

        dataset_info = {
            "name": dataset_name,
            "root_dir": dataset.root_dir,
            "obsspaces": []
        }

        for obsspace_name in dataset.list_obsspaces():

            obsspace = dataset.obsspace(
                obsspace_name
            )

            obsspace_info = (
                generate_obsspace_data(
                    dataset_name,
                    obsspace,
                    dataset_dir,
                    metric_names
                )
            )

            dataset_info[
                "obsspaces"
            ].append(obsspace_info)

        website_data[
            "datasets"
        ].append(dataset_info)

    website_data_file = os.path.join(
        website_dir,
        WEBSITE_DATA_FILE
    )

    with open(website_data_file, "w") as f:

        json.dump(
            website_data,
            f,
            indent=2
        )

##########################################################


def main():
    db = Database("emcda.db")
    logger.info(db.list_datasets())

    generate_website_data(db)
    generate_html(
        website_data,
        website_dir
    )

if __name__ == "__main__":
    main()
