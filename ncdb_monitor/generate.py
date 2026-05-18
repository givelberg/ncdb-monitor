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


def generate_time_series_plots(
    dataset,
    metric_name,
    plot_dir
):

    plots = []

    for obsspace_name in dataset.list_obsspaces():

        obsspace = dataset.obsspace(obsspace_name)

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
                safe_name(
                    f"{obsspace_name}_{var}"
                )
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

            metric.plot(plot_path)

            plots.append({
                "name": f"{obsspace_name}:{var}",
                "path": out_file,
            })

    return plots

def old_generate_nobs_plots(dataset, plot_dir):

    plots = []

    for obsspace_name in dataset.list_obsspaces():

        obsspace = dataset.obsspace(obsspace_name)

        variables = obsspace.list_variables(
            group="ObsValue"
        )

        for var in variables:

            try:
                field = obsspace.field(var)
                nobs = field.nobs

            except Exception as e:

                logger.debug(
                    f"Skipping {obsspace_name}:{var} "
                    f"due to {e}"
                )

                continue

            out_file = (
                safe_name(
                    f"{obsspace_name}_{var}"
                )
                + ".png"
            )

            plot_path = os.path.join(
                plot_dir,
                out_file
            )

            logger.info(
                f"Generating plot {plot_path}"
            )

            nobs.plot(plot_path)

            plots.append({
                "name": f"{obsspace_name}:{var}",
                "path": out_file,
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
            "metrics": {}
        }

        try:

            field = obsspace.field(var)

        except Exception as e:

            logger.debug(
                f"Skipping field "
                f"{obsspace_name}:{var} "
                f"due to {e}"
            )

            continue

        for metric_name in metric_names:

            try:

                metric = getattr(
                    field,
                    metric_name
                )

            except Exception as e:

                logger.debug(
                    f"Skipping metric "
                    f"{metric_name} "
                    f"for "
                    f"{obsspace_name}:{var} "
                    f"due to {e}"
                )

                continue

            metric_dir = os.path.join(
                obsspace_dir,
                metric_name
            )

            os.makedirs(
                metric_dir,
                exist_ok=True
            )

            out_file = (
                safe_name(var)
                + ".png"
            )

            plot_path = os.path.join(
                metric_dir,
                out_file
            )

            logger.info(
                f"Generating "
                f"{metric_name} plot "
                f"{plot_path}"
            )

            metric.plot(plot_path)

            variable_info["metrics"][
                metric_name
            ] = {
                "path": (
                    f"{dataset_name}/"
                    f"{obsspace_safe_name}/"
                    f"{metric_name}/"
                    f"{out_file}"
                ),

                "local_path": (
                    f"{metric_name}/"
                    f"{out_file}"
                )
            }

        obsspace_info[
            "variables"
        ].append(variable_info)

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
            "database_file": str(db.db_path),
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


def old_generate_website_data(db, website_dir):

    website_data = {
        "datasets": []
    }

    for dataset in db.datasets():
        dataset_name = dataset.name

        logger.info(f"Processing dataset {dataset_name}")

        # dataset = db.dataset(dataset_name)

        dataset_dir = os.path.join(
            website_dir,
            dataset_name
        )

        os.makedirs(dataset_dir, exist_ok=True)

        metrics = {}

        for metric_name in ["nobs", "mean"]:

            metric_dir = os.path.join(
                dataset_dir,
                metric_name
            )

            os.makedirs(
                metric_dir,
                exist_ok=True
            )

            metrics[metric_name] = (
                generate_time_series_plots(
                    dataset,
                    metric_name,
                    metric_dir
                )
            )

        dataset_info = {
            "name": dataset_name,
            "metrics": metrics,
        }

        # nobs_plot_dir = os.path.join(
            # dataset_dir,
            # "nobs"
        # )
# 
        # os.makedirs(nobs_plot_dir, exist_ok=True)
# 
        # plots = generate_nobs_plots(
            # dataset,
            # nobs_plot_dir
        # )
# 
        # dataset_info = {
            # "name": dataset_name,
            # "plots": plots,
        # }

        website_data["datasets"].append(
            dataset_info
        )

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

    # return website_data


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





def old_main():
    db = Database("emcda.db")

    print(db.list_datasets())

    ds = db.dataset("gdas")

    # last 4 cycles
    cycles = ds.cycles[-4:]

    # t = ds.cycles[-1]
    cycle = ds.cycles[-1]
    t = datetime.combine(
        cycle.cycle_date,
        time(int(cycle.cycle_hour))
    )

    # ensure output dirs
    os.makedirs(os.path.join(OUT_DIR, "images"), exist_ok=True)

    # generate plots (placeholder for now)
    plots = []

    # for obsspace_name in ds.list_obsspaces():
        # obs = ds.obsspace(obsspace_name)
        # for var_name in obs.list_variables():
            # try:
                # field = obs.field(var_name)
                # f_t = field[t]
            # except Exception:
                # continue


    for obsspace_name in ds.list_obsspaces():
        obsspace = ds.obsspace(obsspace_name)

        try:
            field = obsspace.field("/ObsValue/seaSurfaceTemperature")
        except Exception:
            continue  # this obs space doesn't have SST

        try:
            f_t = field[t]
        except Exception:
            continue  # no data for this time

        coords = f_t.coords

        has_lat = "latitude" in coords
        has_lon = "longitude" in coords
        has_depth = "depth" in coords or "level" in coords

        if has_lat and has_lon and not has_depth:
            out_file = f"images/{obsspace.name}.png"
            plot_path = os.path.join(OUT_DIR, out_file)

            logger.info(f"Generating plot {plot_path}")
            result_path = f_t.plot(plot_path)

            plots.append({
                "name": obsspace.name,
                "path": out_file,
            })
