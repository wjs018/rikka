"""Module used to add a user-created thread to the database."""

import re

from logging import info, error, debug

import lemmy
from helper_functions import add_update_shows_by_id


def main(config, db, *args, **kwargs):
    """Main function for the user_thread module"""

    # Arguments should be post_url, episode_number, anilist_id (optional)

    if len(args) not in [1, 2, 3]:
        error("Incorrect number of arguments provided to module")
        raise Exception("Wrong number of arguments")

    lemmy.init_lemmy(config)

    if len(args) == 1:
        # Need to get episode number from title
        post_title = lemmy.get_post_title(args[0])
        episode_expression = re.compile(r"Episode [\d]+")
        episode_match = re.findall(episode_expression, post_title)
        episode_number = int(episode_match[-1][8:])

    if len(args) == 3:
        debug("Manually specified AniList id provided")
        if not args[2].isdigit():
            error("AniList id must be numeric")
            raise Exception("Improper AniList id provided")

        episode_number = int(args[1])
        anilist_id = int(args[2])

    if len(args) in [1, 2]:
        if len(args) == 2:
            episode_number = int(args[1])

        debug("Extracting AniList id from post")
        anilist_expression = re.compile(r"anilist.co\/anime\/[\d]*")

        info("Fetching lemmy post at {}".format(args[0]))
        post_contents = lemmy.get_post_body(args[0])

        if not post_contents:
            error("No post info found")
            raise Exception("Unable to fetch lemmy post info")

        debug("Extracting AniList id")
        text_match = re.search(anilist_expression, post_contents)
        anilist_id = text_match.group()[17:]

    info(
        "Found AniList id of {} and episode number of {}".format(
            anilist_id, episode_number
        )
    )

    # Check if show already exists in db, add it if it doesn't
    db_show = db.get_show(id=anilist_id)

    if not db_show:
        # Show doesn't exist in database, add it
        added = add_update_shows_by_id(db, [anilist_id], config.ratelimit)

        if not added:
            error("Could not add show to database")
            raise Exception("Problem adding show to database")

    # Add episode thread to database
    db.add_episode(anilist_id, episode_number, args[0], can_edit=False)
