"""Module used to edit the rikka database."""

import yaml
from logging import debug, info, exception, error

from helper_functions import add_update_show_by_id


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

    retries = {}

    for show_id in enabled_list:
        retries[show_id] = 0
    for show_id in disabled_list:
        retries[show_id] = 0

    for show_id in enabled_list:
        debug("Adding show from yaml file with id {}".format(show_id))
        show = add_update_show_by_id(db=db, show_id=show_id, ratelimit=ratelimit)

        if not show:
            if retries[show_id] > 3:
                error("Failed getting show info 3 times, skipping")
                continue

            error("Problem adding show, have retried {} times".format(retries[show_id]))
            retries[show_id] += 1
            enabled_list.append(show_id)

    for show_id in disabled_list:
        debug(
            "Adding show from yaml file with id {} in a disabled state".format(show_id)
        )
        show = add_update_show_by_id(
            db=db, show_id=show_id, ratelimit=ratelimit, enabled=False
        )

        if not show:
            if retries[show_id] > 3:
                error("Failed getting show info 3 times, skipping")
                continue

            error("Problem adding show, have retried {} times".format(retries[show_id]))
            retries[show_id] += 1
            disabled_list.append(show_id)

    return True
