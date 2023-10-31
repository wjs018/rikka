"""
Module to add a show to the database, update its information and enable
discussion threads for it.
"""

from logging import info, warning, error

from helper_functions import add_update_shows_by_id


def main(config, db, *args, **kwargs):
    """Add a show to the database and update its info."""

    if len(args) == 1:
        info("Trying to add show with id {}".format(args[0]))
        show = add_update_shows_by_id(db, [args[0]], ratelimit=config.ratelimit)

        if not show:
            error("Problem adding show with id {}".format(args[0]))

    else:
        warning("Wrong number of args for add module. Found {} args".format(len(args)))
