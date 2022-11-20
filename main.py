# TODO
# Re-add 3.5 stuff
# Deduplicate with monster database main.py
# Handle multiple spells on one page
# Get short-desc and maybe subscripts from all spells page


#####################
# CONFIG
#####################


include3_5 = True




#####################
# PROGRAM
#####################


from bs4 import BeautifulSoup, NavigableString
import regex as re
import json
import sys
import traceback
from tqdm import tqdm
from copy import deepcopy
import os



def parseInt(s, stringIfFail=False):
	def _parseInt(s):
		return int(s.strip().replace(",", "").replace("+ ", "+").replace("- ", "-"))

	if stringIfFail:
		try:
			return _parseInt(s)
		except:
			return s.strip()
	else:
		return _parseInt(s)

def parsePage(html, url):
	# Init the object we'll be building
	pageObject = {}

	# Clean up HTML
	regex = r'(?:\r\n|\r|\xad|' + chr(10) + ')+' # Fix weird whitespace in some entries (e.g. Vermlek, Achaierai, Signifer of the Nail, Vampiric Mist)
	html = re.sub(r'(?<=\s+)' + regex + r'|' + regex + r'(?=\s+)', r'', html) # First handle weird whitespace bordering regular whitespace - just delete it
	html = re.sub(regex, r' ', html) # Then handle weird whitespace bordering non-whitespace - replace with a space
	html = re.sub(r'(?<!<\s*br\s*>\s*)<\s*/\s*br\s*>', r'<br/>', html) # Fix broken <br> tags in some pages, e.g. Vilderavn. Uses a variable-width negative lookbehind, so we use the regex module instead of the re module
	html = re.sub(r'[−—–‐‑‒―]|&ndash;|&mdash;', "-", html) # No reason to deal with all these different dashes

	# Parse HTML into an object
	# soup = BeautifulSoup(html, "html.parser")
	soup = BeautifulSoup(html, "html5lib")

	e = soup.select_one("#main table tr td span:not(:empty)")

	# Prepare the HTML for iteration
	e = e.contents
	e.append(soup.new_tag("custom_end")) # Append a special end tag so we don't fall off the end
	i = 0

	# Helper function to skip br tags
	def skipBr(optional=False):
		nonlocal e, i
		if not optional:
			assert e[i].name == "br", url
		elif e[i].name != "br":
			return

		i += 1

		# Skip phantom spaces that sometimes show up after a br, e.g. Young Occult Dragon
		if isinstance(e[i], NavigableString) and e[i].strip() == "":
			i += 1

	# Helper function to split on separator while avoiding splitting on commas inside parens
	def splitP(s, handleAnd=False, sep=r', '):
		o = re.split(sep + r'(?![^()]*\)|[^\[\]]*\])', s)
		if handleAnd and o[-1].strip().startswith("and "):
			o[-1] = o[-1].strip()[4:]
		return o

	# Helper function to collect all following text, handling unpredictable nodes
	# Doesn't stop until it hits a node on the tags list
	# Will advance nodes
	# Use the special "[text]" value for text nodes
	def collectText(tags, skip=["sup"], mark=[]):
		nonlocal e, i
		text = ""
		while i < len(e) - 1: # -1 for the special end tag
			if ("[text]" in tags and isinstance(e[i], NavigableString)) or (not isinstance(e[i], NavigableString) and e[i].name in tags):
				break

			if ("[text]" in skip and isinstance(e[i], NavigableString)) or (not isinstance(e[i], NavigableString) and e[i].name in skip):
				i += 1
				continue

			if isinstance(e[i], NavigableString):
				s = e[i]
			elif e[i].name == "br":
				s = "\n"
			else:
				s = e[i].get_text()

			# Mark if requested
			if ("[text]" in mark and isinstance(e[i], NavigableString)) or (not isinstance(e[i], NavigableString) and e[i].name in mark):
				tagName = "[text]" if isinstance(e[i], NavigableString) else e[i].name
				s = "<" + tagName + ">" + s + "</" + tagName + ">"

			text += s

			i += 1
		return text

	# Helper to unwrap parens
	def unwrapParens(s):
		if s.startswith("(") and s.endswith(")"):
			s = s[1:-1]
		return s.strip()

	# Helper to strip string and trailing char
	def cleanS(s, trailingChar=";"):
		s = s.strip()
		if s[-1] == trailingChar:
			s = s[:-1]
		s = s.strip()
		return s

	# Helper to remove asterisks
	asterisk_options = ["**", "*", "†"] # Should put things like ** before * for regex matching and such
	def handleAsterisk(s):
		return re.sub(r'(?:' + r'|'.join(re.escape(x) for x in asterisk_options) + r')', '', s).strip()

	# TODO: Pre-sweep to find pages with multiple spells
	# titleCount = 0
	# i2 = i
	# isTestingBlock = False
	# while i2 < len(e) - 1:
	# 	if not isinstance(e[i2], NavigableString):
	# 		if isTestingBlock:
	# 			if e[i2].name == "h3" and e[i2].get('class') == ['framing'] and e[i2].get_text() == "Defense":
	# 				titleCount += 1
	# 				isTestingBlock = False
	# 			elif e[i2].name in ["h1", "h2", "h3"]:
	# 				isTestingBlock = False
	# 		else:
	# 			if e[i2].name == "h2" and e[i2].get('class') == ['title']:
	# 				isTestingBlock = True
	# 	i2 += 1
	# if titleCount > 1:
	# 	pageObject["second_statblock"] = True

	# Get name
	assert e[i].name == "h1" and e[i]['class'] == ['title'], url
	pageObject["name"] = e[i].get_text().strip()
	if e[i].find("img", src="images\\PathfinderSocietySymbol.gif") is not None:
		pageObject["is_PFS_legal"] = True
	if e[i].find("img", src="images\\ThreeFiveSymbol.gif") is not None:
		pageObject["is_3.5"] = True
	i += 1

	# Get source
	assert e[i].name == "b" and e[i].get_text() == "Source", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	i += 1
	pageObject["sources"] = []
	while e[i].name == "a":
		s = e[i].get_text()
		result = re.search(r'^(.+?) pg\. (\d+)', s)
		assert not result is None, url + " |" + s + "|"
		pageObject["sources"].append({
			"name": result.group(1).strip(),
			"page": parseInt(result.group(2)),
			"link": e[i]["href"].strip()
		}) # Strip weird whitespace in some entries (e.g. Vermlek)
		i += 1
		if isinstance(e[i], NavigableString): # Skip comma text node
			i += 1
	assert len(pageObject["sources"]) > 0, url
	skipBr()

	# Get school
	assert e[i].name == "b" and e[i].get_text() == "School"
	i += 1
	s = cleanS(collectText(["b", "h3"]))
	result = re.search(r'^(.+?)(?: \((.+?)\))?(?: \[(.+?)\])?$', s)
	assert not result is None, url + " |" + chunk + "|"
	pageObject["school"] = result.group(1).strip()
	if not result.group(2) is None:
		pageObject["subschool"] = result.group(2).strip()
	if not result.group(3) is None:
		s = result.group(3).strip()
		if " or " in s:
			pageObject["descriptors"] = [[x] for x in splitP(s, sep=r', (?:or )?| or ')]
		else:
			pageObject["descriptors"] = splitP(s)
		
	
	# Get level if present - not present for some 3.5 spells and special spells like Fey Boon
	if e[i].name == "b" and e[i].get_text() == "Level":
		i += 1
		s = cleanS(collectText(["h3"]))
		pageObject["level"] = {}

		# Handle potential racial parenthetical at end of level segment
		result = re.search(r'^(.+? \d) \(([^)]+?)\)$', s)
		if not result is None:
			pageObject["racial_affiliation"] = result.group(2).strip()
			s = result.group(1)
		
		for chunk in splitP(s):
			result = re.search(r'^(.+?) (\d)$', chunk)
			assert not result is None, url + " |" + chunk + "|"
			pageObject["level"][result.group(1).strip()] = parseInt(result.group(2))


	# CASTING
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Casting", url
	i += 1

	# Get casting time
	assert e[i].name == "b" and e[i].get_text() == "Casting Time", url
	i += 1
	s = collectText(["br"]).strip()
	pageObject["casting_time"] = s
	skipBr()

	# Get components
	assert e[i].name == "b" and e[i].get_text() == "Components", url
	i += 1
	s = collectText(["h3"]).strip()
	pageObject["components"] = {}
	for p in splitP(s):
		result = re.search(r'^(.+?)(?: \((.+?)\))?(?:/(.+?)(?: \((.+?)\))?)?(; see text)?$', p)
		assert not result is None, url + " |" + p + "|"
		c1 = result.group(1).strip()
		# Check for slash-separated pair
		if not result.group(3) is None:
			c2 = result.group(3).strip()
			# If only the second component has a parenthetical, need content-based check
			if result.group(2) is None and not result.group(4) is None and not c2 in ["M", "F"]:
				pageObject["components"][c1] = result.group(4)
				pageObject["components"][c2] = True
			else:
				pageObject["components"][c1] = (result.group(2).strip() if result.group(2) else True)
				pageObject["components"][c2] = (result.group(4).strip() if result.group(4) else True)
		else:
			pageObject["components"][c1] = (result.group(2).strip() if result.group(2) else True)

		if not result.group(5) is None:
			pageObject["components"]["see_text"] = True

	
	# EFFECT
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Effect", url
	i += 1

	# Get range
	assert e[i].name == "b" and e[i].get_text() == "Range", url
	i += 1
	s = collectText(["br"]).strip()
	pageObject["range"] = s
	skipBr()

	# Skip weird empty line in e.g. Akashic Communion
	if e[i].name == "b" and e[i].get_text() == "":
		i += 1
		collectText(["br"])
		skipBr()
	
	# Get all of target, area, and effect in whatever order
	while e[i].name == "b" and e[i].get_text() != "Duration":
		prop = None
		p = e[i].get_text().strip()
		i += 1
		s = collectText(["br"]).strip()

		# Special case: Mislead
		if p == "Target/Effect":
			result = s.split('/')
			assert len(result) == 2, url
			pageObject["target"] = result[0].strip()
			pageObject["effect"] = result[1].strip()
		elif p in ["Target", "Targets", "Target or Targets", "Targer"]: # Typo for Grim Stalker
			pageObject["target"] = s
		elif p == "Area":
			pageObject["area"] = s
		elif p in ["Target or Area", "Area or Target"]:
			pageObject["target_or_area"] = s
		elif p in ["Effect", "Efect"]: # Typo for Desperate Weapon
			pageObject["effect"] = s
		elif p in ["Target, Effect, or Area", "Target, Effect, Area"]:
			pageObject["target_effect_or_area"] = s
		else:
			print(e)
			assert False, url + " |" + p + "|"

		skipBr()

	# Get duration
	assert e[i].name == "b" and e[i].get_text() == "Duration", url
	i += 1
	s = collectText(["br", "h3"]).strip()
	pageObject["duration"] = s
	skipBr(optional=True)

	# Get saving throw if present
	if e[i].name == "b" and e[i].get_text() == "Saving Throw":
		i += 1
		s = cleanS(collectText(["b", "h3"]))
		pageObject["save"] = s
		# TODO parse save

	# Get spell resistance if present
	if e[i].name == "b" and e[i].get_text() == "Spell Resistance":
		i += 1
		s = collectText(["h3"]).strip()
		pageObject["SR"] = s


	# DESCRIPTION
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Description", url
	i += 1

	# Get description
	s = collectText(["h1", "h2"]).strip()
	pageObject["description"] = s

	return pageObject


if __name__ == "__main__":
	if len(sys.argv) > 1:
		datapath = sys.argv[1]
	else:
		datapath = "data/"

	urls = []
	with open(os.path.join(datapath, "urls.txt")) as file:
		for line in file:
			urls.append(line.rstrip())

	broken_urls = []
	with open("broken_urls.txt") as file:
		for line in file:
			if not line.strip() == "" and not line.strip().startswith("#"):
				broken_urls.append(line.rstrip())

	pageObjects = {}
	for i, url in enumerate(tqdm(urls)):
		# Skip urls pre-marked as broken
		if url in broken_urls:
			continue

		# if url != "https://aonprd.com/SpellDisplay.aspx?ItemName=Cyclic%20Reincarnation":
		# 	continue

		with open(os.path.join(datapath, str(i) + ".html"), encoding='utf-8') as file:
			html = file.read()

		try:
			pageObjects[url] = parsePage(html, url)
		except Exception as e:
			print(url)
			_, _, tb = sys.exc_info()
			traceback.print_tb(tb)
			print(type(e).__name__ + ": " + str(e))

		if not include3_5 and "is_3.5" in pageObjects[url]:
			del pageObjects[url]

	with open(os.path.join(datapath, 'data.json'), 'w') as fp:
		json.dump(pageObjects, fp)