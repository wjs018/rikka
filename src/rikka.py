"""Main program to run rikka."""

# Standard library imports
import argparse
import logging
import os
import sys
from logging import debug, error, exception, info, warning
from logging.handlers import TimedRotatingFileHandler
from time import time

# Rikka imports
import config as config_loader
from data import database

# Metadata
name = "Rikka"
description = "episode discussion bot"
version = "0.5.0"


def main(config, args, extra_args):
    """Primary function that calls all other modules as needed."""

    # Set things up
    db = database.open_database(config.database)
    if not db:
        error("Cannot continue running without a database")
        return

    try:
        info("Running module {}".format(config.module))
        if config.module == "setup":
            debug("Setting up database")
            db.setup_tables()

        elif config.module == "add":
            debug("Adding a show to the database")
            import module_add as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "disable":
            debug("Disabling a show in the database")
            import module_disable as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "enable":
            debug("Enabling a show in the database")
            import module_enable as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "remove":
            debug("Removing a show from the database")
            import module_remove as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "update":
            debug("Updating shows in the database")
            import module_update as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "edit":
            debug("Parsing a yaml file")
            import module_edit as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "edit_holo":
            debug("Parsing a holo-formatted yaml file")
            import module_edit_holo as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "edit_season":
            debug("Adding shows for an entire season")
            import module_edit_season as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "user_thread":
            debug("Adding a user-created thread to the database")
            import module_user_thread as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "episode":
            debug("Searching for new episodes and making discussion posts")
            import module_episode as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

        elif config.module == "listen":
            debug("Checking for messages requesting newly created threads")
            import module_listen as m  # pylint: disable=import-outside-toplevel

            m.main(config, db, *extra_args)

    except:
        exception("Unknown exception or error")
        db._db.rollback()

    db._db.close()


if __name__ == "__main__":
    # Parse the command line arguments
    parser = argparse.ArgumentParser(description="{}, {}".format(name, description))
    parser.add_argument(
        "--no-input",
        dest="no_input",
        action="store_true",
        help="run without stdin and write to a log file",
    )
    parser.add_argument(
        "-m",
        "--module",
        dest="module",
        nargs=1,
        choices=[
            "setup",
            "edit",
            "edit_holo",
            "edit_season",
            "update",
            "add",
            "disable",
            "enable",
            "remove",
            "episode",
            "user_thread",
            "listen",
        ],
        default=["episode"],
        help="runs the specified module",
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        nargs=1,
        default=["config.ini"],
        help="use or create the specified database location",
    )
    parser.add_argument(
        "-d",
        "--database",
        dest="db_name",
        nargs=1,
        default=[None],
        help="use or create the specified database location",
    )
    parser.add_argument(
        "-s",
        "--community",
        dest="community",
        nargs=1,
        default=None,
        help="set the community on which to make posts",
    )
    parser.add_argument(
        "-l",
        "--lemmy-instance",
        dest="lemmy_instance",
        nargs=1,
        default=None,
        help="set the instance hosting the community",
    )
    parser.add_argument(
        "-L",
        "--log-dir",
        dest="log_dir",
        nargs=1,
        default=["logs"],
        help="set the log directory",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="{} v{}, {}".format(name, version, description),
    )
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("extra", nargs="*")
    args = parser.parse_args()

    config_file = args.config_file[0]
    c = config_loader.from_file(config_file)
    if c is None:
        print("Cannot start without a valid configuration file")
        sys.exit(2)

    # Override config with args
    c.debug |= args.debug
    c.module = args.module[0]
    c.log_dir = args.log_dir[0]
    if args.db_name[0] is not None:
        c.database = args.db_name[0]
    if args.community is not None:
        c.community = args.community[0]
    if args.lemmy_instance is not None:
        c.l_instance = args.lemmy_instance[0]

    # Start
    use_log = args.no_input

    if use_log:
        os.makedirs(c.log_dir, exist_ok=True)

        log_file = "{dir}/rikka_{mod}.log".format(dir=c.log_dir, mod=c.module)
        logging.basicConfig(
            handlers=[
                TimedRotatingFileHandler(
                    log_file, when="midnight", backupCount=7, encoding="UTF-8"
                )
            ],
            format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.DEBUG if c.debug else logging.INFO,
        )
    else:
        logging.basicConfig(
            format="%(levelname)s | %(message)s",
            level=logging.DEBUG if c.debug else logging.INFO,
        )

    if use_log:
        info("------------------------------------------------------------")
    err = config_loader.validate(c)
    if err:
        warning("Configuration state invalid: {}".format(err))

    if c.debug:
        info("DEBUG MODE ENABLED")
    start_time = time()
    main(c, args, args.extra)
    end_time = time()

    time_diff = end_time - start_time
    info("")
    info("Run time: {:.6} seconds".format(time_diff))

    if use_log:
        info("------------------------------------------------------------\n")
