## Already Enabled Shows

These shows are being tracked and are currently enabled in rikka's database. This means that when a new episode airs a discussion thread will be created unless the previous episode's discussion thread (if it exists) fails to meet the engagement criteria to continue posts for this show.

| Show Name | English Show Name | AniList Link | Most Recent Discussion |
| :-------- | :---------------- | :----------- | :--------------------: |
{% for show in context.enabled %}
| {{show[0]}} | {{show[1]}} | {{show[2]}} | {{show[3]}} |
{% endfor %}
{% raw %}{.dense}{% endraw %}


## Requestable Shows

These shows have had episodes air already, but no thread was created because the show was disabled. It is possible to request a discussion thread be created for these shows by pm'ing the bot. Please see the [Bot User Guide](https://wiki.lemmyanime.com/en/rikka) for detailed instructions on how to request a thread via pm.

| Show Name | English Show Name | AniList Link | Most Recently Episode Number  |
| :-------- | :---------------- | :----------- | :--------------------------: |
{% for show in context.requestable %}
| {{show[0]}} | {{show[1]}} | {{show[2]}} | {{show[3]}} |
{% endfor %}
{% raw %}{.dense}{% endraw %}


## Upcoming Shows

These shows have episodes scheduled to air in the near future but are not already enabled. This means that no discussion thread will be created when it does air. Once an episode has aired, it will move from this table up into the **Requestable Shows** table. At that point, you are able to request the show from rikka via pm ([instructions](https://wiki.lemmyanime.com/en/rikka)). If you want to enable this show in the database prior to this, you can try pm'ing rikka's maintainer [wjs018@ani.social](https://ani.social/u/wjs018) and he can enable it manually in a (relatively) timely manner.

| Show Name | English Show Name | AniList Link | Airing Time (UTC) |
| :-------- | :---------------- | :----------- | :---------------: |
{% for show in context.upcoming %}
| {{show[0]}} | {{show[1]}} | {{show[2]}} | {{show[3]}} |
{% endfor %}
{% raw %}{.dense}{% endraw %}
