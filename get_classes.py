from bs4 import BeautifulSoup
import requests
import re
from urllib.parse import quote
import os
from tqdm.auto import tqdm
from pathlib import Path
import json


if __name__ == "__main__":
    url_classes = "https://aonprd.com/Classes.aspx"
    url_prestige = "https://aonprd.com/PrestigeClasses.aspx"
    url_mythic = "https://aonprd.com/MythicPaths.aspx"
    outfile = "data/class_hds.json"

    classes = {}

    # Create output directory if it doesn't exist
    Path(os.path.dirname(outfile)).mkdir(parents=True, exist_ok=True)

    # Classes
    # =======

    # Class list page
    html = requests.get(url_classes).text
    soup = BeautifulSoup(html, "html.parser")
    elems = soup.select("#MainContent_AllClassLabel a")
    entries = [(e.get_text().strip(), e['href'].split("=")[0] + "=" + quote(e['href'].split("=")[1], safe='/()')) for e in elems]

    # Prestige class list page
    html = requests.get(url_prestige).text
    soup = BeautifulSoup(html, "html.parser")
    elems = soup.select("#MainContent_GridViewPrestigeClasses td:first-child a")
    entries += [(e.get_text().strip(), e['href'].split("=")[0] + "=" + quote(e['href'].split("=")[1], safe='/()')) for e in elems]

    # Get hit dice from individual pages
    for name, url in tqdm(entries):
        name = name.strip()
        if name == "Familiar":  # Special case - no hit die
            classes[name] = None
            continue

        if not url.startswith("https://aonprd.com/"):
            url = "https://aonprd.com/" + url
        html = requests.get(url).text
        soup = BeautifulSoup(html, "html.parser")
        # Normal classes
        elem = soup.select_one("#MainContent_DataListTypes_LabelName_0")
        result = re.search(r"Hit Die: d(\d+)\.", elem.get_text())
        if not result is None:
            classes[name] = int(result.group(1))
            continue
        # Weird classes (e.g. Companion)
        elems = soup.find_all('b', string="HD")
        assert len(elems) > 0, url
        for elem in elems: # Find the first one in the overall span (so not the table header)
            if elem.parent.name != "span":
                continue
            result = re.search(r"\(d(\d+)\)", elem.nextSibling.get_text())
            assert not result is None, url
            classes[name] = int(result.group(1))
            break
        else:
            assert False, url

    # Mythic paths all give no hit dice - we encode this as a d0
    html = requests.get(url_mythic).text
    soup = BeautifulSoup(html, "html.parser")
    elems = soup.select("#main > h1 a")
    for e in elems:
        classes[e.get_text()] = 0
    
    # Add some manual ones
    classes.update({
        "Geokineticist": classes["Kineticist"],
        "Hydrokineticist": classes["Kineticist"],
        "Abjurer": classes["Wizard"],
        "Conjurer": classes["Wizard"],
        "Diviner": classes["Wizard"],
        "Enchanter": classes["Wizard"],
        "Evoker": classes["Wizard"],
        "Illusionist": classes["Wizard"],
        "Necromancer": classes["Wizard"],
        "Transmuter": classes["Wizard"]
    })

    # Write the results to disk
    with open(outfile, 'w') as fp:
        json.dump(classes, fp)
