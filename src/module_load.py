"""Module to load upcoming episodes from a csv file."""

import csv

from logging import debug, info, error

from helper_functions import add_update_shows_by_id
from data.models import UpcomingEpisode


def main(config, db, *args, **kwargs):
    """Main function for load module."""

    # Check to make sure we have a filename argument
    if len(args) != 1:
        error(
            "Wrong number of args for episode module. Found {} args".format(len(args))
        )
        raise Exception("Wrong number of arguments")

    # Check to make sure the argument is a string
    if not isinstance(args[0], str):
        error(
            "Wrong type of arg for episode module. Found {} type".format(type(args[0]))
        )
        raise Exception("Wrong type of argument")

    # Check to make sure the argument is a csv file
    if not args[0].endswith(".csv"):
        error("Wrong filetype for episode module")
        raise Exception("Wrong file extension")

    # Read csv and create list of UpcomingEpisode objects
    found_episodes = []

    with open(args[0], mode="r") as infile:
        csv_file = csv.reader(infile)
        debug("Reading header row of {}".format(args[0]))
        csv_headers = next(csv_file)  # Unused header row for ease of reading

        for row in csv_file:
            debug("Parsing csv file rows...")
            try:
                media_id = row[0]
                number = row[1]
                airing_time = row[2]

                found_episode = UpcomingEpisode(
                    media_id=media_id, number=number, airing_time=airing_time
                )

                debug("Parsed upcoming episode in csv file: {}".format(found_episode))

            except:
                error("Problem parsing csv file")
                continue

            found_episodes.append(found_episode)

    info(
        "Parsed {} episodes in the csv file. Adding to the database...".format(
            len(found_episodes)
        )
    )

    # Built our list of episodes from the csv, now to add them to the db
    all_shows = db.get_shows(enabled="all")
    all_shows = [item.id for item in all_shows]
    enabled_shows = db.get_shows(enabled="enabled")
    enabled_shows = [item.id for item in enabled_shows]

    for episode in found_episodes:
        # Add show to the db if it doesn't exist
        if episode.media_id not in all_shows:
            debug("Adding show {} to database.".format(episode.media_id))
            add_update_shows_by_id(db, [episode.media_id])

        # Enable the show if it isn't already
        if episode.media_id not in enabled_shows:
            debug("Enabling show {} in database.".format(episode.media_id))
            episode_show = db.get_show(id=episode.media_id)
            db.set_show_enabled(show=episode_show)

        # Add the upcoming episode
        db.add_upcoming_episode(episode)
        debug("Added upcoming episode to the database: {}".format(episode))

    info("Finished adding upcoming episodes to the database.")
