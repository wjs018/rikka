"""Module to disable a show in the database."""

from logging import info, warning

from helper_functions import add_update_shows_by_id


def main(config, db, *args, **kwargs):
    """Disables a show in the database."""

    if len(args) == 1:

        if args[0].isdigit():
            info("Trying to disable a show with id {}".format(args[0]))
            show = db.get_show(args[0])

            if show:
                info("Show found in database, disabling")
                db.set_show_enabled(show, enabled=False, commit=True)
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
                        disabled_shows += 1

            info("Disabled {} nsfw shows found in the database".format(disabled_shows))

        elif args[0].upper() == "ALL":
            info("Disabling all shows in the database")
            shows = db.get_shows()

            disabled_shows = 0

            if shows:
                for show in shows:
                    db.set_show_enabled(show, enabled=False, commit=True)
                    disabled_shows += 1

            info("Disabled {} shows found in the database".format(disabled_shows))

        elif args[0].upper() == "FINISHED":
            info("Disabling all completed shows in the database")
            shows = db.get_shows()
            show_ids = []

            disabled_shows = 0

            if shows:
                for show in shows:
                    show_ids.append(show.id)

                raw_shows = add_update_shows_by_id(db, show_ids, get_raw_shows=True)

                for raw_show in raw_shows:
                    if not raw_show.is_airing:
                        selected_show = db.get_show(id=raw_show.media_id)
                        db.set_show_enabled(selected_show, enabled=False, commit=True)

            info("Disabled {} shows found in the database".format(disabled_shows))

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
