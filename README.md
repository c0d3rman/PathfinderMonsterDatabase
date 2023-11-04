# PathfinderMonsterDatabase
A database of all monsters in Pathfinder 1e, created by parsing aonprd.com

## Setup

Run the following line to install all required libraries:
```
pip install -r requirements.txt
```

## Downloading and parsing the data
1. Run `download_page_list.py` in order to download the list of monster entry URLs:

```
python download_page_list.py
```

By default, this will get all monsters, NPCs, and mythic monsters.
You can also specify a URL as a parameter to the script to get just the monster entries from there (e.g. https://aonprd.com/Monsters.aspx?Letter=All).
Alternatively, you can just create the `data/urls.txt` file yourself.

2. Run `download_pages.py` to download each individual monster entry page:

```
python download_pages.py
```

This will take a bit. The script limits itself to a maximum of 5 requests a second to not overload aonprd.com, but you can adjust this number if you are still having trouble.
You can also give additional parameters to the script if you want to pull from a different file other than `data/urls.txt`, or if you want to write the results to a folder other than `data`.

3. Run `get_classes.py` to download a list of all classes, which will be used for parsing the data.

4. Run `main.py` to parse the raw HTML into a database:

```
python main.py
```

This script is where the magic happens. If you want to adjust anything from adding special cases, changing how parsing is done, or changing the output format of the database, you'll need to change it here.
The script will pull from the `data` folder by default, but you can give it a different folder as an argument (where it will look for a `urls.txt` and appropriately named html files).
This script will also look for the `broken_urls.txt` file, which contains all URLs to ignore, usually because their HTML is broken or their monster statblocks are malformed in some way.
If you want to exclude 3.5e monster entries, change the `include3_5` variable at the top of this script to `False`. When finished, this script produces a `data.json` containing the database.

## Exploring the data

Run `explore_data.py` in order to look through the data:
```
python -i explore_data.py
```

This script will load up the database and create some useful dictionaries for accessing it, which you can explore using python's interactive mode. It also gives you some useful utility functions.

The dictionaries it creates are:

- `d` - the database. Index it with a url, and you can see the statblock of the monster at that URL. Example usage:
```
>>> pprint(d["https://aonprd.com/MonsterDisplay.aspx?ItemName=Wolf"])
{'AC': {'AC': 14,
        'components': {'dex': 2, 'natural': 2},
        'flat_footed': 12,
        'touch': 12},
 'BAB': 1,
 'CMB': 2,
 'CMD': 14,
 'CMD_other': '18 vs. trip',
 'CR': 1,
 'HP': {'HP': 13, 'long': '2d8+4'},
 'XP': 400,
 'ability_scores': {'CHA': 6,
                    'CON': 15,
                    'DEX': 15,
                    'INT': 2,
                    'STR': 13,
                    'WIS': 12},
 'alignment': 'N',
 'attacks': {'melee': [[{'attack': 'bite',
                         'bonus': [2],
                         'entries': [[{'damage': '1d6+1'}, {'effect': 'trip'}]],
                         'text': 'bite +2 (1d6+1 plus trip)'}]]},
 'desc_long': 'Wandering alone or in packs, wolves sit at the top of the food '
              'chain. Ferociously territorial and exceptionally wide-ranging '
              'in their hunting, wolf packs cover broad areas. A wolf’s wide '
              'paws contain slight webbing between the toes that assists in '
              'moving over snow, and its fur is a thick, water-resistant coat '
              'ranging in color from gray to brown and even black in some '
              'species. Its paws contain scent glands that mark the ground as '
              'it travels, assisting in navigation as well as broadcasting its '
              'whereabouts to fellow pack members. Generally, a wolf stands '
              'from 2-1/2 to 3 feet tall at the shoulder and weighs between 45 '
              'and 150 pounds, with females being slightly smaller.',
 'desc_short': 'This powerful canine watches its prey with piercing yellow '
               'eyes, darting its tongue across sharp white teeth.',
 'ecology': {'environment': 'cold or temperate forests',
             'organization': 'solitary, pair, or pack (3-12)',
             'treasure_type': 'none'},
 'feats': [{'name': 'Skill Focus (Perception)'}],
 'initiative': {'bonus': 2},
 'saves': {'fort': 5, 'ref': 5, 'will': 1},
 'senses': {'low-light vision': True, 'scent': True},
 'size': 'Medium',
 'skills': {'Perception': {'_': 8},
            'Stealth': {'_': 6},
            'Survival': {'_': 1, 'scent tracking': 5},
            '_racial_mods': {'Survival': {'when tracking by scent': 4}}},
 'sources': [{'link': 'http://paizo.com/products/btpy8auu?Pathfinder-Roleplaying-Game-Bestiary',
              'name': 'Pathfinder RPG Bestiary',
              'page': 278}],
 'speeds': {'base': 50},
 'title1': 'Wolf',
 'title2': 'Wolf',
 'type': 'animal'}
```

- `unique_leaves`. This dictionary shows the unique values of every leaf in the database. You can use it when looking for what values a certain leaf can take - e.g. see all speeds, sizes, senses, and so on. Example usage:\
```
>>> p(unique_leaves["speeds"]["fly"])
[
  10,
  15,
  20,
  30,
  40,
  45,
  50,
  60,
  70,
  80,
  90,
  100,
  110,
  120,
  150,
  160,
  180,
  200,
  250,
  480
]
```

- `unique_leaves_lookups`. This dictionary is identical to `unique_leaves`, except that each value instead points to a list of all URLs that have that value for that property.
This dictionary is useful once you've found something of interest in `unique_leaves` and want to see where it appears. For example, let's say after running the previous query you want to find out which entries have a 480-foot fly speed - example usage:
```
>>> p(unique_leaves_lookup["speeds"]["fly"][480])
[
  "https://aonprd.com/MonsterDisplay.aspx?ItemName=Anemos"
]
```

- `unique_leaves_counts`. This dictionary is identical to `unique_leaves, except that it shows how many times each unique leaf appears. It's useful when wanting to get a sense of the relative rarity of different properties. For example, let's say you wanted to know common creatures of different sizes are in Pathfinder - example usage:
```
>>> p(unique_leaves_counts["size"])
{
  "Huge": 348,
  "Medium": 1471,
  "Tiny": 208,
  "Diminutive": 58,
  "Small": 364,
  "Large": 757,
  "Fine": 22,
  "Gargantuan": 154,
  "Colossal": 86
}
```


The utility functions this script provides are:

- `p` and `pprint` - for pretty-printing dictionaries, use whichever you prefer. `pprint` produces more compact output, `p` does better sorting.

- `search` - for searching through a dictionary or sub-dictionary. You can use this function to find something across multiple different parts of the hierarchy.
For example, if you wanted to find all entries that mention the Limited Wish spell, you could run
```
>>> p(search(d, "limited wish", caseSensitive=False))
```
This will find any entry that has `limited wish` in it, whether it appears in the Spells or Spell-Like Abilities blocks, in the description, or wherever else. (It will also show you where in the entry the "limited wish" string appears.)

**This does not search the raw entries** - only the database - so if you search for stuff like "Caster Level", for example, you won't find every single monster with a Spells block, since that block is parsed into data that does not contain the string "caster level".

You can change case sensitivity with the `caseSensitive` parameter (default `True`), and/or you can pass `regex=True` to use a regex instead of a string to search.
