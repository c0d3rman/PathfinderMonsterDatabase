#####################
# CONFIG
#####################


include3_5 = True

"""
TODO
- The current handling of \r and other weird newlines introduces a lot of spaces in the wrong places. Need better solution. See Lastwall Border Scout
- Go over the TBD broken urls
- Swap to manual list of skills for racial mod handling (so I can do better parsing of e.g. "Survival (in snow)" vs "Craft (traps)")
- Look over skills for problems
- Merge melee and ranged attack processing

Handle some special cases:
Strange melee attacks
- https://aonprd.com/MonsterDisplay.aspx?ItemName=Malbolgian%20Cerberi - double plus
- https://aonprd.com/MonsterDisplay.aspx?ItemName=Accomplice%20Devil%20(Hesperian) - extra parens
- https://aonprd.com/MonsterDisplay.aspx?ItemName=Draugr%20Pirate - weird space/non-ascii character instead of X (might have a similar issue in others)
Strange ranged attacks
- https://aonprd.com/MonsterDisplay.aspx?ItemName=Canopy%20Creeper - grab before plus
"""



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



sizes = ['Fine', 'Diminutive', 'Tiny', 'Small', 'Medium', 'Large', 'Huge', 'Gargantuan', 'Colossal']

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
	html = html.replace("\r\n", " ").replace("\r", " ").replace(chr(10), " ").replace('\xad', '') # Fix weird whitespace in some entries (e.g. Vermlek, Achaierai, Signifer of the Nail, Vampiric Mist)
	html = re.sub(r'(?<!<\s*br\s*>\s*)<\s*/\s*br\s*>', r'<br/>', html) # Fix broken <br> tags in some pages, e.g. Vilderavn. Uses a variable-width negative lookbehind, so we use the regex module instead of the re module
	html = re.sub(r'[−—–‐‑‒―]|&ndash;|&mdash;', "-", html) # No reason to deal with all these different dashes

	# Parse HTML into an object
	soup = BeautifulSoup(html, "html.parser")
	e = soup.select_one("div#main table tr td span")

	# Handle superscripts with commas/semicolons in them - just split them into multiple superscripts
	for tag in e.find_all("sup"):
		if not re.search(r'[;,] ', tag.get_text()) is None:
			for s in re.split(r'[;,] ', tag.get_text()):
				if s.strip() == "": # Eliminate empty superscripts, mostly for Dagon
					continue

				newTag = soup.new_tag('sup')
				newTag.string = s
				tag.insert_after(newTag)
			tag.extract()

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

	# Sweep for asterisk lines, then return back to the beginning to start the real parse
	while i < len(e) - 1:
		if not isinstance(e[i], NavigableString) and e[i].name == "br":
			if isinstance(e[i+1], NavigableString):
				result = re.search(r'^(' + r'|'.join(re.escape(x) for x in asterisk_options) + r') ', str(e[i+1]).strip())
				if result is None:
					i += 1
					continue

				asterisk = result.group(1)
			elif e[i+1].name == "sup" and e[i+1].get_text().strip() in asterisk_options:
				asterisk = e[i+1].get_text().strip()
			else:
				i += 1
				continue

			e[i].extract() # Remove the br

			# Collect the text and remove tags along the way
			s = ""
			while i < len(e) - 1:
				if not isinstance(e[i], NavigableString) and e[i].name in ["br", "h1", "h2", "h3"]:
					break

				if isinstance(e[i], NavigableString):
					s += e[i]
				else:
					s += e[i].get_text()

				e[i].extract()

			s = s.strip()

			if not "asterisk" in pageObject:
				pageObject["asterisk"] = {}

			result = re.search(r'^' + re.escape(asterisk) + r'\s*(.+)$', s)
			assert not result is None, url + " |" + s + "|"
			assert not result.group(1) in pageObject["asterisk"], url + " |" + s + "|"
			pageObject["asterisk"][asterisk] = result.group(1)
		else:
			i += 1
	i = 0

	# Skip preamble sections, like in Mythic Nalfeshnee
	while not (e[i].name == "h1" and ((e[i+1].name == "i" and e[i+2].name == "h2") or e[i+1].name == "h2")):
		i += 1

	# Pre-sweep to find pages with multiple statblocks
	titleCount = 0
	i2 = i
	isTestingBlock = False
	while i2 < len(e) - 1:
		if not isinstance(e[i2], NavigableString):
			if isTestingBlock:
				if e[i2].name == "h3" and e[i2].get('class') == ['framing'] and e[i2].get_text() == "Defense":
					titleCount += 1
					isTestingBlock = False
				elif e[i2].name in ["h1", "h2", "h3"]:
					isTestingBlock = False
			else:
				if e[i2].name == "h2" and e[i2].get('class') == ['title']:
					isTestingBlock = True
		i2 += 1
	if titleCount > 1:
		pageObject["second_statblock"] = True

	# Get main title
	assert e[i].name == "h1" and e[i]['class'] == ['title'], url
	pageObject["title1"] = e[i].get_text()
	if e[i].find("img", src="images\\ThreeFiveSymbol.gif") is not None:
		pageObject["is_3.5"] = True
	i += 1

	# Get short description if present
	if e[i].name == "i":
		pageObject["desc_short"] = e[i].get_text()
		i += 1

	# Get statblock title & CR
	assert e[i].name == "h2" and e[i]['class'] == ['title'], url
	result = re.search(r'^(.+) CR ([0-9/-]+?)(?:/MR (\d+))?$', e[i].get_text())
	assert not result is None, "CR-finding Regex failed for " + url
	pageObject["title2"] = result.group(1)
	pageObject["CR"] = parseInt(result.group(2), stringIfFail=True)
	if pageObject["CR"] == "-":
		pageObject["CR"] = None
	if not result.group(3) is None:
		pageObject["MR"] = parseInt(result.group(3))
	i += 1

	# Get source
	assert e[i].name == "b" and e[i].get_text() == "Source", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	i += 1
	pageObject["sources"] = []
	while e[i].name == "a":
		pageObject["sources"].append({"name": e[i].get_text(), "link": e[i]["href"].strip()}) # Strip weird whitespace in some entries (e.g. Vermlek)
		i += 1
		if isinstance(e[i], NavigableString): # Skip comma text node
			i += 1
	assert len(pageObject["sources"]) > 0, url
	skipBr()

	# Get XP if present (might be blank if there is none, such as with a Butterfly/Moth)
	if e[i].name == "b" and e[i].get_text() == "XP":
		i += 1
		assert isinstance(e[i], NavigableString), url
		s = handleAsterisk(e[i].strip())
		if s == "":
			pageObject["XP"] = None
		else:
			pageObject["XP"] = parseInt(s)
		i += 1
		skipBr()

	# Get race and class levels if present
	s = collectText(["br"]).strip()
	skipBr()
	if isinstance(e[i], NavigableString): # If we're looking at a string instead of the bold "Init", then we have a race/class line
		result = re.search(r'^(.+?) (.+)?$', s)
		assert not result is None, "Race and Class Regex failed for " + url
		pageObject["race"] = result.group(1)
		pageObject["classes"] = result.group(2).split("/")
		
		# Fetch the actual alignment line this time
		s = collectText(["br"])
		skipBr()
	# Special case - has a unique line after alignment line
	elif e[i].name == "a" and url == "https://aonprd.com/MonsterDisplay.aspx?ItemName=Ugash-Iram":
		collectText(["br"])
		skipBr()

	# Get alignment, size, type, subtypes
	result = re.search(r'^(.+) (' + "|".join(sizes) + r') ([^(]+)(?: \((.+)\))?$', handleAsterisk(s))
	assert not result is None, "Alignment Line Regex failed for " + url + " |" + handleAsterisk(s) + "|"
	pageObject["alignment"] = result.group(1)
	pageObject["size"] = result.group(2)
	pageObject["type"] = result.group(3)
	if result.group(4) is not None:
		pageObject["subtypes"] = splitP(result.group(4))

	# Get initiative
	assert e[i].name == "b" and e[i].get_text() == "Init", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	s = collectText("b").strip()
	result = re.search(r'^([+-]\s*\d+)(?:/([+-]\s*\d+))?\s*(?:\(([+-]\s*\d+)\s+(.+?)\))?\s*(?:[,;]\s*(.+?)\s*)?;$', s)
	assert not result is None, "Initiative Regex failed for " + url + " |" + s + "|"
	if not result.group(2) is None: # Check for dual initiative
		pageObject["initiative"] = {"bonus": [parseInt(result.group(1)), parseInt(result.group(2))]}
	else:
		pageObject["initiative"] = {"bonus": parseInt(result.group(1))}
	if not result.group(3) is None: # Different initiative modifier in some instances (e.g. Formian Taskmaster, "(+6 with hive mind)")
		pageObject["initiative"]["other"] = {result.group(4): parseInt(result.group(3))}
	if not result.group(5) is None: # Initiative abilities
		pageObject["initiative"]["ability"] = result.group(5)

	# Get senses
	assert e[i].name == "b" and e[i].get_text() == "Senses", url
	i += 1
	s = collectText(["h3", "br"]).strip()
	if not "is_3.5" in pageObject:
		result = re.search(r'^(?:(.+)[;,])?\s*Perception\s+([+-]\s*\d+.*?)$', s) # Regex handles broken formatting on pages like Demonologist that use a comma instead of a semicolon. Space before Perception is variable length because of the typos in Elder Air Elemental and Scarlet Walker, and space inside number because of Mirror Serpent
		assert not result is None, "Senses Regex failed for " + url
		perceptionSkill = parseInt(result.group(2), stringIfFail=True) # Save perception skill to combine with skills section later
	else:
		result = re.search(r'^(?:(.+)[;,])?\s*Listen\s+([+-]\s*\d+),\s*Spot\s+([+-]\s*\d+)$', s)
		assert not result is None, "Senses Regex failed for " + url
		listenSkill = parseInt(result.group(2), stringIfFail=True)
		spotSkill = parseInt(result.group(3), stringIfFail=True)
	if result.group(1) is not None:
		entries = splitP(result.group(1), sep=r'[,;]')
		pageObject["senses"] = {}
		for entry in entries:
			entry = handleAsterisk(entry.strip())
			result = re.search(r'^(.+?)\s+(\d+)\s*ft\s*\.?\s*(?:\((.+?)\))?$', entry)
			if not result is None:
				pageObject["senses"][result.group(1).lower()] = parseInt(result.group(2))
				if not result.group(3) is None:
					pageObject["senses"][result.group(1).lower() + "_other"] = result.group(3).strip()
			else:
				pageObject["senses"][entry.lower()] = True

	skipBr(optional=True)

	# Get auras if present
	if e[i].name == "b" and e[i].get_text() == "Aura":
		i += 1
		pageObject["auras"] = []
		for aura in splitP(collectText(["h3", "br"]).strip()):
			aura_dict = {}
			result = re.search(r'^(.+?)(?:\s+\((.+?)\))?$', aura)
			assert not result is None, "Aura Regex failed for " + url
			aura_dict['name'] = handleAsterisk(result.group(1).strip())
			if not result.group(2) is None:
				parts = splitP(result.group(2), sep=r'[,;]')
				for part in parts:
					part = part.strip()

					result = re.search(r'^(\d+)[ -](?:ft\.?|feet)(?: radius)?$', part)
					if not result is None:
						aura_dict['radius'] = parseInt(result.group(1), stringIfFail=True)
						continue

					result = re.search(r'^DC (\d+)(?: (Fort|Ref|Will))?$|^(Fort|Ref|Will) DC (\d+) negates$', part)
					if not result is None:
						if not result.group(1) is None:
							aura_dict['DC'] = parseInt(result.group(1))
							if not result.group(2) is None:
								aura_dict['DC_type'] = result.group(2)
						else:
							aura_dict['DC'] = parseInt(result.group(4))
							aura_dict['DC_type'] = result.group(3)
						continue

					result = re.search(r'^\d+(?:d\d+)? (?:round|minute|hour|day)s?$', part)
					if not result is None:
						aura_dict['duration'] = part
						continue

					if not 'other' in aura_dict:
						aura_dict['other'] = []
					aura_dict['other'].append(part)
			pageObject['auras'].append(aura_dict)

	# DEFENSE
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Defense", url
	i += 1

	# Get AC
	assert e[i].name == "b" and e[i].get_text() == "AC", url
	i += 1
	s = collectText(["br"]).strip()
	result = re.search(r'^(-?\d+)[,;]\s+touch\s+(-?\d+)[,;]\s+flat-?footed\s+(-?\d+)(?:\s*;?\s*\((.+?)\))?(?:;?\s*(.+))?\.?$', s) # Accepts ; as well as , because of broken formatting on pages like Bugbear Lurker. Skip broken formatting trailing period in e.g. Flying Fox
	assert not result is None, "AC Regex failed for " + url
	pageObject["AC"] = parseInt(result.group(1))
	pageObject["AC_touch"] = parseInt(result.group(2))
	pageObject["AC_flatfooted"] = parseInt(result.group(3))
	if not result.group(5) is None:
		pageObject["AC_other"] = result.group(5)
		if pageObject["AC_other"].startswith("(") and pageObject["AC_other"].endswith(")"):
			pageObject["AC_other"] = pageObject["AC_other"][1:-1]
	if not result.group(4) is None:
		entries = splitP(result.group(4), sep=r'[,;] ')
		pageObject["AC_components"] = {}
		for entry in entries:
			entry = entry.strip() # Fixes whitespace issues in e.g. Malsandra (probably caused by \r handling)
			result = re.search(r'^([+-]\d+)\s+(.+)$', entry)
			if not result is None:
				pageObject["AC_components"][result.group(2).lower().strip()] = parseInt(result.group(1))
			else:
				if not "other" in pageObject["AC_components"]:
					pageObject["AC_components"]["other"] = []
					pageObject["AC_components"]["other"].append(entry)
	skipBr()

	# Get HP, and fast healing / regeneration / other HP abilities if present
	assert e[i].name == "b" and e[i].get_text() == "hp", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	s = handleAsterisk(e[i].strip())
	result = re.search(r'^(\d+)(?:\s+each)?\s*\((?:(\d+)\s+HD;\s+)?(.+?)\)(?:[;,] (.+))?$', s) # Supports , instead of ; for broken formatting on pages like Egregore
	assert not result is None, "HP Regex failed for " + url
	pageObject["HP"] = parseInt(result.group(1))
	pageObject["HP_long"] = result.group(3)
	if result.group(2) is not None:
		pageObject["HD"] = parseInt(result.group(2))
	if result.group(4) is not None:
		result2 = re.search(r'^(fast healing|regeneration)\s+(\d+)(?:\s*\((.+?)\))?$', result.group(4).strip())
		if not result2 is None:
			pageObject[result2.group(1).replace(" ", "_")] = parseInt(result2.group(2))
			if not result2.group(3) is None:
				pageObject[result2.group(1).replace(" ", "_") + "_weakness"] = result2.group(3).strip()
		else:
			pageObject["HP_other"] = result.group(4)
	i += 1
	skipBr()

	# Get saves
	pageObject["saves"] = {}
	for save in ["Fort", "Ref", "Will"]:
		assert e[i].name == "b" and e[i].get_text() == save, url
		i += 1
		assert isinstance(e[i], NavigableString), url
		s = cleanS(e[i], trailingChar=',')
		i += 1
		result = re.search(r'^([+-]?\s*\d+)\s*(?:\((.+?)\))?\s*(?:;\s+(.+?))?$', s)
		assert not result is None, save + " Save Regex failed for " + url + "\tInput: |" + s + "|"
		pageObject["saves"][save.lower()] = parseInt(result.group(1))
		if not result.group(2) is None:
			pageObject["saves"][save.lower() + "_other"] = result.group(2).strip()

		# On the last save (Will) check for a post-save semicolon covering misc. bonuses that apply to every save type
		if not save == "Will":
			assert result.group(3) is None, url
		elif not result.group(3) is None:
			pageObject["saves"]["other"] = result.group(3).strip()
	skipBr(optional=True)

	# Get defensive abilities if present
	if e[i].name == "b" and e[i].get_text() == "Defensive Abilities":
		i += 1
		pageObject["defensive_abilities"] = splitP(handleAsterisk(cleanS(collectText(["b", "br", "h3"]))))

	# Get DR if present
	if e[i].name == "b" and e[i].get_text() == "DR":
		i += 1
		s = cleanS(collectText(["b", "br", "h3"]))
		entries = splitP(s, sep=r'(?:,|\s+and)(?:\s+DR)?\s+(?=\d+/)')
		pageObject["DR"] = []
		for entry in entries:
			entry = entry.strip()
			entrydict = {}
			result = re.search(r'^(\d+)/\s*(.+?)\s*(?:\((?:(?:(.+?), )?(\d+) (?:hp|hit points|points)|(.+?))?\))?$', entry)
			assert not result is None, url + " |" + entry + "|"
			entrydict["amount"] = parseInt(result.group(1))
			entrydict["weakness"] = result.group(2)
			if not result.group(4) is None:
				entrydict["max_absorb"] = parseInt(result.group(4))
			if not result.group(3) is None:
				entrydict["other"] = result.group(3)
			elif not result.group(5) is None:
				entrydict["other"] = result.group(5)
			pageObject["DR"].append(entrydict)

	# Get immunities if present
	if e[i].name == "b" and e[i].get_text() == "Immune":
		i += 1
		pageObject["immunities"] = splitP(cleanS(collectText(["h3", "br", "b"])).strip(), handleAnd=True)

	# Get resistances if present
	if e[i].name == "b" and e[i].get_text() == "Resist":
		i += 1
		s = cleanS(collectText(["h3", "br", "b"])) # collectText specifically for Arcanotheign

		pageObject["resistances"] = {}

		# Special case: First Blade, ability in the Resist section
		result = re.search(r'^(.+); (.+)$', s)
		if not result is None:
			pageObject["resistances"]["_ability"] = result.group(2).strip()
			s = result.group(1).strip()

		entries = splitP(s, sep=r'(?:,?\s+and\s+|,)')
		for entry in entries:
			entry = entry.strip() # Handles strange whitespace in cases like Black Magga (probably caused by \r handling)
			result = re.search(r'^(.+?)\s+(\d+)(?:\s*\((.+?)\))?$', entry)
			if result is None: # Custom resistances, e.g. The Whispering Tyrant
				pageObject["resistances"][entry] = True
			else:
				pageObject["resistances"][result.group(1).lower()] = parseInt(result.group(2))
				if not result.group(3) is None:
					pageObject["resistances"][result.group(1).lower() + "_other"] = result.group(3).strip()

	# Get SR if present
	if e[i].name == "b" and e[i].get_text() == "SR":
		i += 1
		assert isinstance(e[i], NavigableString), url
		pageObject["SR"] = parseInt(cleanS(e[i]), stringIfFail=True)
		i += 1

	skipBr(optional=True)

	# Get weaknesses if present
	if e[i].name == "b" and e[i].get_text() == "Weaknesses":
		i += 1
		pageObject["weaknesses"] = splitP(collectText(["h3"]).strip()) # Skip leading space


	# OFFENSE
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Offense", url
	i += 1

	# Get speed
	assert e[i].name == "b" and e[i].get_text() == "Speed", url
	i += 1
	s = collectText(["br"])
	# Handle entries like Solar that have one set of speeds normally and another in armor
	parts = re.split(r'; (?![^()]*\))', s) # Use a special split to avoid splitting on semicolons inside parens
	assert len(parts) <= 2, url
	s = parts[0]
	entries = splitP(s)
	pageObject["speeds"] = {}
	for j, entry in enumerate(entries):
		result = re.search(r'^\s*(?:(.+?)\s+)?(\d+)\s*ft\s*\.\s*(?:\((.+?)\))?$', entry.strip())
		if not result is None:
			t = result.group(1)
			if j != 0:
				assert t is not None, url
			elif t is None:
				t = "base"
			t = t.lower()
			pageObject["speeds"][t] = parseInt(result.group(2))
			if result.group(3) is not None:
				t2 = t + "_other"
				v = result.group(3).strip()
				if t == "fly" and v.lower() in ["clumsy", "poor", "average", "good", "perfect"]:
					v = v.lower()
					t2 = "fly_maneuverability"
				pageObject["speeds"][t2] = v
		else:
			if not "other" in pageObject["speeds"]:
				pageObject["speeds"]["other"] = []
			pageObject["speeds"]["other"].append(entry.strip())

		if len(parts) > 1:
			pageObject["speeds"]["other_semicolon"] = parts[1].strip()

	skipBr()

	# Get melee attacks if present
	if e[i].name == "b" and e[i].get_text() == "Melee":
		i += 1
		s = handleAsterisk(collectText(["h3", "b"]).strip())

		if s != "---": # Special case - no melee attack (currently only present in Lar)
			pageObject["attacks_melee"] = []
			groups = splitP(s, sep=r'(?<=\))[;,]?\s+or\s+')
			for group in groups:
				entries = splitP(group.strip())
				group_list = []
				for entry in entries:
					entry = entry.strip()
					attack_dict = {"text": entry}

					# First, process the body and separate the parenthetical
					result = re.search(r'^(\d+)?\s*(.+?)\s*((?:[+-]\d+/)*[+-]\d+)?(?:\s+melee)?(\s+touch)?\s*(?:\(([^)]+)\))?$', entry)
					assert not result is None, "Melee Attack Regex 1 failed for " + url
					if not result.group(1) is None:
						attack_dict["count"] = parseInt(result.group(1))
					attack_dict["attack"] = result.group(2)
					if not result.group(3) is None:
						attack_dict["bonus"] = [parseInt(x) for x in splitP(result.group(3), sep=r'/')]
					if not result.group(4) is None:
						attack_dict["touch"] = True

					# Now, process the parenthetical
					if not result.group(5) is None:
						p = result.group(5).strip()
						result = re.search(r'^(\d+(?:d\d+)?(?:[+-]\d+)?)?\s*(?:/(\d+\s*-\s*\d+))?\s*(?:/[×x]\s*(\d))?\s*(?:(.+?)?\s*plus\s+([^)]+?)|\s+(.+?))?(?:(?:, )?DC (\d+))$', p)
						if result is None:
							attack_dict["effects"] = p
						else:
							if result.group(1) is None:
								assert result.group(2) is None and result.group(3) is None and result.group(4) is None and result.group(6) is None, url
							else:
								attack_dict["damage"] = result.group(1)
								if not result.group(2) is None:
									attack_dict["crit_range"] = result.group(2)
								if not result.group(3) is None:
									attack_dict["crit_multiplier"] = parseInt(result.group(3))
								if not result.group(4) is None or not result.group(6) is None:
									assert result.group(4) is None or result.group(6) is None, urls # Can't have both at the same time, so make sure one is None
									if result.group(4) is None:
										attack_dict["damage_type"] = result.group(6)
									else:
										attack_dict["damage_type"] = result.group(4)
								if not result.group(5) is None:
									attack_dict["effects"] = result.group(5)
								if not result.group(7) is None:
									attack_dict["DC"] = parseInt(result.group(7))

					group_list.append(attack_dict)
					
				pageObject["attacks_melee"].append(group_list)
	
	# Get ranged attacks if present
	if e[i].name == "b" and e[i].get_text() == "Ranged":
		i += 1
		pageObject["attacks_ranged"] = []
		groups = splitP(handleAsterisk(collectText(["h3", "b"]).strip()), sep=r'(?<=\))[;,]?\s+or\s+')
		for group in groups:
			entries = splitP(group.strip())
			group_list = []
			for entry in entries:
				entry = entry.strip()
				attack_dict = {"text": entry}

				# First, process the body and separate the parenthetical
				result = re.search(r'^(\d+)?\s*(.+?)\s*((?:[+-]\d+/)*[+-]\d+)?(?:\s+(?:ranged\s+)?(touch))?\s*(?:\(([^)]+)\))?$', entry)
				assert not result is None, "Ranged Attack Regex 1 failed for " + url
				if not result.group(1) is None:
					attack_dict["count"] = parseInt(result.group(1))
				attack_dict["attack"] = result.group(2)
				if not result.group(3) is None:
					attack_dict["bonus"] = [parseInt(x) for x in splitP(result.group(3), sep=r'/')]
				if result.group(4) == "touch":
					attack_dict["touch"] = True

				# Now, process the parenthetical
				if not result.group(5) is None:
					p = result.group(5).strip()
					result = re.search(r'^(\d+(?:d\d+)?(?:[+-]\d+)?)?\s*(?:/(\d+\s*-\s*\d+))?\s*(?:/[×x]\s*(\d))?\s*(?:(.+?)?\s*plus\s+([^)]+?)|\s+(.+?))?(?:(?:, )?DC (\d+))$', p)
					if result is None:
						attack_dict["effects"] = p
					else:
						if result.group(1) is None:
							assert result.group(2) is None and result.group(3) is None and result.group(4) is None and result.group(6) is None, url
						else:
							attack_dict["damage"] = result.group(1)
							if not result.group(2) is None:
								attack_dict["crit_range"] = result.group(2)
							if not result.group(3) is None:
								attack_dict["crit_multiplier"] = parseInt(result.group(3))
							if not result.group(4) is None or not result.group(6) is None:
								assert result.group(4) is None or result.group(6) is None, urls # Can't have both at the same time, so make sure one is None
								if result.group(4) is None:
									attack_dict["damage_type"] = result.group(6)
								else:
									attack_dict["damage_type"] = result.group(4)
							if not result.group(5) is None:
								attack_dict["effects"] = result.group(5)
							if not result.group(7) is None:
									attack_dict["DC"] = parseInt(result.group(7))

				group_list.append(attack_dict)
			pageObject["attacks_ranged"].append(group_list)

	# Get space if present
	if e[i].name == "b" and e[i].get_text() == "Space":
		i += 1
		assert isinstance(e[i], NavigableString), url
		result = re.search(r'^(?:(\d+)|(2\s*-?\s*1/2)|(1/2))\s*(?:ft\.?|feet)$', cleanS(e[i], ",").strip())
		assert not result is None, "Space Regex failed for " + url
		if not result.group(2) is None:
			pageObject["space"] = 2.5
		elif not result.group(3) is None:
			pageObject["space"] = 0.5
		else:
			pageObject["space"] = parseInt(result.group(1))
		i += 1

	# Get reach if present
	if e[i].name == "b" and e[i].get_text() == "Reach":
		i += 1
		assert isinstance(e[i], NavigableString), url
		
		result = re.search(r'^(?:(\d+)|(2\s*-?\s*1/2)|(1/2))\s*(?:ft\.?|feet)(?:\s*\(?([^)]+)\)?)?$', cleanS(e[i], ",").strip())
		assert not result is None, "Reach Regex failed for " + url
		if not result.group(2) is None:
			pageObject["reach"] = 2.5
		elif not result.group(3) is None:
			pageObject["reach"] = 0.5
		else:
			pageObject["reach"] = parseInt(result.group(1))
		if not result.group(4) is None:
			pageObject["reach_other"] = result.group(4).strip()
		i += 1

	# Skip br if present
	skipBr(optional=True)

	# Get special attacks if present
	if e[i].name == "b" and e[i].get_text() == "Special Attacks":
		i += 1
		pageObject["attacks_special"] = [x.strip() for x in splitP(handleAsterisk(collectText(["h3", "br"]).strip()))]
		skipBr(optional=True)

	# Handle all spell-related blocks, including spells, spell-like abilities, and more
	while True:
		if e[i].name == "b" and ("Spells" in e[i].get_text() or "Extracts" in e[i].get_text()):
			key = "spells"
			result = re.search(r'^(?:([\w ]+) )?(?:Spells|Extracts) (Prepared|Known)$', e[i].get_text().strip())
			assert not result is None, "Spell Class Regex failed for " + url
			source = result.group(1)
			spell_type = result.group(2).lower()
			if source is None:
				# If no class was listed, but we have only one class, use that one
				if "classes" in pageObject and pageObject["classes"] is not None and len(pageObject["classes"]) == 1:
					result = re.search(r'^(.+?)\s+\d+$', pageObject["classes"][0].strip())
					if not result is None:
						source = result.group(1).title()
				else: # No idea. e.g. Noble (Knight), where the spells are Paladin spells, but he also has the Aristocrat class
					source = "?"
		elif e[i].name == "b" and e[i].get_text().strip().endswith("Spell-Like Abilities"):
			key = "spell_like_abilities"
			source = e[i].get_text().replace("Spell-Like Abilities", "").strip().lower() # Get type of spell-like ability (notably "Domain")
			if source == "":
				source = "default"
		elif e[i].name == "b" and e[i].get_text().strip() == "Kineticist Wild Talents Known":
			key = "kineticist_wild_talents"
		elif e[i].name == "b" and (e[i].get_text().strip() == "Psychic Magic" or e[i].get_text().strip() == "Psychic Magic (Sp)"):
			key = "psychic_magic"
			source = "default"
		else:
			break

		i += 1

		# Handle spell-related header
		if key != "kineticist_wild_talents":
			# Init the first time we encounter a key of a given type (since we may encounter e.g. multiple spell blocks)
			if not key in pageObject:
				pageObject[key] = {"entries": []}

			# Init the first time
			if not "sources" in pageObject[key]:
				pageObject[key]["sources"] = []

			sourcedict = {"name": source}
			if key == "spells":
				sourcedict["type"] = spell_type

			assert isinstance(e[i], NavigableString), url

			result = re.search(r'^\((.+)\)$', e[i].strip())
			assert not result is None, "Spell-Related Header Base Regex failed for " + url
			entries = splitP(result.group(1).strip(), sep=r'[;,]') # Handles corrupted formatting for , instead of ; like in Ice Mage
			i += 1

			# The CL should always be there
			result = re.search(r'^(?:CL|caster level)\s+(\d+)(?:\w{2})?$', entries.pop(0), re.IGNORECASE) # Ignore case for Nochlean
			assert not result is None, "Spell-Related Header CL Regex failed for " + url
			sourcedict["CL"] = parseInt(result.group(1))

			# Optional entries
			for entry in entries:
				entry = entry.strip()

				# Concentration
				result = re.search(r'^conc(?:entration|\.):?\s+([+-]\d+)$', entry, re.IGNORECASE) # Concentration colon for Executioner Devil (Munagola)
				if not result is None:
					sourcedict["concentration"] = parseInt(result.group(1))
					continue

				# Arcane spell failure
				result = re.search(r'^(?:(?:(\d+%) (?:arcane )?spell failure(?: chance)?)|(?:arcane )?spell failure(?: chance)? (\d+%))$', entry, re.IGNORECASE)
				if not result is None:
					if result.group(1) is not None: # There are two capture groups that might capture the failure chance
						sourcedict["failure_chance"] = result.group(1)
					elif result.group(2) is not None:
						sourcedict["failure_chance"] = result.group(2)
					continue

				# Save DC ability score
				result = re.search(r'^(?:save DCs are )?(\w+)-based$', entry, re.IGNORECASE)
				if not result is None:
					sourcedict["DC_ability_score"] = result.group(1)
					continue

				# Ranged touch attack modifier (present on Vampire and some 3.5 entries)
				result = re.search(r'^([+-]\d+) (ranged|touch|ranged touch)?$', entry, re.IGNORECASE)
				if not result is None:
					if result.group(2) == "touch":
						sourcedict["touch_attack_melee"] = parseInt(result.group(1))
					else:
						sourcedict["touch_attack_ranged"] = parseInt(result.group(1))
					continue

				raise Exception("Spell-Related Header Entry Regexes failed for " + url + "\tEntry: |" + entry + "|")

		skipBr()

		if key == "spells" or key == "spell_like_abilities":
			while isinstance(e[i], NavigableString): # Go over lines
				s = collectText(["h3", "br"], skip=[], mark=["sup"]).strip()
				skipBr(optional=True)

				# Special case: Bloodless Vessel
				if s == "Varies":
					pageObject[key]["varies"] = True
					break

				# Line regex
				if key == "spells":
					result = re.search(r'^(\d+)(?:\w{2})?\s*(?:\((?:(at[ -]will)|(\d+)(?:/day)?)\))?\s*(-)(?![^()]*\))', s, re.IGNORECASE) # Make sure not to get a dash inside parens e.g. Young Occult Dragon
					assert not result is None, url + " |" + s + "|"

					level = parseInt(result.group(1))
					if not result.group(2) is None:
						slots = "at-will"
					elif not result.group(3) is None:
						slots = parseInt(result.group(3))
					else:
						slots = None

					if not slots is None:
						if not "slots" in sourcedict:
							sourcedict["slots"] = {}
						sourcedict["slots"][level] = slots

					entries = splitP(s[result.end(4):].strip())
				else:
					# Special case: Elder Sphinx, Gynosphinx, and Akilep Lady of Stone
					is_symbol_special = False
					result = re.search(r'^(.+?-)any (.+?) of the following: (.+?); all symbols last for (.+?) maximum$', s, re.IGNORECASE)
					if not result is None:
						pageObject[key]["symbols_special"] = {
							"max_duration": result.group(4),
							"num_selected": result.group(2)
						}
						s = result.group(1) + result.group(3)
						is_symbol_special = True

					result = re.search(r'^([^-]*?at-will[^-]*?|.+?)\s*-\s*(.+)$', s, re.IGNORECASE) # Specially allow at-will before dash like in Kasa-obake
					assert not result is None, url + " |" + s + "|"

					freq = result.group(1)
					entries = splitP(result.group(2))
				
				for entry in entries: # Go over each spell in the line
					entry = entry.strip()
					entrydict = {}

					# Handle superscripts
					regex = r'(<sup>(.+?)</sup>)'
					result = re.search(regex, entry)
					while not result is None:
						s = result.group(2).strip()
						entry = entry[:result.start(1)] + entry[result.end(1):] # Strip out all superscripts
						entry = entry.strip()
						if s == "D":
							entrydict["is_domain_spell"] = True
						elif s == "S":
							entrydict["is_spirit_spell"] = True
						elif s == "M":
							entrydict["is_mythic_spell"] = True
						else:
							if not "superscripts" in entrydict:
								entrydict["superscripts"] = []
							entrydict["superscripts"].append(s)
						result = re.search(regex, entry) # repeat regex to look for next <sup>

					# Finish symbol special case handling from before
					if key == "spell_like_abilities" and is_symbol_special:
						entrydict["symbols_special"] = True

					result = re.search(r'^([^)(]+?)\s*(?:\(([^)]+)\))?\s*(?:\(([^)]+)\))?$', entry) # Some entries have double-parenthetical, e.g. Solar
					assert not result is None, "Single Spell or Spell-Like Ability Regex failed for " + url + " |" + entry + "|"
					name = handleAsterisk(result.group(1).strip())
					parenthetical = result.group(2)
					parenthetical2 = result.group(3)
					entrydict["name"] = name
					entrydict["source"] = source
					if key == "spells":
						entrydict["level"] = level
					else:
						entrydict["freq"] = freq

					entrydict_orig = entrydict.copy() # Save a copy in case we give up processing
					if not parenthetical is None:
						parenthetical = parenthetical.strip()
						entrydict_orig["paren_text"] = parenthetical
					if not parenthetical2 is None:
						parenthetical2 = parenthetical2.strip()
						entrydict_orig["paren_text2"] = parenthetical2
					giveup = False

					# Handle special case: summon spell-like ability
					if key == "spell_like_abilities" and not parenthetical is None and entrydict["name"].lower().startswith("summon") and parenthetical.startswith("level "): # startswith summon to account for stuff like "summon bees" in Thriae Seer, startswith level to dodge things like Summon Monster
						assert parenthetical2 is None, url + " |" + parenthetical2 + "|"
						result = re.search(r'^level (\d+), (.+)$', parenthetical)
						assert not result is None, "Summon Spell-Like Ability Regex failed for " + url + " |" + parenthetical + "|"
						entrydict["level"] = parseInt(result.group(1))
						entrydict["summons"] = []
						s = result.group(2).strip()

						# Check for percentage-at-end format, e.g. Accuser Devil (Zebub)
						commonChance = None
						result = re.search(r'^(.+?), (\d+%)$', s)
						if not result is None:
							s = result.group(1).strip()
							commonChance = result.group(2)

						pentries = splitP(s, sep="(?:,? or|,)")
						for pentry in pentries:
							result = re.search(r'^(?:(\d+(?:d\d+)?) )?(.+?)(?: (\d+%))?$', pentry.strip())
							assert not result is None, "Summon Spell-Like Ability Entry Regex failed for " + url + " |" + s + "|"
							summondict = {"name": result.group(2).strip()}
							if not result.group(1) is None:
								summondict["amount"] = parseInt(result.group(1), stringIfFail=True)
							if not commonChance is None:
								assert result.group(3) is None, "Two conflicting chances for a summon entry in " + url
								summondict["chance"] = commonChance
							elif not result.group(3) is None:
								summondict["chance"] = result.group(3)
							entrydict["summons"].append(summondict)

					# Handle parenthetical entries
					elif not parenthetical is None:
						pentries = splitP(parenthetical, sep=r'[;,] ') # semicolon for Storm Sorcerer
						if not parenthetical2 is None:
							pentries += splitP(parenthetical2, sep=r'[;,] ')
						for pentry in pentries:
							pentry = pentry.strip()

							result = re.search(r'^DC\s+(\d+)$', pentry)
							if not result is None:
								if "DC" in entrydict:
									giveup = True
									break
								entrydict["DC"] = parseInt(result.group(1))
								continue

							if key == "spells":
								if pentry.isdigit():
									if "count" in entrydict:
										giveup = True
										break
									entrydict["count"] = parseInt(pentry)
									continue
							else:
								result = re.search(r'^CL (\d+)(?:\w{2})?$', pentry)
								if not result is None:
									if "CL" in entrydict:
										giveup = True
										break
									entrydict["CL"] = parseInt(result.group(1))
									continue

							if "other" in entrydict:
								giveup = True
								break
							entrydict["other"] = pentry

					if giveup:
						entrydict = entrydict_orig
					pageObject[key]["entries"].append(entrydict)

			# Skip "D for Domain spell" chunk if present
			if e[i].name == "b" and e[i].get_text().strip() == "D":
				i += 1 # Skip "D"
				assert isinstance(e[i], NavigableString) and e[i].strip().lower() == "domain spell;", url
				i += 1 # Skip "Domain spell; "
				skipBr(optional=True)

			# Get domain if present (separate from the previous chunk because inquisitors get domains but no domain spells)
			# Rarely there's a domain with the spell-like abilities, e.g. Clockwork Priest
			if e[i].name == "b" and (e[i].get_text().strip() == "Domain" or e[i].get_text().strip() == "Domains"):
				i += 1
				sourcedict["domains"] = splitP(handleAsterisk(cleanS(collectText(["br", "b", "h3"])).lower())) # collectText because there might be a superscript splitting the text tag, like in Usij Cabalist. cleanS because there might be a semicolon like in Mythic Lich
				skipBr(optional=True)

			# Get bloodline if present
			if e[i].name == "b" and e[i].get_text().strip() == "Bloodline":
				i += 1
				sourcedict["bloodline"] = handleAsterisk(cleanS(collectText(["br", "b", "h3"])).lower()) # collectText in case of superscripts / italics, e.g. Kobold Guilecaster. cleanS because there might be a semicolon like in Kortash Khain
				skipBr(optional=True)

			# Skip "M for mythic spell" chunk if present
			if e[i].name == "b" and e[i].get_text().strip() == "M":
				i += 1
				assert isinstance(e[i], NavigableString) and (e[i].strip().lower() == "mythic spell" or e[i].strip().lower() == "mythic spells"), url
				i += 1
				skipBr(optional=True)

			# Skip "S for spirit magic spell" chunk if present
			if e[i].name == "b" and e[i].get_text().strip() == "S":
				i += 1 # Skip "S"
				assert isinstance(e[i], NavigableString) and e[i].strip().lower() == "spirit magic spell;", url
				i += 1 # Skip "spirit magic spell; "
				skipBr(optional=True)

			# Get spirit if present (separate from the previous chunk just in case)
			if e[i].name == "b" and e[i].get_text().strip() == "Spirit":
				i += 1
				sourcedict["spirit"] = collectText(["br", "b", "h3"]).lower().strip() # collectText in case of superscripts
				skipBr(optional=True)

			# Get opposition schools if present
			if e[i].name == "b" and (e[i].get_text().strip() == "Opposition Schools" or e[i].get_text().strip() == "Prohibited Schools"):
				i += 1
				sourcedict["opposition_schools"] = splitP(collectText(["br", "b", "h3"]).lower().strip())
				skipBr(optional=True)

			# Get patron if present
			if e[i].name == "b" and e[i].get_text().strip() == "Patron":
				i += 1
				sourcedict["patron"] =collectText(["br", "b", "h3"]).lower().strip()
				skipBr(optional=True)

			# Get mystery if present
			if e[i].name == "b" and e[i].get_text().strip() == "Mystery":
				i += 1
				sourcedict["mystery"] = collectText(["br", "b", "h3"]).lower().strip()
				skipBr(optional=True)

			# Get psychic discipline if present
			if e[i].name == "b" and e[i].get_text().strip() == "Psychic Discipline":
				i += 1
				sourcedict["psychic_discipline"] = collectText(["br", "b", "h3"]).lower().strip()
				skipBr(optional=True)

			# Get mythic restriction if present
			if e[i].name == "sup" and e[i].get_text() == "M":
				sourcedict["mythic_restriction"] = collectText(["br", "b", "h3"]).strip()
				skipBr(optional=True)

		elif key == "kineticist_wild_talents":
			assert not key in pageObject, url
			pageObject[key] = {}
			while isinstance(e[i], NavigableString):
				result = re.search(r'^(.+?)\s*-\s*(.+)$', collectText(["h3", "br"]).strip())
				assert not result is None, "Kineticist Wild Talent Line Regex failed for " + url
				pageObject[key][result.group(1)] = splitP(result.group(2))
				skipBr(optional=True)

		elif key == "psychic_magic":
			result = re.search(r'^(.+?)\s*-\s*(.+)$', collectText(["h3", "br"], skip=[], mark=["sup"]).strip())
			assert not result is None, "Psychic Magic Line Regex failed for " + url
			
			pageObject["psychic_magic"]["PE"] = result.group(1)

			# Numericize PE if possible
			if re.search(r'^(\d+) PE$', pageObject["psychic_magic"]["PE"]) is not None:
				pageObject["psychic_magic"]["PE"] = parseInt(pageObject["psychic_magic"]["PE"][:-3])

			# Parse spells
			for entry in splitP(result.group(2)):
				entrydict = {}
				entry = entry.strip()

				# Handle superscripts
				regex = r'(<sup>(.+?)</sup>)'
				result = re.search(regex, entry)
				while not result is None:
					s = result.group(2).strip()
					entry = entry[:result.start(1)] + entry[result.end(1):] # Strip out all superscripts
					entry = entry.strip()
					if not "superscripts" in entrydict:
						entrydict["superscripts"] = []
					entrydict["superscripts"].append(s)
					result = re.search(regex, entry) # repeat regex to look for next <sup>

				result = re.search(r'^(.+?)\s*(?:\(([^)]+)\))?$', entry)
				assert not result is None, "Psychic Magic Spell Regex failed for " + url
				entrydict["name"] = result.group(1)
				if not result.group(2) is None:
					for subentry in splitP(result.group(2), sep=r'[,;] '):
						if subentry.endswith(" PE"):
							entrydict["PE"] = parseInt(subentry[:-3])
						elif subentry.startswith("DC "):
							entrydict["DC"] = parseInt(subentry[3:])
						else:
							assert not "other" in entrydict, url + " |" + entrydict["other"] + "|    |" + subentry + "|"
							entrydict["other"] = subentry.strip()
				pageObject[key]["entries"].append(entrydict)
			skipBr(optional=True)

			# For Mythic Solar Pitri (Agnishvatta): Skip "M for mythic spell-like ability" chunk if present
			if e[i].name == "b" and e[i].get_text().strip() == "M":
				i += 1
				assert isinstance(e[i], NavigableString) and e[i].strip().lower() == "mythic spell-like ability", url
				i += 1
				skipBr(optional=True)

		# Get occultist implements if present
		if key == "spells" and e[i].name == "b" and e[i].get_text().strip() == "Implements":
			i += 1
			skipBr()
			sourcedict["occultist_implements"] = []
			while e[i].name == "b":
				s = collectText(["h3", "br"]).strip()
				skipBr(optional=True)
				entrydict = {}
			
				result = re.search(r'^(.+?) \((.+?), (\d+) points\)-Resonant (.+); Focus (.+)$', s, re.IGNORECASE)
				assert not result is None, url + " |" + s + "|"
				entrydict["school"] = result.group(1).strip()
				entrydict["slot"] = result.group(2).strip()
				entrydict["points"] = parseInt(result.group(3))
				entrydict["resonant_power"] = result.group(4).strip()
				entrydict["focus_powers"] = splitP(result.group(5).strip())

				sourcedict["occultist_implements"].append(entrydict)

		if key != "kineticist_wild_talents":
			pageObject[key]["sources"].append(sourcedict)
		

	# TACTICS if present
	if e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Tactics":
		pageObject["tactics"] = {}
		i += 1
		if isinstance(e[i], NavigableString) and e[i].strip() == "": # Handle the odd phantom spacing, like in Shoanti Gladiator
			i += 1
		while e[i].name == "b":
			t = e[i].get_text().strip()
			i += 1
			pageObject["tactics"][t] = collectText(["h3", "br"]).strip()
			skipBr(optional=True)
			skipBr(optional=True) # Sometimes double-spaced, like in Ogre King
			if isinstance(e[i], NavigableString) and e[i].strip() == "": # Handle the odd phantom spacing, like in Lastwall Border Scout
				i += 1

	# STATISTICS
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Statistics", url
	i += 1

	# Get ability scores
	pageObject["ability_scores"] = {}
	checkCounter = 0
	ability_score_names = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
	while e[i].name == "b":
		t = e[i].get_text().upper()
		assert t == ability_score_names[checkCounter], url
		i += 1
		v = cleanS(e[i], trailingChar=",")
		if v == "-":
			v = None
		else:
			v = parseInt(v, stringIfFail=True)
		pageObject["ability_scores"][t] = v
		i += 1
		checkCounter += 1
	assert checkCounter == 6, "Incorrect amount of ability scores (" + checkCounter + ") found in " + url
	skipBr()

	# Get BAB, CMB, and CMD
	assert e[i].name == "b" and e[i].get_text() == "Base Atk", url
	i += 1
	pageObject["BAB"] = parseInt(cleanS(collectText(["b"])), stringIfFail=True)
	if not "is_3.5" in pageObject:
		assert e[i].name == "b" and e[i].get_text() == "CMB", url
		i += 1
		x = cleanS(collectText(["b"])).strip()
		result = re.search(r'^(-|[+-]?\d+)(?:\s*\(([^)]+)\))?$', x)
		assert not result is None, "CMB Regex failed for " + url
		if result.group(1) == "-":
			pageObject["CMB"] = None
		else:
			pageObject["CMB"] = parseInt(result.group(1))
		if not result.group(2) is None:
			pageObject["CMB_other"] = result.group(2).strip()
		assert e[i].name == "b" and e[i].get_text() == "CMD", url
		i += 1
		result = re.search(r'^(-|[+-]?\d+)(?:\s*\(([^)]+)\))?$', cleanS(collectText(["br", "h1", "h2", "h3"])).strip())
		assert not result is None, "CMD Regex failed for " + url
		if result.group(1) == "-":
			pageObject["CMD"] = None
		else:
			pageObject["CMD"] = parseInt(result.group(1))
		if not result.group(2) is None:
			pageObject["CMD_other"] = result.group(2).strip()
		skipBr(optional=True)
	else:
		assert e[i].name == "b" and e[i].get_text() == "Grapple", url
		i += 1
		pageObject["grapple_3.5"] = parseInt(collectText(["br", "b", "h3", "h2", "h1"]), stringIfFail=True)
		skipBr(optional=True)

	# Get feats if present
	if e[i].name == "b" and e[i].get_text() == "Feats":
		i += 1

		# Before we collect the text, we need to unwrap all the <a> tags so we can properly read superscripts inside them. We look ahead for this
		i2 = i
		while i2 < len(e) - 1:
			if not isinstance(e[i2], NavigableString):
				if e[i2].name == "a":
					e[i2].unwrap()
				elif e[i2].name == "br":
					break
			i2 += 1

		s = collectText(["br"], skip=[], mark=["sup"]).strip()
		pageObject["feats"] = []
		entries = splitP(s)
		for entry in entries:
			entry = handleAsterisk(entry.strip())
			entrydict = {}

			# First, handle all superscripts
			regex = r'(<sup>(.+?)</sup>)'
			result = re.search(regex, entry)
			while not result is None:
				s = result.group(2).strip()
				entry = entry[:result.start(1)] + entry[result.end(1):] # Strip out all superscripts
				entry = entry.strip()
				if s == "B":
					entrydict["is_bonus"] = True
				elif s == "M":
					entrydict["is_mythic"] = True
				else:
					if not "superscripts" in entrydict:
						entrydict["superscripts"] = []
					entrydict["superscripts"].append(s)
				result = re.search(regex, entry) # repeat regex to look for next <sup>

			result = re.search(r"^(.+?)(?: \((.+?)\))?$", entry)
			assert not result is None, "Feats Regex failed for " + url
			if result.group(2) is None:
				entrylist = [result.group(1)]
			else: # Deal with commas inside parentheses (e.g. "Spell Focus (conjuration, enchantment)") - breaks up into multiple feats
				entrylist = [result.group(1) + " (" + t + ")" for t in splitP(result.group(2))]
			
			for subentry in entrylist:
				subentrydict = deepcopy(entrydict)
				subentrydict["name"] = subentry
				pageObject["feats"].append(subentrydict)
		skipBr(optional=True)

	# Get skills if present
	pageObject["skills"] = {}
	if e[i].name == "b" and e[i].get_text() == "Skills":
		i += 1
		s = cleanS(collectText(["br", "h1", "h2", "h3"]))

		# Check for racial modifiers
		s_racial = None
		result = re.search(r"^(.+?);?\s*Racial +Modifiers?\s*(.+?)$", s)
		if not result is None:
			s = result.group(1).strip()
			s_racial = result.group(2).strip()

		# Handle the skills segment
		entries = splitP(s, sep=",")
		for entry in entries: # Complex ingestion process to deal with commas inside parentheses (e.g. "Knowledge (arcana, religion)")
			entry = handleAsterisk(entry.strip())
			result = re.search(r"^(.+?)(?: \((.+?)\))? ([+-]\d+)(?: *\(([^)]+)\))?$", entry)
			assert not result is None, "Skills Regex failed for " + url
			
			# De-abbreviate name
			name = result.group(1).strip()
			if name in ["Dip."]:
				name = "Diplomacy"
			elif name in ["Know.", "Knowl."]:
				name = "Knowledge"
			elif name in ["Ling."]:
				name = "Linguistics"
			elif name in ["Per.", "Percep.", "Percept."]:
				name = "Perception"
			elif name in ["S. Motive"]:
				name = "Sense Motive"

			# Handle skills with parens like Craft (traps)
			skillNames = [name]
			if name in ["Craft", "Knowledge", "Perform", "Profession"]:
				if not result.group(2) is None:
					skillNames = [name + " (" + t.strip() + ")" for t in splitP(result.group(2), sep=r"(?:, | and | plus )")] # All the strip() calls here and in the other if branch handle strange whitespace in cases like Black Magga (probably caused by \r handling)
			else:
				assert result.group(2) is None, url + " |" + entry + "|"

			pageObject["skills"].update({skillName: parseInt(result.group(3)) for skillName in skillNames})
			if result.group(4) is not None:
				pageObject["skills"].update({skillName + "_other": result.group(4).strip() for skillName in skillNames})

			# Save raw entry for perception mismatch checking later
			if name == "Perception":
				perceptionRaw = entry

		# Get racial modifiers if present
		if s_racial is not None:
			pageObject["skill_racial_mods"] = {}
			s = s_racial

			bonusFirst = s[0] in "+-" # Similar logic as above, but need to handle 2 different formats ("+4 Perception" vs. "Perception +4")
			while s is not None and s.strip() != "":
				if bonusFirst:
					result = re.search(r"^([+-]\d+)\s+([^,)(]+?)(?:\s+\(([^+-][^)]+?)\))?(?:\s+\(([+-][^)]+?)\))?(?:, ([+-].+))?$", s.strip())
					groupBonus = 1
					groupSkill = 2
					groupSkillParen = 3
				else:
					result = re.search(r"^([^,)(]+?)(?:\s+\(([^+-][^)]+?)\))?\s+([+-]\d+)(?:\s+\(([+-][^)]+?)\))?(?:, (.+))?$", s.strip())
					groupBonus = 3
					groupSkill = 1
					groupSkillParen = 2

				if not result is None:
					assert result.group(groupSkillParen) is None or result.group(4) is None, url # Assert there are no double parens to save us the trouble of handling them since they never happen
				
					if result.group(groupSkillParen) is None:
						pageObject["skill_racial_mods"][result.group(groupSkill)] = parseInt(result.group(groupBonus))
						if not result.group(4) is None:
							pageObject["skill_racial_mods"][result.group(groupSkill) + "_other"] = result.group(4)
					else:
						pageObject["skill_racial_mods"].update({result.group(groupSkill) + " (" + t + ")": parseInt(result.group(groupBonus)) for t in splitP(result.group(groupSkillParen), sep=r',\s+(?:and\s+)?')})
					s = result.group(5)
				else:
					pageObject["skill_racial_mods"]["other"] = s
					break

		skipBr(optional=True)

	# Add in perception skill from Senses if not already present
	if not "is_3.5" in pageObject:
		if "Perception" in pageObject["skills"]:
			if perceptionSkill != pageObject["skills"]["Perception"]:
				if "Perception_other" in pageObject["skills"]:
					if "Perception " + str(perceptionSkill) != parseInt(perceptionRaw, stringIfFail=True):
						pageObject["skills"]["_Perception_mismatch"] = True
				else:
					pageObject["skills"]["_Perception_mismatch"] = True
		else:
			pageObject["skills"]["Perception"] = perceptionSkill
	else:
		if "Listen" in pageObject["skills"]:
			if not "Listen_other" in pageObject["skills"] and pageObject["skills"]["Listen"] != listenSkill:
				pageObject["skills"]["_Listen_mismatch"] = True
		else:
			pageObject["skills"]["Listen"] = listenSkill

		if "Spot" in pageObject["skills"]:
			if not "Spot_other" in pageObject["skills"] and pageObject["skills"]["Spot"] != spotSkill:
				pageObject["skills"]["_Spot_mismatch"] = True
		else:
			pageObject["skills"]["Spot"] = spotSkill

	# Get languages if present
	if e[i].name == "b" and e[i].get_text() == "Languages":
		i += 1
		pageObject["languages"] = splitP(collectText(["h3", "br"]).strip(), sep=r'[,;] ')
		pageObject["languages"] = [l.strip() for l in pageObject["languages"]] # Handles strange whitespace in cases like Black Magga (probably caused by \r handling)
		skipBr(optional=True)

	# Get special qualities if present
	if e[i].name == "b" and e[i].get_text() == "SQ":
		i += 1
		pageObject["special_qualities"] = splitP(handleAsterisk(collectText(["h3", "br"]).strip()))
		skipBr(optional=True)

	# Get gear if present (could be Combat Gear, Other Gear, or just Gear)
	for gear_name, gear_string in [("gear", "Gear"), ("combat", "Combat Gear"), ("other", "Other Gear")]:
		if e[i].name == "b" and e[i].get_text() == gear_string:
			i += 1
			if not "gear" in pageObject:
				pageObject["gear"] = {}
			pageObject["gear"][gear_name] = splitP(handleAsterisk(cleanS(collectText(["h3", "br", "b"]))))
	skipBr(optional=True)

	# Get npc boon if present
	skipBr(optional=True)
	if e[i].name == "b" and e[i].get_text().strip() == "Boon":
		i += 1
		assert isinstance(e[i], NavigableString), url
		pageObject["npc_boon"] = e[i].strip()
		i += 1
		skipBr(optional=True)

	# ECOLOGY if present
	if e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Ecology":
		pageObject["ecology"] = {}
		i += 1
		
		# Get environment
		assert e[i].name == "b" and e[i].get_text() == "Environment", url
		i += 1
		pageObject["ecology"]["environment"] = collectText(["h3", "br"]).strip()
		skipBr(optional=True)

		# Get organization and treasure if present (they should always be present but some pages have incomplete info)
		if e[i].name == "b" and e[i].get_text() == "Organization":
			i += 1
			pageObject["ecology"]["organization"] = collectText(["h3", "br"]).strip()
			skipBr(optional=True)

		if e[i].name == "b" and e[i].get_text() == "Treasure":
			i += 1
			s = collectText(["h3", "br"]).strip()
			treasure_types = ['none', 'incidental', 'half', 'standard', 'double', 'triple', 'NPC Gear']
			result = re.search(r'^(' + "|".join(treasure_types) + r')(?:\s+\((.+?)\))?$', s, re.IGNORECASE)
			if not result is None:
				pageObject["ecology"]["treasure_type"] = [x for x in treasure_types if x.lower() == result.group(1).lower()][0]
				if not result.group(2) is None:
					pageObject["ecology"]["treasure"] = splitP(handleAsterisk(result.group(2).strip()))
			else:
				pageObject["ecology"]["treasure"] = splitP(handleAsterisk(s))
			skipBr(optional=True)

		# For 3.5 entries, get advancement if present
		if "is_3.5" in pageObject and e[i].name == "b" and e[i].get_text() == "Advancement":
			i += 1
			s = collectText(["h3", "br"]).strip()
			if s != "none":
				pageObject["ecology"]["advancement_3.5"] = []
				entries = splitP(s, sep=r'(?:,| or|(?<=\));)')
				for entry in entries:
					entrydict = {}
					entry = entry.strip()
					result = re.search(r'^(\d+)(?:-(\d+)|\+) (?:HD )?\((' + "|".join(sizes) + r')\)$', entry, re.IGNORECASE)
					if not result is None:
						entrydict = {
							"type": "size",
							"HD_min": parseInt(result.group(1)),
							"size": result.group(3)
						}
						if not result.group(2) is None:
							entrydict["HD_max"] = parseInt(result.group(2))

						pageObject["ecology"]["advancement_3.5"].append(entrydict)
						continue

					result = re.search("^by character class(?:; Favored Class (.+))?$", entry, re.IGNORECASE)
					if not result is None:
						entrydict["type"] = "class"
						if not result.group(1) is None:
							entrydict["favored_class"] = result.group(1)

						pageObject["ecology"]["advancement_3.5"].append(entrydict)
						continue

					raise Exception("Unknown advancement fragment in " + url + " - |" + entry + "|")

			skipBr(optional=True)



	# SPECIAL ABILITIES if present
	if e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Special Abilities":
		pageObject["special_abilities"] = {}
		i += 1

		assert e[i].name == "b", url

		while e[i].name == "b":
			# Get the current special ability name
			t = e[i].get_text().strip()
			i += 1

			# Find the next tag to stop at
			nextI = i
			while nextI < len(e) - 1: # -1 for the special end tag
				if e[nextI].name in ["h1", "h2", "h3"]:
					break
				elif e[nextI].name == "b":
					# Check if we're right after a newline, if not then go next
					# To do this, sweep backwards across whitespace-only text nodes to find a newline-creating tag
					i2 = nextI - 1
					while i2 > 0 and isinstance(e[i2], NavigableString) and e[i2].strip() == "":
						i2 -= 1
					if e[i2].name in ["h3", "br", "ul"]:
						break
				nextI += 1

			# If we didn't find a tag to stop at, then scan again and stop at the first double-br
			if nextI == len(e) - 1:
				nextI = i
				while nextI < len(e):
					if e[nextI-1].name == "br" and e[nextI].name == "br":
						nextI -= 1
						break
					nextI += 1

			# Manually collect the text from the selected nodes
			text = ""
			while i < nextI:
				if isinstance(e[i], NavigableString):
					text += e[i]
				elif e[i].name == "br":
					text += "\n"
				else:
					text += e[i].get_text()
				i += 1
			
			# Update page data
			pageObject["special_abilities"][t] = text.strip()
	
	# Skip the final DESCRIPTION header if present, as well as any trailing br tags
	if e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Description":
		i += 1
	while e[i].name == "br":
		skipBr()

	# Get all the rest as a description
	pageObject["desc_long"] = collectText(["h1", "h2"])


	return pageObject


if __name__ == "__main__":
	urls = []
	with open(sys.argv[1] + "/urls.txt") as file:
		for line in file:
			urls.append(line.rstrip())

	broken_urls = []
	with open("broken_urls.txt") as file:
		for line in file:
			broken_urls.append(line.rstrip())

	pageObjects = {}
	for i, url in enumerate(tqdm(urls)):
	# for i, url in enumerate(urls):
		# Skip urls pre-marked as broken
		if url in broken_urls:
			continue

		# if url != "https://aonprd.com/MonsterDisplay.aspx?ItemName=Lusca":
		# 	continue

		with open(sys.argv[1] + "/" + str(i) + ".html") as file:
			html = file.read()

		try:
			pageObjects[url] = parsePage(html, url)
		except Exception as e:
			print(url)
			_, _, tb = sys.exc_info()
			traceback.print_tb(tb)
			print(type(e).__name__ + ": " + str(e))

		if not include3_5 and url in pageObject:
			del pageObject[url]

	with open(sys.argv[1] + '/data.json', 'w') as fp:
		json.dump(pageObjects, fp)