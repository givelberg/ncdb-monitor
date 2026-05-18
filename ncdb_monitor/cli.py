import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

import argparse
from pathlib import Path

from ncdb.api.database import Database
from ncdb_monitor.generate import generate_website_data
from ncdb_monitor.render import generate_html

from ncdb.scanners.marine_da_scanner import MarineDAScanner
from ncdb.scanners.obsforge_scanner import ObsForgeScanner

from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
# import os
# from pathlib import Path
# import logging
# logger = logging.getLogger(__name__)

SCANNERS = {
    "marine": MarineDAScanner,
    "obsforge": ObsForgeScanner,
}



def cmd_scan(args):

    logger.info("Scanning data into database")

    db = Database(args.database)
    # print(db.list_datasets())

    scanner_cls = SCANNERS[args.scanner]

    logger.info(f"Database: {args.database}")
    logger.info(f"Data root: {args.data_dir}")
    logger.info(f"Scanner: {args.scanner}")

    db.scan(
        data_root=args.data_dir,
        n_cycles=args.n_cycles,
        scanner_cls=scanner_cls
    )


def cmd_generate(args):
    logger.info("Generating website data")

    db = Database(args.database)

    logger.info(f"Database: {args.database}")
    logger.info(f"Website dir: {args.website_dir}")

    website_dir = Path(args.website_dir)

    generate_website_data(
        db=db,
        website_dir=website_dir
    )

def cmd_render(args):
    logger.info(f"Rendering: Website dir: {args.website_dir}")

    website_dir = Path(args.website_dir)

    generate_html(
        website_dir=website_dir
    )


def save_run_report(website_dir, run_report):
    import json
    from pathlib import Path

    runs_dir = Path(website_dir) / "runs"
    runs_dir.mkdir(exist_ok=True)

    start_time = run_report["start_time"]
    run_file = runs_dir / f"{start_time}.json"

    with open(run_file, "w") as f:
        json.dump(run_report, f, indent=2)


def cmd_run(args):
    from datetime import datetime
    import time

    start = time.time()
    start_time = datetime.utcnow().isoformat() + "Z"

    logger.info("=== NCDB Monitor PIPELINE ===")

    # SCAN
    cmd_scan(args)

    # GENERATE
    cmd_generate(args)

    # RENDER
    cmd_render(args)

    end = time.time()
    end_time = datetime.utcnow().isoformat() + "Z"

    run_report = {
        "status": "success",
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": round(end - start, 3),

        "database": args.database,
        "website_dir": str(args.website_dir),
        "scanner": args.scanner,
        "n_cycles": args.n_cycles,
    }

    save_run_report(args.website_dir, run_report)

    return run_report

def old_cmd_run(args):

    logger.info("=== NCDB Monitor PIPELINE ===")

    # 1. SCAN
    logger.info("=== SCAN ===")
    cmd_scan(args)

    # 2. GENERATE
    logger.info("=== GENERATE ===")
    cmd_generate(args)

    # 3. RENDER
    logger.info("=== RENDER ===")
    cmd_render(args)



# the server is currently redundant
class ReusableTCPServer(TCPServer):
    allow_reuse_address = True


def cmd_serve(args):

    website_dir = Path(args.website_dir).resolve()

    port = args.port

    logger.info(f"Serving {website_dir} at http://localhost:{port}")

    # Important: switch working directory to website root
    os.chdir(website_dir)

    handler = SimpleHTTPRequestHandler

    with ReusableTCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down server")
            httpd.shutdown()


def build_parser():
    parser = argparse.ArgumentParser(
        description="NCDB monitoring application"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    #
    # scan
    #
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan filesystem data into database"
    )

    scan_parser.add_argument(
        "--scanner",
        required=True,
        choices=["marine", "obsforge"],
        help="Scanner type to use"
    )

    scan_parser.add_argument(
        "--n-cycles",
        type=int,
        default=-1,
        help="Number of cycles to scan"
    )

    scan_parser.add_argument(
        "--data-dir",
        required=True,
        help="Root data directory"
    )

    scan_parser.add_argument(
        "--database",
        required=True,
        help="Path to ncdb database"
    )

    scan_parser.set_defaults(func=cmd_scan)

    #
    # generate
    #
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate website data"
    )

    gen_parser.add_argument(
        "--database",
        required=True,
        help="Path to ncdb database"
    )

    gen_parser.add_argument(
        "--website-dir",
        required=True,
        help="Website output directory"
    )

    gen_parser.set_defaults(func=cmd_generate)

    #
    # render
    #
    render_parser = subparsers.add_parser(
        "render",
        help="Render website HTML"
    )

    render_parser.add_argument(
        "--website-dir",
        required=True,
        help="Website output directory"
    )

    render_parser.set_defaults(func=cmd_render)

    #
    # serve
    #
    # serve_parser = subparsers.add_parser(
        # "serve",
        # help="Serve generated website"
    # )
# 
    # serve_parser.add_argument(
        # "--website-dir",
        # required=True,
        # help="Website output directory"
    # )
# 
    # serve_parser.add_argument(
        # "--port",
        # type=int,
        # default=8734,
        # # default=8000,
        # help="Port number"
    # )
#
    # serve_parser.set_defaults(func=cmd_serve)

    #
    # run
    #
    run_parser = subparsers.add_parser(
        "run",
        help="Run monitor pipeline"
    )

    run_parser.set_defaults(func=cmd_run)

    run_parser.add_argument(
        "--scanner",
        required=True,
        choices=["marine", "obsforge"],
        help="Scanner type to use"
    )

    run_parser.add_argument(
        "--n-cycles",
        type=int,
        default=-1,
        help="Number of cycles to scan"
    )

    run_parser.add_argument(
        "--data-dir",
        required=True,
        help="Root data directory"
    )

    run_parser.add_argument(
        "--database",
        required=True,
        help="Path to ncdb database"
    )

    run_parser.add_argument(
        "--website-dir",
        required=True,
        help="Website output directory"
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    args.func(args)


if __name__ == "__main__":
    main()
