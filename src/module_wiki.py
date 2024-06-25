"""Module to create a series of formatted pages to list episodes in a wiki format"""

import os
import pathlib

from jinja2 import Template
from logging import debug, info

from module_episode import _format_post_text


def main(config, db, *args, **kwargs):
    """Main function for the module"""

    seasons = ["winter", "spring", "summer", "fall"]
    options = ["enable", "disable"]

    # Set a season not to be tracked
    if len(args) > 0 and args[0].lower() in options:
        track = args[0] == "enable"
        if args[1].isnumeric():
            # A specific show id was given
            info("Manually setting the tracking status for show id {}".format(args[1]))
            db.set_tracking(args[1], track=track)
        elif len(args) == 3 and args[1].lower() in seasons and args[2].isnumeric():
            # A season was provided
            info(
                "Manually setting the tracking status for the {} {} season".format(
                    args[1], args[2]
                )
            )
            db.set_track_season(args[1], args[2], track=track)

        return

    info("Running the wiki module and outputting formatted files")

    # Build the jinja template
    debug("Reading template file and creating jinja Template object")
    with open(config.wiki_template, "r") as file:
        template = Template(file.read(), trim_blocks=True)

    # First need to get list of season-year pairs that contain episodes
    debug("Identifying seasons that have episodes for tracked shows")
    seasons = db.get_seasons_with_episodes()

    # Next, for each season, create the context dict object and output the file
    info("Identified {} seasons to export as formatted files".format(len(seasons)))
    for pair in seasons:

        selected_season = pair[0]
        selected_year = pair[1]

        # Get shows in season from db that have episodes
        debug(
            "Fetching tracked shows with episodes from {} {}".format(
                selected_season, selected_year
            )
        )
        output_shows = db.get_shows_from_season(selected_season, selected_year)

        # Build dict object used for jinja templating
        context = _build_context(config, db, output_shows)
        context["season"] = selected_season
        context["year"] = selected_year

        # Do some filepath stuff
        debug(
            "Creating needed filepath for {} {}".format(selected_season, selected_year)
        )
        current_dir = os.getcwd()
        output_folder = os.path.join(
            current_dir, config.wiki_folder, str(selected_year)
        )
        pathlib.Path(output_folder).mkdir(parents=True, exist_ok=True)
        output_filename = os.path.join(output_folder, selected_season.lower() + ".md")

        # Create the output
        debug("Writing {}".format(output_filename))
        rendered = template.render(context=context)
        with open(output_filename, "w", encoding="utf8") as file:
            file.write(rendered)

        # Reset the updated column
        debug(
            "Marking shows as no longer updated for {} {}".format(
                selected_season, selected_year
            )
        )
        db.set_season_updated(selected_season, selected_year, updated=False)

    info("Finished writing formatted files")


def _build_context(config, db, shows_list):
    """Build context object for jinja given list of show ids"""

    context = {}
    context["shows"] = []

    for media_id in shows_list:
        # Get show
        debug("Fetching show with id {}".format(media_id))
        show = db.get_show(media_id)

        # Get an episode to use in _format_post_text
        debug("Fetching an episode from the show")
        latest_episode = db.get_latest_episode(show)

        # Check if show has English name
        if show.name_en:
            debug("Show has English name")
            heading_template = config.wiki_show_heading_with_en
        else:
            debug("No English name for show")
            heading_template = config.wiki_show_heading

        # Build heading
        debug("Formatting section heading")
        heading = _format_post_text(config, db, latest_episode, heading_template)

        # Build table of episodes
        debug("Formatting table of episodes")
        table = _format_post_text(config, db, latest_episode, "{discussions}")

        # Add it to the context object
        context["shows"].append([heading, table])

    # Sort the list alphabetically by heading
    context["shows"].sort(key=lambda x: x[0])

    return context
