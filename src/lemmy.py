"""Module for interacting with Lemmy"""

from logging import debug, info, warning, error, exception
from pythorhead import Lemmy

# Initialization

_l = None
_config = None


def init_lemmy(config):
    global _config
    _config = config


def _connect_lemmy():
    if _config is None:
        error("Can't connect to lemmy without a config")
        return None
    lemmy = Lemmy(_config.l_instance, request_timeout=5)
    return lemmy if lemmy.log_in(_config.l_username, _config.l_password) else None


def _ensure_connection():
    global _l
    if _l is None:
        _l = _connect_lemmy()
    return _l is not None


def _get_post_id_from_shortlink(url):
    _ensure_connection()
    return int(url.split("/")[-1])


def _extract_post_response(post_data):
    if (
        not post_data
        or not post_data["post_view"]
        or not post_data["post_view"]["post"]
    ):
        exception(f"Bad post response: {post_data}")
    return post_data["post_view"]["post"]


def _extract_comment_response(comment_data):
    if (
        not comment_data
        or not comment_data["comment_view"]
        or not comment_data["comment_view"]["comment"]
    ):
        exception(f"Base comment response: {comment_data}")
    return comment_data["comment_view"]["comment"]


def _get_host_instance():
    if _config.l_community.find("@") != -1:
        return _config.l_community.split("@")[-1]
    else:
        return _config.l_instance


# Thing doing


def submit_text_post(community, title, body, nsfw):
    _ensure_connection()
    info(f"Submitting post to {community}")
    community_id = _l.discover_community(community)
    if not community_id:
        exception(f"Community {community} not found")
    response = _l.post.create(community_id, title, body=body, nsfw=nsfw)
    return _extract_post_response(response)


def edit_text_post(url, body):
    _ensure_connection()
    post_id = _get_post_id_from_shortlink(url)
    try:
        info(f"Editing post {url}")
        response = _l.post.edit(post_id, body=body)
        return _extract_post_response(response)
    except:
        exception("Failed to submit text post")
        return None


def submit_text_comment(parent_post_url, body):
    """Create a top level comment underneath the provided post."""

    _ensure_connection()
    post_id = _get_post_id_from_shortlink(parent_post_url)
    try:
        info("Submitting comment to post at {}".format(parent_post_url))
        response = _l.comment.create(post_id, body)
        return _extract_comment_response(response)
    except:
        error("Failed to create comment")
        return None


def is_post_url(url):
    """Returns True if the given url is a post url (as opposed to a comment url)."""

    return "post" == url.split("/")[-2]


def is_comment_url(url):
    """Returns True if the given url is a comment url (as opposed to a post url)."""

    return "comment" == url.split("/")[-2]


def get_engagement(url):
    """
    Returns [num_upvotes, num_comments] for a given lemmy url (can be either post or
    comment).
    """

    if is_post_url(url):
        return get_post_engagement(url)
    elif is_comment_url(url):
        return get_comment_engagement(url)
    else:
        exception("Unable to parse provided url as lemmy post or comment.")

    return None


def get_post_engagement(url):
    """Returns [num_upvotes, num_comments] for a given lemmy post url."""

    _ensure_connection()
    post_id = _get_post_id_from_shortlink(url)
    try:
        response = _l.post.get(post_id)
    except:
        exception("Failed to retrieve post")
        return None

    upvotes = response["post_view"]["counts"]["upvotes"]
    comments = response["post_view"]["counts"]["comments"]

    return [upvotes, comments]


def get_post_upvotes(url):
    """Returns the number of upvotes for a given lemmy post url."""

    _ensure_connection()
    post_id = _get_post_id_from_shortlink(url)
    try:
        response = _l.post.get(post_id)
    except:
        exception("Failed to retrieve post")
        return None

    return response["post_view"]["counts"]["upvotes"]


def get_post_comments(url):
    """Returns the number of comments on a given lemmy post url."""

    _ensure_connection()
    post_id = _get_post_id_from_shortlink(url)
    try:
        response = _l.post.get(post_id)
    except:
        exception("Failed to retrieve post")
        return None

    return response["post_view"]["counts"]["comments"]


def get_comment_engagement(url):
    """Returns [num_upvotes, num_comments] for a given lemmy comment url."""

    _ensure_connection()
    comment_id = _get_post_id_from_shortlink(url)
    try:
        response = _l.comment.get(comment_id=comment_id)
    except:
        exception("Failed to retrieve post")
        return None

    upvotes = response["comment_view"]["counts"]["upvotes"]
    children = response["comment_view"]["counts"]["child_count"]

    return [upvotes, children]


def get_comment_upvotes(url):
    """Returns the number of upvotes for a given lemmy comment url."""

    _ensure_connection()
    comment_id = _get_post_id_from_shortlink(url)
    try:
        response = _l.comment.get(comment_id=comment_id)
    except:
        exception("Failed to retrieve post")
        return None

    upvotes = response["comment_view"]["counts"]["upvotes"]

    return upvotes


def get_comment_comments(url):
    """Returns the number of child comments for a given lemmy comment url."""

    _ensure_connection()
    comment_id = _get_post_id_from_shortlink(url)
    try:
        response = _l.comment.get(comment_id=comment_id)
    except:
        exception("Failed to retrieve post")
        return None

    children = response["comment_view"]["counts"]["child_count"]

    return children


# Utilities


def get_shortlink_from_id(id):
    return f"{_get_host_instance()}/post/{id}"


def get_commentlink_from_id(id):
    return f"{_get_host_instance()}/comment/{id}"
