"""Module used to update show information in the database."""

from logging import info, error, debug

from helper_functions import add_update_show_by_id


def main(config, db, *args, **kwargs):
    """Update show information in the database."""

    show_id = None

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

    retries = {}

    for show in shows:
        retries[show.id] = 0

    info("Updating {} shows in the database".format(len(shows)))
    for show in shows:
        updated_show = add_update_show_by_id(
            db=db, show_id=show.id, ratelimit=config.ratelimit
        )

        if not updated_show:
            if retries[show.id] >= 3:
                error("Failed getting show info 3 times, skipping")
                continue

            error(
                "Problem updating show, have retried {} times".format(retries[show.id])
            )
            retries[show.id] += 1
            shows.append(show)
