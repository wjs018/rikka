"""Module used to update show information in the database."""

from logging import info, error, debug

from helper_functions import add_update_shows_by_id


def main(config, db, *args, **kwargs):
    """Update show information in the database."""

    show_id = None
    show_ids = []

    if len(args) == 0:
        enabled = "enabled"
    elif args[0].isnumeric():
        show_id = int(args[0])
    elif len(args) == 1:
        enabled = args[0]
    else:
        error("Incorrect number of arguments for update module")

    if show_id:
        debug("Fetching show with id {}".format(show_id))
        shows = [db.get_show(id=show_id)]
    else:
        debug("Fetching list of shows from database. enable set to {}".format(enabled))
        shows = db.get_shows(enabled=enabled)

    for show in shows:
        show_ids.append(show.id)

    info("Updating {} shows in the database".format(len(shows)))

    num_shows = add_update_shows_by_id(
        db, show_ids, config.ratelimit, ignore_enabled=True
    )

    # Clear out old ignored episodes from the database
    db.remove_old_ignored_episodes(num_days=config.episode_retention)

    if num_shows != len(shows):
        error(
            "Number of updated shows does not match number of api queries. Some were \
            likely skipped due to bad api responses."
        )
