"""Module to add or remove related communities for a show."""

from logging import info, error

from data.models import RelatedCommunity


def main(config, db, *args, **kwargs):
    """Main function of the community module"""

    if len(args) != 4:
        error("Wrong number of arguments for community module")
        raise Exception("Wrong number of arguments")

    commands = ["add", "remove"]

    if args[0].lower() not in commands:
        error("First argument must either be add or remove in the community module")
        raise Exception("Improper argument")

    if args[1].isdigit():
        show = db.get_show(args[1])

        if not show:
            error("Show not present in database")
            raise Exception("Show missing from database")

    else:
        error("Show id must be an integer")
        raise Exception("Improper argument")

    media_id = int(args[1])
    name = args[2]
    instance = args[3]

    rel_comm = RelatedCommunity(media_id=media_id, community=name, instance=instance)

    if args[0].lower() == "add":
        info("Adding related community {}".format(rel_comm))
        db.add_community(rel_comm)
    elif args[0].lower() == "remove":
        info("Removing related community {}".format(rel_comm))
        db.remove_community(rel_comm)
