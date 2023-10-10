![Rikka, of course](rikka.jpg)

# rikka

Anime episode discussion post bot for use with a [Lemmy](https://join-lemmy.org/) instance. Monitors [AniList](https://anilist.co) for upcoming episodes and creates discussion posts for episodes once they air.

## Table of Contents

* [Requirements](https://github.com/wjs018/rikka#requirements)
* [Design Notes](https://github.com/wjs018/rikka#design-notes)
* [Modules](https://github.com/wjs018/rikka#modules)
  * [setup](https://github.com/wjs018/rikka#the-setup-module)
  * [add](https://github.com/wjs018/rikka#the-add-module)
  * [disable](https://github.com/wjs018/rikka#the-disable-module)
  * [enable](https://github.com/wjs018/rikka#the-enable-module)
  * [remove](https://github.com/wjs018/rikka#the-remove-module)
  * [update](https://github.com/wjs018/rikka#the-update-module)
  * [edit](https://github.com/wjs018/rikka#the-edit-module)
  * [edit_holo](https://github.com/wjs018/rikka#the-edit_holo-module)
  * [episode](https://github.com/wjs018/rikka#the-episode-module)
* [Usage](https://github.com/wjs018/rikka#usage)
* [Module Run Frequency](https://github.com/wjs018/rikka#module-run-frequency)


## Requirements

* Python
  * Tested and run on >= 3.9
  * To my knowlege, requires >= 3.7
* `unidecode`
* `requests`
* `pyyaml`
* `pythorhead`

## Design notes

This project began as I was experimenting with [holo](https://github.com/r-anime/holo) and ran into difficulties with certain aspects of running it. Specifically, I had problems with the detection of new episodes for certain series and could not figure out the root cause. This led me to think about how to avoid having to parse so many different stream providers like holo does and instead rely on a single, reliable API endpoint. After some searching, I found that AniList provides an endpoint for episode airtimes, so I decided to re-engineer holo to solely rely on the AniList API.

I drew heavy inspiration from the holo project and reworked large sections of the codebase to try to make it simpler. This was done by removing large portions of the code pertaining to stream providers and polls. I also made this with Lemmy in mind, so I removed reddit support as I would not be able to test/support reddit using the new code. Additionally, I added several new modules in order to make things a bit easier to manage in an ongoing basis (add, remove, enable, disable, etc.).

The current version of rikka is still missing some features that holo does provide (new show discovery, batch episode threads, show stream/info links in threads, poll creation). Additionally, there are some features I want to implement in the future such as the option to create a daily/weekly megathread and have some shows in the megathread vs. having a separate discussion post. I would also like to eventually implement engagement tracking. Basically keeping track of previously created posts and recording up/down votes as well as number of comments to potentially automatically enable/disable shows based on engagement.

Finally, this bot is designed to run mostly identically to holo. So, it runs once and then exits so that it plays nice with external schedulers (I simply use cron and a shell script).

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

---

### The `enable` Module

It is also possible to re-enable a show in a similar fashion to the disable module.

```bash
python src/rikka.py -m enable 457
```

---

### The `remove` Module

If you want to not only disable, but purge a show and any references to it from the database, that can be done with the remove module and the Anilist id.

```bash
python src/rikka.py -m remove 154391
```

It is also possible to just remove all the disabled shows from the database by omitting an id when invoking the remove module.

```bash
python src/rikka.py -m remove
```

---

### The `update` Module

The update module will fetch updated information from the AniList API and populate the database with it. By default, it will only update the shows that are marked as enabled in the database. This can be modified through the cli. Additionally, if the show is marked as finished airing or cancelled by AniList when the api call is made, the show will be disabled in the rikka database.

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

The edit_holo module is similar to the edit module above, but instead parses a yaml file that is formatted for use by [holo](https://github.com/r-anime/holo). An example file is included at `season_configs/example_holo.yaml`. The only parts of this file that is used by rikka are the AniList urls so that the AniList id can be extracted. Then, the rikka database is populated through fresh pulls on the AniList API. This module is included for convenience since the holo project does such excellent work cataloguing shows. Usage is identical to the edit module just with a different module name.

```bash
python src/rikka.py -m edit_holo season_configs/example_holo.yaml
```

---

### The `episode` Module

The episode module is the primary module that is used to make discussion posts. First, it will query AniList for upcoming episodes of all enabled shows in the database. Then, it will make discussion posts for episodes that were previously found as upcoming, but the current time is later than the scheduled airing time.

```bash
python src/rikka.py -m episode
```

## Usage

1. Update config file with your desired configuration including lemmy details. Make sure the sommunity you're posting to is a personal test community while you are confirming everything works for you.

```ini
[lemmy]
instance = https://your.instance.com
community = your_community
username = your_username
password = your_password
```

2. Set up the database by running `python src/rikka.py -m setup`
3. Enable the shows that should get discussion posts one of two ways:
   1. Load list of AniList ids by yaml file `python src/rikka.py -m edit season_configs/yaml_file_of_ids.yaml`
   2. Load yaml config file formatted for [holo](https://github.com/r-anime/holo) `python src/rikka.py -m edit_holo season_configs/holo_formatted_file.yaml`
4. The bot is now ready to post threads with `python src/rikka.py`

### Module Run Frequency

Module|Run freq|Command
:--|:-:|:--
Episode:<br>Find new episodes|high|`python src/rikka.py`
Update:<br>Update show information|low|`python src/rikka.py -m update`
Edit:<br>Load or modify shows in database|manual|`python src/rikka.py -m edit [show-config]`
Setup:<br>Set up database|once|`python src/rikka.py -m setup`
Others|manual|See module descriptions
