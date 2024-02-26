![Rikka, of course](rikka.jpg)

# rikka

Anime episode discussion post bot for use with a [Lemmy](https://join-lemmy.org/) instance. Monitors [AniList](https://anilist.co) for upcoming episodes and creates discussion posts for episodes once they air.

## Table of Contents

- [Requirements](https://github.com/wjs018/rikka?tab=readme-ov-file#requirements)
- [Design Notes](https://github.com/wjs018/rikka?tab=readme-ov-file#design-notes)
- [Megathread Configuration](https://github.com/wjs018/rikka?tab=readme-ov-file#megathread-configuration)
- [Modules](https://github.com/wjs018/rikka?tab=readme-ov-file#modules)
  - [setup](https://github.com/wjs018/rikka?tab=readme-ov-file#the-setup-module)
  - [add](https://github.com/wjs018/rikka?tab=readme-ov-file#the-add-module)
  - [disable](https://github.com/wjs018/rikka?tab=readme-ov-file#the-disable-module)
  - [enable](https://github.com/wjs018/rikka?tab=readme-ov-file#the-enable-module)
  - [remove](https://github.com/wjs018/rikka?tab=readme-ov-file#the-remove-module)
  - [update](https://github.com/wjs018/rikka?tab=readme-ov-file#the-update-module)
  - [edit](https://github.com/wjs018/rikka?tab=readme-ov-file#the-edit-module)
  - [edit_holo](https://github.com/wjs018/rikka?tab=readme-ov-file#the-edit_holo-module)
  - [edit_season](https://github.com/wjs018/rikka?tab=readme-ov-file#the-edit_season-module)
  - [episode](https://github.com/wjs018/rikka?tab=readme-ov-file#the-episode-module)
  - [user_thread](https://github.com/wjs018/rikka?tab=readme-ov-file#the-user_thread-module)
  - [listen](https://github.com/wjs018/rikka?tab=readme-ov-file#the-listen-module)
- [First Time Setup and Usage](https://github.com/wjs018/rikka?tab=readme-ov-file#first-time-setup-and-usage)
- [Automating Rikka](https://github.com/wjs018/rikka?tab=readme-ov-file#automating-rikka)

## Requirements

- Python
  - Tested and run on >= 3.9
  - To my knowlege, requires >= 3.7
- `unidecode`
- `requests`
- `pyyaml`
- `python-dateutil`
- `pythorhead` >= 0.20.0

## Design notes

This project began as I was experimenting with [holo](https://github.com/r-anime/holo) and ran into difficulties with certain aspects of running it. Specifically, I had problems with the detection of new episodes for certain series and could not figure out the root cause. This led me to think about how to avoid having to parse so many different stream providers like holo does and instead rely on a single, reliable API endpoint. After some searching, I found that AniList provides an endpoint for episode airtimes, so I decided to re-engineer holo to solely rely on the AniList API.

I drew heavy inspiration from the holo project and reworked large sections of the codebase to try to make it simpler. This was done by removing large portions of the code pertaining to stream providers and polls. I also made this with Lemmy in mind, so I removed reddit support as I would not be able to test/support reddit using the new code. Additionally, I added several new modules in order to make things a bit easier to manage in an ongoing basis (add, remove, enable, disable, etc.).

The current version of rikka is still missing some features that holo does provide (batch episode threads, show stream/info links in threads, poll creation). Additionally, there are some features I want to implement in the future such as the option to create a daily/weekly megathreads, or the automatic disabling of shows based on engagement.

Finally, this bot is designed to run mostly identically to holo. So, it runs once and then exits so that it plays nice with external schedulers (I simply use cron and a shell script).

## Megathread Configuration

The config file contains several different settings that can impact how rikka makes posts. The most different of these from what is possible with holo is the engagement and megathread settings. The basic idea is that rikka enables the option to create megathreads for shows instead of standalone discussion posts for each episode. Each show would have its own megathread and then each episode would consist of a top-level comment to that post within the megathread. The rationale for this option is to still allow for a place to discuss shows that fewer people might be engaged with, but avoiding having a bunch of standalone discussion posts with little/no engagement that clog up the community feed for others.

The megathread post/comment templates are configured in their own section of the config file. They reuse the same formatting settings as in the post section of the config file (all the `format_*` options). Also in that section is `megathread_episodes` which specifies the number of episode generated top-level comments that should be included in a megathread before creating a new megathread to house future discussions.

Additional settings for enabling/disabling megathreads are found in the options section of the config. That is where the engagement metric thresholds are set. The `min_upvotes` setting specifies how many upvotes a show's previous episode must have in order to remain (or become) a standalone post for the current episode. This check is run at the time a new episode is about to be posted. So, for a show that airs weekly, the previous episode will have had 7 days to collect enough upvotes to try to meet the threshold. If the threshold is not met, then the current episode will instead be placed in the show's megathread. If there is not a previous megathread for the show, then rikka will create one and place the top-level comment into that megathread. If the previous week's episode was posted as a top-level comment in a megathread, then the number of upvotes on that comment will be compared to the threshold.

The `min_comments` setting works similarly but instead of upvotes, it checks the number of comments in the previous episode's discussion thread. If the previous episode was posted in a megathread, then it checks the number of children comment to the previous episode's top-level comment. Episodes must meet both the upvote and comment criteria to have episodes posted as standalone posts. It is possible to have a show be relegated to a megathread, but then be promoted back to standalone posts based on engagement.

To disable megathreads altogether and preserve behavior similar to holo, you can set `min_upvotes = 1` and `min_comments = 0`. These are the default values if these settings are not configured in the config file.

Alternatively, setting `disable_inactive = true` causes rikka to simply disable a show and future discussion posts for shows in which the engagement metric is not met. This means that no megathreads get created nor standalone discussion posts. If the previous episode's enagement metrics aren't met, no post is made and the show is marked as disabled in the database, preventing future posts.

## Modules

### The `setup` Module

To create the initial sqlite database file and correct schema, the setup module should be run at least once. You can specify the database file using the `config.ini` file or using the cli with the `-d` flag. If the file is specified using the cli, that will take precedence over the config file.

If you specify the database file in the config file, then you don't need to specify it on the cli:

```bash
python src/rikka.py -m setup
```

Alternatively, using the cli:

```bash
python src/rikka.py -m setup -d database.sqlite
```

Technically speaking, the setup module is not a separate file like all the other modules. Instead, the work done when invoking the setup module is entirely located in the `src/data/database.py` file (and a local import from `src/data/models.py`).

---

### The `add` Module

You can add shows via cli one at a time by providing the AniList id. It will add the show, enable it, and update the show information with one command.

```bash
python src/rikka.py -m add 130298
```

---

### The `disable` Module

You can disable shows via cli one at a time by providing the AniList id. This will set the `enabled` column for that show in the `Shows` table to 0, thus disabling future comment threads, but will preserve the show information and post history for the show.

```bash
python src/rikka.py -m disable 162893
```

You can also disable all shows marked as nsfw according to AniList's api with one command using `nsfw`.

```bash
python src/rikka.py -m disable nsfw
```

---

### The `enable` Module

It is also possible to re-enable a show in a similar fashion to the disable module.

```bash
python src/rikka.py -m enable 457
```

---

### The `remove` Module

If you want to not only disable, but purge a show and any references to it from the database, that can be done with the remove module and the AniList id.

```bash
python src/rikka.py -m remove 154391
```

It is also possible to just remove all the disabled shows from the database by omitting an id when invoking the remove module.

```bash
python src/rikka.py -m remove
```

Finally, it is possible to remove all shows marked as NSFW by AniList by providing the `nsfw` argument.

```bash
python src/rikka.py -m remove nsfw
```

---

### The `update` Module

The update module will fetch updated show information from the AniList API and populate the database with it. By default, it will only update the shows that are marked as enabled in the database. This can be modified through the cli. Additionally, if the show is marked as finished airing or cancelled by AniList when the api call is made, the show will be disabled in the rikka database. Conversely, if you choose to update all or disabled shows, then shows that you have manually marked as disabled may be re-enabled through the update if they are still airing.

#### Update only enabled shows information

```bash
python src/rikka.py -m update
```

or

```bash
python src/rikka.py -m update enabled
```

#### Update only disabled show information

```bash
python src/rikka.py -m update disabled
```

#### Update show information for all shows (enabled and disabled)

```bash
python src/rikka.py -m update all
```

#### Update specific show by specifying AniList id

```bash
python src/rikka.py -m update 163623
```

---

### The `edit` Module

The edit module can be used to add/update many shows at once by parsing a yaml file of AniList ids. An example file is included in `season_configs/example.yaml`. The file contains a list of shows to add/update as enabled and a list of shows to add/update as disabled.

If the show already exists in the database, then its information will be updated with a fresh pull from AniList and its enabled status will be updated depending on which list it is in inside the yaml file. If the show does not already exist in the database, then the show information will be fetched from AniList and added to the database. Also, its enabled status will be set according to which list it is in inside the yaml.

```bash
python src/rikka.py -m edit season_configs/example.yaml
```

---

### The `edit_holo` Module

The edit_holo module is similar to the edit module above, but instead parses a yaml file that is formatted for use by [holo](https://github.com/r-anime/holo). An example file is included at `season_configs/example_holo.yaml`. The only parts of this file that are used by rikka are the AniList urls so that the AniList id can be extracted. Thus, if there is not an AniList url provided for a show, it will not be added to the rikka database. After extracting AniList ids from the yaml file, the rikka database is populated through fresh pulls on the AniList API. This module is included for convenience since the holo project does such excellent work cataloguing shows. Usage is identical to the edit module just with a different module name.

```bash
python src/rikka.py -m edit_holo season_configs/example_holo.yaml
```

---

### The `edit_season` Module

The edit_season module is a way to automatically add all the media from a given season to rikka's database. This works by retrieving all the media for a given season and year from the AniList api and then applying the show discovery criteria to them as configured in the config file. This means there are a couple caveats to this module:

- The season and year for a given show are limited to what is in AniList's api. So, shows that run multiple cours are typically going to be listed under the first cour in which they begin airing. As an example, Frieren: Beyond Journey's End is listed in AniList's api as a Fall 2023 show, but not a Winter 2024 show despite airing in both seasons.
- Related to the caveat above, long-running shows might be listed under a very different season than might be intuitively expected. As an example, One Piece, despite still airing as of writing this in 2024, is listed in the Fall 1999 season.
- Show discovery must be enabled for this module to load any results into the database. This entails setting `show_discovery = true` in the `[options]` section of the config file. For more info on the show discovery criteria, see the comments in the example config file.

To use the edit_season module, you must provide two arguments:

1. The season - one of `winter`, `spring`, `summer`, or `fall`
2. The year

So, to load all the shows matching the discovery criteria from the Fall 2023 season, simply run:

```bash
python src/rikka.py -m edit_season fall 2023
```

### The `episode` Module

The episode module is the primary module that is used to make discussion posts and the default module that is run if no module is specified. First, it will query AniList for upcoming episodes of all enabled shows in the database. Then, it will make discussion posts for episodes that were previously found as upcoming, but the current time is later than the scheduled airing time.

```bash
python src/rikka.py -m episode
```

or

```bash
python src/rikka.py
```

Also, if enabled in the config file, the episode module can discover new shows that match the specified criteria and populate the database with the show's information.

An alternative way to use the episode module is to manually specify which show and episode number a discussion thread should be made for. This will cause rikka to ignore engagement metrics and create a standalone post for the show/episode. There are two arguments that need to be provided:

1. The AniList id number
2. The episode number

A caveat to this is that the show must already exist in the database. So, if you want to manually create a discussion thread for a new show that doesn't exist, you must first add the show through the add module and then create the discussion thread. So, an example of this usage would be:

```bash
python src/rikka.py 457 80
```

or

```bash
python src/rikka.py -m episode 457 80
```

Both of these commands do the same thing. They add an episode 80 discussion thread link to the database for the show with an Anilist id of 457 (Mushishi). If there is an existing entry in the database for that show/episode combo, it will be overwritten.

### The user_thread Module

The user_thread module is used to manually add user-created (non-editable) discussion threads to the database. This allows the thread to show up in the table of links for a show, but it will not try to edit the post and cause errors to happen after each new post is made. There are a couple different arguments you can provide:

1. The url for the post
2. The episode number (optional, see below)
3. The AniList id for the show (optional, see below)

Arguments 2 and 3 above are optional and can be inferred from the post information, but only if the post is formatted in a certain way. Specifically:

- The episode number can be inferred from the post title if it contains the text "Episode XX" where XX is a number.
- The AniList id can be inferred if the body of the post contains a link to the AniList page for the series.

So, you can use this thread in a couple different ways.

1. If the post title specifies the episode number and the post body has an AniList link:

```bash
python src/rikka.py -m user_thread https://lemmy.instance.tld/post/1234
```

2. If the post body has an AniList link, but the post title does not specify the episode number:

```bash
python src/rikka.py -m user_thread https://lemmy.instance.tld/post/1234 80
```

3. If neither the episode number nor AniList link are provided:

```bash
python src/rikka.py -m user_thread https://lemmy.instance.tld/post/1234 80 457
```

### The listen Module

The listen module allows for users to private message the bot and request the creation of a discussion thread. The message to the bot needs to contain two elements:

1. The AniList link to the piece of media
2. Text specifying which episode the thread should be for, in the formate "Episode ##"

So, if you were requesting an episode discussion thread for episode 80 of Mushishi, the message to rikka would simply be:

> https://anilist.co/anime/457/Mushishi/ Episode 80

When running the listen module, the lemmy user specified in the config file will check for unread private messages and then parse them, creating episode discussion posts as required. If an episode thread is created in this way, the show is also set to enabled in the database so that future episode discussion threads will be created, subject to engagement criteria. The listen module will pull the 20 most recent private messages, so make sure to run it at a high enough frequency to accomodate the volume of expected messages. It is run without arguments:

```bash
python src/rikka.py -m listen
```

## First Time Setup and Usage

I have tried to walk through the steps of how to set up and run rikka for the first time.

1. Clone the repo into a folder on the target machine and navigate into the root folder.

```bash
git clone https://github.com/wjs018/rikka.git
cd rikka
```

2. Copy and rename the example config file.

```bash
cp config.ini.example config.ini
```

3. Edit the config file as desired. By default, it is set up to simulate the posting behavior of holo in which each episode gets a separate discussion post and extra features like automated show discovery, or engagement driven megathreads are turned off. The `[lemmy]` section needs to be filled out with the details of the community and instance to post to as well as the posting user's username and password.

```ini
[lemmy]
instance = https://your.instance.com
community = your_community
username = your_username
password = your_password
```

Comments have been added into the example config file to try to make clear what the different options do.

4. Once the config file is finished, make sure the python dependencies are installed. It is recommended to utilize a venv (or similar) dedicated to rikka for this purpose. Setting up and activating a venv is left as an activity for the reader. Once you have activated your venv you can install the dependencies:

```bash
pip install -r requirements.txt
```

5. Next, the database needs to be set up. This is done by rikka using the `setup` module.

```bash
python src/rikka.py -m setup
```

6. After building the database, it needs to be populated with shows to monitor. This can be done in multiple ways. The simplest way is to configure the show discovery options in the config file before running the `episode` module in the next step. The relevant options are found in the `[options]` section of the config file.

- To enable show discovery, first specify `show_discovery = true`.
- Then, the types of shows can be specified through adding them to `new_show_types`. The default value of `tv ona` tends to account for most media released each season, but the full list of options are included in the comments of the config file for reference.
- To prevent discovery of explicit, adult media, you can make sure that `nsfw_discovery = false`
- Finally, to include media from multiple countries of origin, you can specify the `countries` value. The default of `JP` will only discover media made in Japan. To add another country, just expand this list. For example a value of `JP CN` would discover media made in both Japan and China.

Another simple method to populate the database is to use the `edit_season` module. This uses the configured show discovery options and then automatically populates the database with all the matching shows from a given season and year. You can see more about how to use it in the [edit_season module section](https://github.com/wjs018/rikka?tab=readme-ov-file#the-edit_season-module) above.

Another method to add shows to the database is to make use of the various edit/add modules. First, the `edit` module provides a couple different ways to add shows to the database. You can see usage examples of the edit module in the [edit module section](https://github.com/wjs018/rikka?tab=readme-ov-file#the-edit-module) above.

The `edit_holo` module is specifically made to be able to load shows into the database through the use of yaml files that have been produced and formatted for the [holo](https://github.com/r-anime/holo) project. To find a yaml file for a specific season, you can browse the holo repository in the `season_configs` folder. Download the yaml files for the season(s) that you want to load into rikka's database and then use the `edit_holo` module to load each of them (see [module section above](https://github.com/wjs018/rikka?tab=readme-ov-file#the-edit_holo-module) for instructions).

The final option to populate the database with shows is through the use of the `add` module. This adds a single show at a time. Refer to the [module section above](https://github.com/wjs018/rikka?tab=readme-ov-file#the-add-module) for usage instructions.

7. Once either show discovery is enabled and configured and/or shows have been loaded into the database through the use of the edit/add modules, it is time to run the `episode` module. The first time this module is run, no posts will be made to lemmy. rikka only has the capability to look forward in time for upcoming episodes that will air. So, the first time the `episode` module is run, it will populate the database with all the upcoming episodes that are going to air over the time period specified in the config file (default of 7 days). Because there were no existing episodes in the database with a timestamp in the past, no discussion threads will be generated. To run the `episode` module, simply run rikka with no arguments:

```bash
python src/rikka.py
```

The `episode` module is the module that finds newly aired episodes, makes discussion posts, and (if enabled) discovers new shows. So, to automate rikka, the episode module should be run with a fairly high frequency. For my personal usage, I use cron to run the episode module every 15 minutes.

8. Occasionally, you might want to update the metadata of shows that are in the database. This is done with the `update` module. It does not need to be run as frequently as the `episode` module. Once per week is more than enough. Also, it is not necessary to update after adding a new show/shows. When a new show is added to the database using either edit module, the add module, or through show discovery, the metadata is updated automatically. For details on the `update` module, see the [module section above](https://github.com/wjs018/rikka?tab=readme-ov-file#the-update-module).

```bash
python src/rikka.py -m update
```

## Automating rikka

I have a couple best practices I have developed over the course of my time working on and running rikka that I thought I would share. Firstly, this is the frequency with which I run the different modules on my version of rikka:

| Module                                             |     Run freq     | Command                                          |
| :------------------------------------------------- | :--------------: | :----------------------------------------------- |
| `episode`:<br>Find new episodes                    | every 15 minutes | `python src/rikka.py`                            |
| `update`:<br>Update show information               |    every week    | `python src/rikka.py -m update all`              |
| `edit_season`:<br>Load or modify shows in database | once per season  | `python src/rikka.py -m edit_season season year` |
| Others                                             |      manual      | module dependent                                 |

I schedule these through the use of a shell script and cron on my server. A simple example version of the shell script I use for the `episode` module follows (change folders/paths to fit your environment).

```sh
# Activate venv
source /home/rikka-user/environments/rikka/bin/activate

# Navigate to folder
cd /home/rikka-user/rikka/

# Run episode module
python src/rikka.py
```

I then schedule this to run every 15 minutes with logging written out to a file using cron. Below, I have written out my crontab entry:

```
*/15 * * * * /home/rikka-user/run_rikka.sh >> /home/rikka-user/rikka-log.log 2>&1
```

This would log all the output of rikka to the `rikka-log.log` file. So, to prevent an ever-ballooning log file, I set up logrotate to keep things in check. This is done by adding a block at the end of `/etc/logrotate.conf` on most servers. I use the following config block on my server:

```
/home/rikka-user/rikka-log.log {
        missingok
        notifempty
        maxsize 10M
        daily
        create 0644 rikka-user rikka-user
        rotate 4
}
```

This retains logs from the previous 4 days to aid in troubleshooting if any issues come up.

Finally, the last thing I do when automating rikka is to set up a healthcheck through a service like healthchecks.io. I won't go into the details of how to interface with their service and leave it as an exercise to the reader, but it is a way to check in with a server each time your script executes. If it fails to check in after a specified amount of time, then you can configure alerts that are sent to you. In my case, through using healthchecks.io, all I need to do is add a line at the end of my shell script from above:

```sh
# Send an HTTP GET request with curl to signal script execution:
curl -m 10 --retry 5 https://hc-ping.com/your-specific-endpoint-here
```
