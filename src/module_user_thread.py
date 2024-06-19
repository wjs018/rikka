"""Module used to add a user-created thread to the database."""

import re
import time

from logging import info, error, debug

import lemmy
from data.models import UpcomingEpisode
from helper_functions import add_update_shows_by_id
from module_episode import _format_post_text, _edit_post


def main(config, db, *args, **kwargs):
    """Main function for the user_thread module"""

    # Arguments should be post_url, episode_number, anilist_id (optional)
    # Fourth argument is either 'comment' or is not present to determine show
    # comment creation in the thread
    make_comment = False

    if len(args) not in [1, 2, 3, 4]:
        error("Incorrect number of arguments provided to module")
        raise Exception("Wrong number of arguments")

    lemmy.init_lemmy(config)

    if len(args) == 1:
        # Need to get episode number from title
        post_title = lemmy.get_post_title(args[0])
        episode_expression = re.compile(r"(?i)Episode [\d]+")
        episode_match = re.findall(episode_expression, post_title)
        episode_number = int(episode_match[-1][8:])

    if len(args) in [3, 4]:
        debug("Manually specified AniList id provided")
        if not args[2].isdigit():
            error("AniList id must be numeric")
            raise Exception("Improper AniList id provided")

        episode_number = int(args[1])
        anilist_id = int(args[2])

    if len(args) in [1, 2]:
        if len(args) == 2:
            episode_number = int(args[1])

        debug("Extracting AniList id from post")
        anilist_expression = re.compile(r"anilist.co\/anime\/[\d]*")

        info("Fetching lemmy post at {}".format(args[0]))
        post_contents = lemmy.get_post_body(args[0])

        if not post_contents:
            error("No post info found")
            raise Exception("Unable to fetch lemmy post info")

        debug("Extracting AniList id")
        text_match = re.search(anilist_expression, post_contents)
        anilist_id = text_match.group()[17:]

    if len(args) == 4 and args[3].lower() == "comment":
        make_comment = True

    info(
        "Found AniList id of {} and episode number of {}".format(
            anilist_id, episode_number
        )
    )

    # Check if show already exists in db, add it if it doesn't
    db_show = db.get_show(id=anilist_id)

    if not db_show:
        # Show doesn't exist in database, add it
        added = add_update_shows_by_id(db, [anilist_id], config.ratelimit)

        if not added:
            error("Could not add show to database")
            raise Exception("Problem adding show to database")

    # Add episode thread to database
    db.add_episode(anilist_id, episode_number, args[0], can_edit=False)

    if make_comment:
        handled = _create_user_thread_comment(
            db, config, args[0], anilist_id, episode_number
        )

        if handled:
            info("Comment successfully created")
            link = handled["ap_id"]
            db.add_user_episode(anilist_id, episode_number, link)
        else:
            error("Problem creating comment")
            raise Exception("Problem creating comment in thread")

    user_show = db.get_show(id=anilist_id)
    user_comments = db.get_user_episodes(user_show)

    for comment in user_comments:
        comment_body = _format_post_text(
            config, db, comment, config.user_thread_comment
        )
        response = lemmy.edit_text_comment(comment.link, comment_body)
        if not response:
            error("Problem editing user episode {}".format(comment))

    db_show = db.get_show(id=anilist_id)
    episodes = db.get_episodes(db_show)

    for episode in episodes:
        if episode.can_edit:

            if config.submit_image == "banner":
                banner_image = db.get_banner_image(episode.media_id)
                if banner_image:
                    image_url = banner_image.image_link
                else:
                    image_url = None
            elif config.submit_image == "cover":
                cover_image = db.get_cover_image(episode.media_id)
                if cover_image:
                    image_url = cover_image.image_link
                else:
                    image_url = None
            else:
                image_url = None

            _edit_post(
                config,
                db,
                episode,
                episode.link,
                config.submit,
                image_url=image_url,
            )


def _create_user_thread_comment(db, config, post_url, anilist_id, episode_number):
    """Creates a comment to the post"""

    # Create UpcomingEpisode object for use
    episode = UpcomingEpisode(anilist_id, episode_number, int(time.time()))

    # First, generate post contents
    body = _format_post_text(config, db, episode, config.user_thread_comment)

    # Create the comment
    info("Creating a comment in the user thread as {}".format(post_url))
    response = lemmy.submit_text_comment(post_url, body)

    if response:
        return response

    return None
