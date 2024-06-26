"""Module to check for user requests to create new discussion threads."""

import re

from logging import debug, info, error

import lemmy


error_message = (
    "There was a problem with the request. The following message was "
    "generated from your request. If this message is unhelpful and you need "
    "additional help, please see my profile page for the contact "
    "information of my maintainer.\n\nBot output:\n\n> "
)


def main(config, db, *args, **kwargs):
    """Main function for listen module"""

    global error_message

    lemmy.init_lemmy(config)

    info("Fetching unread private messages to parse")
    messages = lemmy.get_private_messages(unread_only=True)

    if not messages:
        info("No unread messages found")
        return

    for message in messages:

        handled = _handle_message(db, config, message)
        # handled, if successful, has form [Show object, episode_number]

        if not handled:
            reply_message = error_message
            lemmy.create_private_message(reply_message, recipient=message.sender_id)
            lemmy.set_private_message_read(message.message_id, True)
        else:
            episode = db.get_episode(handled[0], handled[1])
            created_thread = episode.link
            reply_message = "Discussion thread successfully created at {}".format(
                created_thread
            )
            lemmy.set_private_message_read(message.message_id, True)
            lemmy.create_private_message(reply_message, recipient=message.sender_id)

            db.remove_ignored_episode(episode.media_id, episode.number)


def _handle_message(db, config, message):
    """Parses and handles a private message"""

    global error_message
    message_ending = (
        "\n\n---\n\nThe format to request an episode discussion thread is:\n\n"
        "> anilist_link Episode ##\n\n"
        "So, if you were requesting a discussion thread for episode 1 of Mushishi, "
        "the message would be:\n\n"
        "> https://anilist.co/anime/457/Mushishi/ Episode 1"
        "\n\nIf you have any issues with this bot, please contact the "
        "maintainer for assistance. You can check my user profile for "
        "my maintainer's contact information.\n\n"
        "Project source code can be found at https://github.com/wjs018/rikka"
    )

    info("Parsing message {} for info.".format(message.message_id))
    anilist_expression = re.compile(r"anilist.co\/anime\/[\d]*")
    text_match = re.search(anilist_expression, message.message_contents)

    if not text_match:
        error_message += "Could not parse message for AniList id" + message_ending
        error("Could not parse message for AniList id")
        return False

    anilist_id = text_match.group()[17:]

    episode_expression = re.compile(r"(?i)Episode [\d]+")
    episode_match = re.findall(episode_expression, message.message_contents)

    if not episode_match:
        error_message += "Could not parse episode number" + message_ending
        error("Could not parse episode number")
        return False

    episode_number = int(episode_match[-1][8:])

    info("Parsed show id {} and episode number {}".format(anilist_id, episode_number))

    debug("Checking database for show with id {}".format(anilist_id))
    selected_show = db.get_show(id=anilist_id)

    if not selected_show:
        error_message += (
            "No show with matching id found in database, contact"
            " maintainer to add the show to the database if needed."
        ) + message_ending
        error("No show with matching id found in database")
        return False

    debug("Checking if there is an existing discussion thread for that episode")
    found_episode = db.get_episode(selected_show, episode_number)

    if found_episode:
        error_message = "Found existing discussion thread at {}".format(
            found_episode.link
        )
        info("Found existing discussion thread at {}".format(found_episode.link))
        return False

    debug("Checking for a more recent episode for the show")
    latest_episode = db.get_latest_episode(selected_show)

    if latest_episode:
        if latest_episode.number > episode_number:
            error_message += (
                "There already exists a more recent episode discussion thread for this "
                "series. New discussion threads for older episodes are disabled."
                + message_ending
            )
            error("Show has a more recent episode thread already")
            return False

    debug("Checking for a candidate episode that was ignored")
    ignored_episode = db.get_ignored_episode(anilist_id, episode_number)

    if not ignored_episode:
        error_message += (
            "Was not able to identify a candidate episode that recently aired for this "
            "piece of media. Please contact my maintainer if you think this is an "
            "error. Information for debugging: anilist_id={}, episode_number={}".format(
                anilist_id, episode_number
            )
        ) + message_ending
        error("No ignored episode candidate found")
        return False

    info(
        "Creating discussion thread for {} Episode {}".format(
            selected_show.name, episode_number
        )
    )

    try:
        import module_episode as m

        m.main(config, db, anilist_id, episode_number)
        db.set_show_enabled(show=selected_show, enabled=True)
        return [selected_show, episode_number]
    except:
        error_message += (
            "Problem with discussion thread creation in episode module" + message_ending
        )
        error("Problem with discussion thread creation in episode module")
        return False
