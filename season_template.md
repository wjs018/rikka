Below, you can find an index of all the discussion threads for shows from the {{context.season}} {{context.year}} anime season. Not every episode of every show may have a discussion thread. To more easily find the show you are looking for, use the navigation menu for this page or use Ctrl+F.

{% for show in context.shows %}
## {{show[0]}}

{{show[1]}}
{% raw %}{.dense}{% endraw %}


{% endfor %}