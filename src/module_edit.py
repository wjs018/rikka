"""Module used to edit the rikka database."""

import yaml
from logging import debug, info, exception, error

from helper_functions import add_update_shows_by_id


def main(config, db, *args, **kwargs):
    """Main function for the edit module"""

    if len(args) == 1:
        if _edit_with_file(db, config.ratelimit, args[0]):
            info("Edit successful; saving")
            db.save()
        else:
            error("Edit failed")
            db.rollback()


def _edit_with_file(db, ratelimit, edit_file):
    """Add shows to the database using a yaml file."""

    info("Parsing yaml file {}".format(edit_file))

    try:
        with open(edit_file, "r", encoding="UTF-8") as f:
            parsed = yaml.safe_load(f)
    except yaml.YAMLError:
        exception("Failed to parse edit file")
        return False

    enabled_list = parsed.get("enabled", [])
    disabled_list = parsed.get("disabled", [])

    info(
        "Found {} enabled shows and {} disabled shows in yaml file".format(
            len(enabled_list), len(disabled_list)
        )
    )

    enabled_done = True
    disabled_done = True

    if enabled_list:
        enabled_shows = add_update_shows_by_id(
            db, enabled_list, ratelimit, enabled=True
        )
        enabled_done = len(enabled_list) == enabled_shows
    if disabled_list:
        disabled_shows = add_update_shows_by_id(
            db, disabled_list, ratelimit, enabled=False
        )
        disabled_done = len(disabled_list) == disabled_shows

    if not enabled_done or not disabled_done:
        error("Number of added shows does not match parsed yaml.")
        return False

    return True
