"""Module used to update show information in the database."""

from logging import info, error, debug

from helper_functions import add_update_show_by_id


def main(config, db, *args, **kwargs):
    """Update show information in the database."""

    show_id = None

    if args[0].isnumeric():
        show_id = int(args[0])
    elif len(args) == 1:
        enabled = args[0]
    elif len(args) == 0:
        enabled = "enabled"
    else:
        error("Incorrect number of arguments for update module")

    if show_id:
        debug("Fetching show with id {}".format(show_id))
        shows = [db.get_show(id=show_id)]
    else:
        debug("Fetching list of shows from database. enable set to {}".format(enabled))
        shows = db.get_shows(enabled=enabled)

    info("Updating {} shows in the database".format(len(shows)))
    for show in shows:
        db_show = add_update_show_by_id(
            db=db, show_id=show.id, ratelimit=config.ratelimit
        )

        if not db_show:
            error("Problem updating show with id {}".format(show.id))
