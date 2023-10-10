"""Module to disable a show in the database."""

from logging import info, warning


def main(config, db, *args, **kwargs):
    """Disables a show in the database."""

    if len(args) == 1:
        info("Trying to disable a show with id {}".format(args[0]))
        show = db.get_show(args[0])

        if show:
            info("Show found in database, disabling")
            db.set_show_enabled(show, enabled=False, commit=True)
        else:
            info("Show not found in database to disable")

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
