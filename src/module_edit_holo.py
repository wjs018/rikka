"""Module to parse holo formatted yaml files."""

import re
import yaml
from logging import info, exception, error

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
    """Add shows to the database using a holo formatted yaml file."""

    info("Parsing yaml file {}".format(edit_file))

    try:
        with open(edit_file, "r", encoding="UTF-8") as f:
            parsed = list(yaml.safe_load_all(f))
            info("Found {} shows in parsed yaml file.".format(len(parsed)))
    except yaml.YAMLError:
        exception("Failed to parse edit file")
        return False

    found_ids = []
    anilist_expression = re.compile(r"\/anime\/[\d]*")

    for doc in parsed:
        anilist_url = doc["info"]["anilist"]

        if not anilist_url:
            info(
                "Skipping show {} that does not have an AniList url.".format(
                    doc["title"]
                )
            )
            continue

        match = re.search(anilist_expression, anilist_url)
        anilist_id = match.group()[7:]
        found_ids.append(anilist_id)

        info("Found show with AniList id {}".format(anilist_id))

    added_shows = add_update_shows_by_id(db, found_ids, ratelimit)

    if not added_shows:
        error("Problem adding shows from yaml file.")

    info("Successfully added {} shows to the database.".format(added_shows))

    return True
