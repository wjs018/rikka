"""Module to remove a show from the database."""

from logging import info, warning


def main(config, db, *args, **kwargs):
    """Removes a show from the database."""

    if len(args) == 1:
        info("Trying to remove a show with id {}".format(args[0]))
        db.remove_show(args[0])
    elif len(args) == 0:
        info("Trying to remove all disabled shows")
        shows = db.get_shows(enabled="disabled")

        for show in shows:
            db.remove_show(show.id)

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
