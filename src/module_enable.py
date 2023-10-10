"""Module to enable a show in the database."""

from logging import info, warning


def main(config, db, *args, **kwargs):
    """Enables a show in the database."""

    if len(args) == 1:
        info("Trying to enable a show with id {}".format(args[0]))
        show = db.get_show(args[0])

        if show:
            info("Show found in database, enabling")
            db.set_show_enabled(show, enabled=True, commit=True)
        else:
            info("Show not found in database to enable")

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
