"""Module to disable a show in the database."""

from logging import info, warning


def main(config, db, *args, **kwargs):
    """Disables a show in the database."""

    if len(args) == 1:

        if args[0].isdigit():
            info("Trying to disable a show with id {}".format(args[0]))
            show = db.get_show(args[0])

            if show:
                info("Show found in database, disabling")
                db.set_show_enabled(show, enabled=False, commit=True)
                db.remove_upcoming_episodes(show.id)
            else:
                info("Show not found in database to disable")

        elif args[0].upper() == "NSFW":
            info("Disabling all shows marked NSFW in the database")
            shows = db.get_shows()

            disabled_shows = 0

            if shows:
                for show in shows:
                    if show.is_nsfw:
                        db.set_show_enabled(show, enabled=False, commit=True)
                        db.remove_upcoming_episodes(show.id)
                        disabled_shows += 1

            info("Disabled {} nsfw shows found in the database".format(disabled_shows))

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
