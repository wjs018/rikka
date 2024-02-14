"""Module to remove a show from the database."""

from logging import info, warning


def main(config, db, *args, **kwargs):
    """Removes a show from the database."""

    if len(args) == 1:
        if args[0].isdigit():
            info("Trying to remove a show with id {}".format(args[0]))
            db.remove_show(args[0])
        elif args[0].upper() == "NSFW":
            info("Trying to remove all shows marked NSFW in the database.")
            shows = db.get_shows(enabled="all")

            removed_shows = 0

            for show in shows:
                if show.is_nsfw:
                    db.remove_show(show.id)
                    removed_shows += 1

            info("Removed {} shows marked NSFW in the database.".format(removed_shows))

    elif len(args) == 0:
        info("Trying to remove all disabled shows")
        shows = db.get_shows(enabled="disabled")

        for show in shows:
            db.remove_show(show.id)

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
