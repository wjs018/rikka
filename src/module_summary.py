"""Module to create and update summary posts."""

import time
import operator

from logging import debug, info, error

import lemmy
from helper_functions import safe_format
from data.models import ShowType, SummaryPost


def main(config, db, *args, **kwargs):
    """Main function for summary module"""

    if len(args) not in [0, 1]:
        error(
            "Incorrect number of arguments, not 0 or 1. Found {} arguments".format(
                len(args)
            )
        )
        raise Exception("Wrong number of arguments")

    lemmy.init_lemmy(config)

    if len(args) == 0:
        handled = _create_summary_post(db, config)
        if handled:
            info("Successfully created a new summary post")
    elif len(args) == 1 and args[0].lower() == "update":
        handled = _update_summary_post(db, config)
        if handled:
            info("Successuflly updated summary post")
    else:
        error("Unknown argument provided: {}".format(args[0]))
        raise Exception("Unknown argument provided")

    if not handled:
        error("Problem creating/updating summary post")
        raise Exception("Problem creating or updating summary post")


def _create_summary_post(db, config):
    """Function for handling creation of a summary post"""

    # First, unpin any threads that might already exist
    pinned_posts = db.get_pinned_summary_posts()
    for post in pinned_posts:
        info("Unpinning post found at {}".format(post.post_url))
        lemmy.feature_post(post_url=post.post_url, featured=False)
        post.pinned = 0
        db.add_summary_post(post)

    # Next, rebuild RecentEpisodes table in database
    db.build_latest_episodes(config.summary_days)

    # Next, prune old episodes that are no longer recent
    db.prune_latest_episodes(config.summary_days)

    # Generate the post contents
    post_title, post_body = _create_post_contents(config, db)

    # Create the lemmy post
    info("Creating new summary post on lemmy")
    new_post = lemmy.submit_text_post(
        config.l_community, post_title, post_body, nsfw=False, url=None
    )

    if new_post is not None:
        post_link = lemmy.get_shortlink_from_id(new_post["id"])
        if config.pin_summary:
            lemmy.feature_post(post_url=post_link, featured=config.pin_summary)
    else:
        error("Problem making post to lemmy")
        return None

    # Figure out the thread number
    previous_summary = db.get_latest_summary_post()
    if previous_summary:
        thread_num = previous_summary.number + 1
    else:
        thread_num = 1

    # Get the current time
    debug("Getting timestamp and saving summary post to the database")
    current_time = int(time.time())

    # Construct object
    summary_post = SummaryPost(
        number=thread_num,
        post_url=post_link,
        pinned=config.pin_summary,
        creation_time=current_time,
        last_update=current_time,
    )

    # Add it to the database
    db.add_summary_post(summary_post)

    return True


def _update_summary_post(db, config):
    """Function for handling updating of a summary post"""

    # First, rebuild RecentEpisodes table in database
    db.build_latest_episodes(config.summary_days)

    # Next, prune old episodes that are no longer recent
    db.prune_latest_episodes(config.summary_days)

    # Generate the post contents
    _, post_body = _create_post_contents(config, db)

    # Fetch the most recent summary post
    latest_summary = db.get_latest_summary_post()

    if not latest_summary:
        error("No existing summary post found to update")
        return False

    # Check if an update is needed
    latest_summary_body = lemmy.get_post_body(latest_summary.post_url)
    if post_body == latest_summary_body:
        info("Summary post is unchanged. No update needed.")
        return True

    # Update the lemmy post
    info("Updating the latest summary post on lemmy")
    updated_post = lemmy.edit_text_post(url=latest_summary.post_url, body=post_body)

    if updated_post is not None:
        post_link = lemmy.get_shortlink_from_id(updated_post["id"])
        if config.pin_summary != updated_post["featured_community"]:
            lemmy.feature_post(post_url=post_link, featured=config.pin_summary)
    else:
        error("Problem making post to lemmy")
        return None

    # Update timestamp for summary post and save it to the db
    debug("Updating summary post timestamp and saving it to the database")
    current_time = int(time.time())
    latest_summary.last_update = current_time

    # Add it to the database
    db.add_summary_post(latest_summary)

    return True


def _create_post_contents(config, db):
    """Generates the title and body of the summary post"""

    title = config.summary_title

    recent_episodes = db.get_latest_episodes()

    if config.alphabetize:

        for episode in recent_episodes:
            show = db.get_show(episode.media_id)
            episode.name = show.name

            if not show.name_en:
                episode.name_en = show.name
            else:
                episode.name_en = show.name_en

        recent_episodes.sort(key=operator.attrgetter("name_en", "name"))

    body = safe_format(
        config.summary_body,
        latest_episodes=_gen_text_latest_episodes(config, db, recent_episodes),
    )

    return title[:198], body


def _gen_text_latest_episodes(config, db, episodes):
    """Generates the table of latest episode links"""

    table_rows = ""

    for episode in episodes:
        has_en = False
        is_movie = False

        show = db.get_show(episode.media_id)

        if show.type == ShowType.MOVIE.value:
            is_movie = True

        if is_movie:
            ep_markdown = episode.to_markdown_movie_en()
        else:
            ep_markdown = episode.to_markdown_en()

        formatted = safe_format(
            ep_markdown,
            show_name=episode.name,
            show_name_en=episode.name_en,
            episode=episode.number,
            link=episode.link,
        )

        table_rows += formatted.strip() + "\n"

    return table_rows
