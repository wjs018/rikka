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
    elif len(args) == 0:
        info("Trying to enable all shows in the database")
        enabled_shows = 0
        shows = db.get_shows(enabled="all")

        if shows:
            for show in shows:
                db.set_show_enabled(show, enabled=True, commit=True)
                enabled_shows += 1
            info("Enabled {} shows".format(enabled_shows))
        else:
            info("No shows found in database to enable")

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
