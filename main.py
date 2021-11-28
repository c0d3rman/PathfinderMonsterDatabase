#####################
# CONFIG
#####################

# Should we keep superscripts (<sup>)?
# If true, superscripts will be kept as plaintext, which may garble some words.
# If false, they'll just be dropped.
# TODO - this ruins domain spell parsing, need a better solution
keepSuperscripts = False

# TODO - handle asterisks * better
# TODO - handle 3.5 skills and tag 3.5 monsters (skipping for now)
# TODO - investigate URLs that appear multiple times in monster list
# TODO - investigate pages with multiple statblocks (e.g. mammoth rider NPC)
# TODO - check creatures with no base land speed (if those exist)
# TODO - the current handling of \r and other weird newlines introduces a lot of spaces in the wrong places. Need better solution. See Lastwall Border Scout
# TODO - make sure the dash in At-will doesn't break things in spells, spell like abilities, etc.
# TODO - fix racial modifiers all around, including giving it similar _other structure to skills (try on Demonic Deadfall Scorpion)


#####################
# PROGRAM
#####################


from bs4 import BeautifulSoup, NavigableString
import regex as re
import json
import sys
import traceback
from tqdm import tqdm


def parseInt(s, stringIfFail=False):
	def _parseInt(s):
		return int(s.strip().replace("–", "-").replace("—", "-").replace("−", "-").replace(",", "").replace("+ ", "+").replace("- ", "-"))

	if stringIfFail:
		try:
			return _parseInt(s)
		except:
			return s.strip()
	else:
		return _parseInt(s)

def parsePage(html):
	# Clean up HTML
	html = html.replace("\r\n", " ").replace("\r", " ").replace(chr(10), " ").replace('\xad', '') # Fix weird whitespace in some entries (e.g. Vermlek, Achaierai, Signifer of the Nail, Vampiric Mist)
	html = re.sub(r'(?<!<\s*br\s*>\s*)<\s*/\s*br\s*>', r'<br/>', html) # Fix broken <br> tags in some pages, e.g. Vilderavn. Uses a variable-width negative lookbehind, so we use the regex module instead of the re module

	soup = BeautifulSoup(html, "html.parser")

	# Delete superscripts if config tells us to
	if not keepSuperscripts:
		for t in soup.select('sup'):
			t.extract()

	pageObject = {}

	# Temporary - if it's a 3.5 statblock, give up
	if soup.find("img", src="images\\ThreeFiveSymbol.gif") is not None:
		return {"is_3.5": True}

	e = soup.select_one("div#main table tr td span").contents
	i = 0
	e.append(soup.new_tag("custom_end")) # Append a special end tag so we don't fall off the end

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

	# Helper function to collect all following text, handling unpredictable nodes
	# Doesn't stop until it hits a node on the tags list
	# Will advance nodes
	# Use the special "[text]" value for text nodes
	def collectText(tags):
		nonlocal e, i
		text = ""
		while i < len(e) - 1: # -1 for the special end tag
			if ("[text]" in tags and isinstance(e[i], NavigableString)) or (not isinstance(e[i], NavigableString) and e[i].name in tags):
				break

			if isinstance(e[i], NavigableString):
				text += e[i]
			elif e[i].name == "br":
				text += "\n"
			else:
				text += e[i].get_text()
			i += 1
		return text

	# Get main title
	assert e[i].name == "h1" and e[i]['class'] == ['title'], url
	pageObject["title1"] = e[i].get_text()
	i += 1

	# Get short description if present
	if e[i].name == "i":
		pageObject["desc_short"] = e[i].get_text()
		i += 1

	# Get statblock title & CR
	assert e[i].name == "h2" and e[i]['class'] == ['title'], url
	result = re.search(r'^(.+) CR ([0-9/−—–-]+)$', e[i].get_text())
	assert not result is None, "CR-finding Regex failed for " + url
	pageObject["title2"] = result.group(1)
	pageObject["CR"] = result.group(2)
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
		if e[i].strip() != "":
			pageObject["XP"] = parseInt(e[i][1:]) # Don't include space
		i += 1
		skipBr()

	# Get race and class levels if present
	s = collectText(["br"])
	skipBr()
	if isinstance(e[i], NavigableString): # If we're looking at a string instead of the bold "Init", then we have a race/class line
		result = re.search(r'^(.+?) (.+)?$', s)
		assert not result is None, "Race and Class Regex failed for " + url
		pageObject["race"] = result.group(1)
		pageObject["classes"] = result.group(2).split("/")
		
		# Fetch the actual alignment line this time
		s = collectText(["br"])
		skipBr()

	# Get alignment, size, type, subtypes
	sizes = ['Fine', 'Diminutive', 'Tiny', 'Small', 'Medium', 'Large', 'Huge', 'Gargantuan', 'Colossal']
	result = re.search(r'^(.+) (' + "|".join(sizes) + r') ([^(]+)(?: \((.+)\))?$', s.strip())
	assert not result is None, "Alignment Line Regex failed for " + url
	pageObject["alignment"] = result.group(1)
	pageObject["size"] = result.group(2)
	pageObject["type"] = result.group(3)
	if result.group(4) is not None:
		pageObject["subtypes"] = result.group(4).split(", ")

	# Get initiative
	assert e[i].name == "b" and e[i].get_text() == "Init", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	result = re.search(r'^ ([+−—–-][\d,]+(?: \(.+?\))?); ', e[i])
	assert not result is None, "Initiative Regex failed for " + url
	pageObject["initiative"] = parseInt(result.group(1), stringIfFail=True)
	i += 1

	# Get senses
	assert e[i].name == "b" and e[i].get_text() == "Senses", url
	i += 1
	result = re.search(r'^(?: (.+)[;,])? *Perception ([+−—–-] ?[\d,]+)', collectText(["h3", "br"])) # Regex handles broken formatting on pages like Demonologist that use a comma instead of a semicolon. Space before Perception is variable length because of the typos in Elder Air Elemental and Scarlet Walker, and space inside number because of Mirror Serpent
	assert not result is None, "Senses Regex failed for " + url
	if result.group(1) is not None:
		pageObject["senses"] = result.group(1).split(", ")
	perceptionSkill = parseInt(result.group(2), stringIfFail=True)

	skipBr(optional=True)

	# Get auras if present
	if e[i].name == "b" and e[i].get_text() == "Aura":
		i += 1
		pageObject["auras"] = re.split(r', (?![^()]*\))', collectText(["h3", "br"]).strip()) # Skip leading space and use a special split to avoid splitting on commas inside parens

	# DEFENSE
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Defense", url
	i += 1

	# Get AC
	assert e[i].name == "b" and e[i].get_text() == "AC", url
	i += 1
	s = collectText(["br"]).strip()
	result = re.search(r'^([\d,-]+?)[,;] touch ([\d,-]+?)[,;] flat-footed ([\d,-]+?)(?: \((.+)\))?(?:; (.+))?\.?$', s) # Accepts ; as well as , because of broken formatting on pages like Bugbear Lurker. Skip broken formatting trailing period in e.g. Flying Fox
	assert not result is None, "AC Regex failed for " + url
	pageObject["AC"] = parseInt(result.group(1))
	pageObject["AC_touch"] = parseInt(result.group(2))
	pageObject["AC_flatfooted"] = parseInt(result.group(3))
	if result.group(4) is not None:
		entries = [entry.strip() for entry in result.group(4).split(", ")] # Fixes whitespace issues in e.g. Malsandra (probably caused by \r handling)
		pageObject["AC_components"] = {entry[entry.find(" ")+1:]: parseInt(entry[:entry.find(" ")]) for entry in entries}
	pageObject["AC_other"] = result.group(5)
	skipBr()

	# Get HP, and fast healing / regeneration / other HP abilities if present
	assert e[i].name == "b" and e[i].get_text() == "hp", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	result = re.search(r'^(.+) \((.+)\)(?:[;,] (.+))?$', e[i].strip()) # Supports , instead of ; for broken formatting on pages like Egregore
	assert not result is None, "HP Regex failed for " + url
	pageObject["HP"] = parseInt(result.group(1), stringIfFail=True)
	pageObject["HP_long"] = result.group(2)
	if result.group(3) is not None:
		if result.group(3).startswith("fast healing "):
			pageObject["fast_healing"] = parseInt(result.group(3).replace("fast healing ", ""))
		elif result.group(3).startswith("regeneration "):
			pageObject["regeneration"] = parseInt(result.group(3).replace("regeneration ", ""))
		else:
			pageObject["hp_ability_other"] = result.group(3)
	i += 1
	skipBr()

	# Get saves
	assert e[i].name == "b" and e[i].get_text() == "Fort", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	pageObject["fort"] = parseInt(e[i][:-2], stringIfFail=True) # Skip trailing ", "
	i += 1
	assert e[i].name == "b" and e[i].get_text() == "Ref", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	pageObject["ref"] = parseInt(e[i][:-2], stringIfFail=True) # Skip trailing ", "
	i += 1
	assert e[i].name == "b" and e[i].get_text() == "Will", url
	i += 1
	assert isinstance(e[i], NavigableString), url
	pageObject["will"] = parseInt(e[i], stringIfFail=True)
	i += 1

	skipBr(optional=True)

	# Helper to strip string and trailing char
	def cleanS(s, trailingChar=";"):
		s = s.strip()
		if s[-1] == trailingChar:
			s = s[:-1]
		return s

	# Get defensive abilities if present
	if e[i].name == "b" and e[i].get_text() == "Defensive Abilities":
		i += 1
		pageObject["defensive_abilities"] = cleanS(collectText(["b", "br", "h3"])).split(", ") 

	# Get DR if present
	if e[i].name == "b" and e[i].get_text() == "DR":
		i += 1
		pageObject["DR"] = cleanS(collectText(["b", "br", "h3"]))

	# Get immunities if present
	if e[i].name == "b" and e[i].get_text() == "Immune":
		i += 1
		pageObject["immunities"] = cleanS(collectText(["h3", "br", "b"])).split(", ")

	# Get resistances if present
	if e[i].name == "b" and e[i].get_text() == "Resist":
		i += 1
		assert isinstance(e[i], NavigableString), url
		entries = [entry.strip() for entry in cleanS(e[i]).split(", ")] # Handles strange whitespace in cases like Black Magga (probably caused by \r handling)
		pageObject["resistances"] = {entry[:entry.rfind(" ")]: parseInt(entry[entry.rfind(" ")+1:]) for entry in entries}
		i += 1

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
		pageObject["weaknesses"] = collectText(["h3"])[1:].split(", ") # Skip leading space


	# OFFENSE
	assert e[i].name == "h3" and e[i]['class'] == ['framing'] and e[i].get_text() == "Offense", url
	i += 1

	# Get speed
	assert e[i].name == "b" and e[i].get_text() == "Speed", url
	i += 1
	entries = collectText(["br"]).split(", ")
	pageObject["speeds"] = {}
	for entry in entries[1:]: # Skip base speed
		if "ft." in entry:
			pageObject["speeds"][entry[:entry.find(" ")]] = entry[entry.find(" ")+1:]
		else:
			pageObject["speeds"][entry] = entry # Non-numeric entries like "air walk"
	pageObject["speeds"]["base"] = entries[0].strip() # Handle base speed separately. Skip leading space
	skipBr()

	# Get melee attacks if present
	if e[i].name == "b" and e[i].get_text() == "Melee":
		i += 1
		pageObject["attacks_melee"] = collectText(["h3", "b"]).strip() # Strip leading space if present

	# Get ranged attacks if present
	if e[i].name == "b" and e[i].get_text() == "Ranged":
		i += 1
		pageObject["attacks_ranged"] = collectText(["h3", "b"]).strip() # Strip leading space if present

	# Get space if present
	if e[i].name == "b" and e[i].get_text() == "Space":
		i += 1
		pageObject["space"] = cleanS(e[i], ",")
		i += 1

	# Get space if present
	if e[i].name == "b" and e[i].get_text() == "Reach":
		i += 1
		pageObject["reach"] = cleanS(e[i], ",")
		i += 1

	# Skip br if present
	skipBr(optional=True)

	# Get special attacks if present
	if e[i].name == "b" and e[i].get_text() == "Special Attacks":
		i += 1
		pageObject["attacks_special"] = re.split(r', (?![^()]*\))', collectText(["h3", "br"])[1:]) # Skip leading space and use a special split to avoid splitting on commas inside parens
		skipBr(optional=True)

	# Helper function to handle headers of spell and spell-like ability blocks
	def handleSpellRelatedHeader(text, out):
		assert isinstance(text, NavigableString), url
		result = re.search(r'^\((?:CL|caster level) (\d+)(?:\w{2})?(?:[;,] +conc(?:entration|\.):? ([+−—–-][\d,]+))?(?:[;,] +(?:(?:(\d+%) (?:arcane )?spell failure(?: chance)?)|(?:arcane )?spell failure(?: chance)? (\d+%)))?(?:[;,] +(?:save DCs are )?(\w+)[−—–-]based)?\)$', text.strip(), re.IGNORECASE) # Handles corrupted formatting for , instead of ; like in Ice Mage. Concentration colon for Executioner Devil (Munagola)
		assert not result is None, "Spell-Related Header Regex failed for " + url
		out["CL"] = parseInt(result.group(1))
		if result.group(2) is not None:
			out["concentration"] = parseInt(result.group(2))
		if result.group(3) is not None: # There are two capture groups that might capture the failure chance
			out["failure_chance"] = result.group(3)
		elif result.group(4) is not None:
			out["failure_chance"] = result.group(4)
		if result.group(5) is not None:
			out["DC_ability_score"] = result.group(5)

	# Get all spell-like abilities (potentially from multiple sources)
	while e[i].name == "b" and e[i].get_text().strip().endswith("Spell-Like Abilities"):
		# Init the first time
		if not "spell_like_abilities" in pageObject:
			pageObject["spell_like_abilities"] = {}

		t = e[i].get_text().replace("Spell-Like Abilities", "").strip().lower() # Get type of spell-like ability (notably "Domain")
		if t == "":
			t = "default"
		pageObject["spell_like_abilities"][t] = {}
		i += 1
		handleSpellRelatedHeader(e[i], pageObject["spell_like_abilities"][t])
		i += 1
		skipBr()

		pageObject["spell_like_abilities"][t]["freq"] = {}
		while isinstance(e[i], NavigableString):
			result = re.search(r'^(.+?)\s*[−—–-]\s*(.+)$', collectText(["h3", "br"]).strip())
			if not result is None:
				pageObject["spell_like_abilities"][t]["freq"][result.group(1)] = re.split(r', (?![^()]*\))', result.group(2)) # Use a special split to avoid splitting on commas inside parens
				skipBr(optional=True)
			elif (e[i].name == "br" and e[i+1].name == "br") or e[i].name == "h3": # Skip asterisk line if present, like in Szuriel. Kinda hacky and not very tested, hopefully it won't break anything
				skipBr(optional=True)
				break
			else:
				raise Exception("Spell-Like Ability Line Regex failed for " + url)

			skipBr(optional=True)

		# Get domain if present - rarely there's a domain with the spell-like abilities, e.g. Clockwork Priest
		if e[i].name == "b" and (e[i].get_text().strip() == "Domain" or e[i].get_text().strip() == "Domains"):
			i += 1
			assert isinstance(e[i], NavigableString), url
			pageObject["spell_like_abilities"][t]["domains"] = collectText(["br", "h3"]).lower().strip().split(", ") # collectText because there might be a superscript splitting the text tag, like in Usij Cabalist
			skipBr(optional=True)

	# Get kineticist wild talents (if present)
	if e[i].name == "b" and e[i].get_text().strip() == "Kineticist Wild Talents Known":
		pageObject["kineticist_wild_talents"] = {}
		i += 1
		skipBr()

		while isinstance(e[i], NavigableString):
			result = re.search(r'^(.+?)\s*[−—–-]\s*(.+)$', collectText(["h3", "br"]).strip())
			assert not result is None, "Spell-Like Ability Line Regex failed for " + url
			pageObject["kineticist_wild_talents"][result.group(1)] = re.split(r', (?![^()]*\))', result.group(2)) # Use a special split to avoid splitting on commas inside parens
			skipBr(optional=True)

	# Get psychic magic if present
	if e[i].name == "b" and (e[i].get_text().strip() == "Psychic Magic" or e[i].get_text().strip() == "Psychic Magic (Sp)"):
		pageObject["psychic_magic"] = {}
		i += 1
		handleSpellRelatedHeader(e[i], pageObject["psychic_magic"])
		i += 1
		skipBr()

		result = re.search(r'^(.+?)\s*[−—–-]\s*(.+)$', collectText(["h3", "br"]).strip())
		assert not result is None, "Psychic Magic Line Regex failed for " + url
		
		pageObject["psychic_magic"]["PE"] = result.group(1)

		# Numericize PE if possible
		if re.search(r'^(\d+) PE$', pageObject["psychic_magic"]["PE"]) is not None:
			pageObject["psychic_magic"]["PE"] = parseInt(pageObject["psychic_magic"]["PE"][:-3])

		pageObject["psychic_magic"]["spells"] = re.split(r', (?![^()]*\))', result.group(2)) # Use a special split to avoid splitting on commas inside parens
 
		skipBr(optional=True)

	# Get all spells (potentially from multiple sources)
	# TODO - fix this. Need to parse (?)times prepared, (?)number of spells per day, (?)domain spells, (?)DC
	# For now, keeping as a string
	while e[i].name == "b" and ("Spells" in e[i].get_text() or "Extracts" in e[i].get_text()):
		# Init the first time
		if not "spells" in pageObject:
			pageObject["spells"] = {}

		result = re.search(r'^(?:([\w ]+) )?(?:Spells|Extracts) (Prepared|Known)$', e[i].get_text().strip())
		assert not result is None, "Spell Class Regex failed for " + url
		t = result.group(1)
		if t is None:
			# If no class was listed, but we have only one class, use that one
			if "classes" in pageObject and pageObject["classes"] is not None and len(pageObject["classes"]) == 1:
				t = pageObject["classes"][0]
			else: # No idea. e.g. Noble (Knight), where the spells are Paladin spells, but he also has the Aristocrat class
				t = "?"
		pageObject["spells"][t] = {"type": result.group(2).lower()}
		i += 1
		handleSpellRelatedHeader(e[i], pageObject["spells"][t])
		i += 1
		skipBr()

		pageObject["spells"][t]["level"] = {}
		while isinstance(e[i], NavigableString):
			s = collectText(["h3", "br"]).strip()
			result = re.search(r'^(.+?)\s*([−—–-])(?![^()]*\))', s) # Make sure not to get a dash inside parens e.g. Young Occult Dragon
			if not result is None:
				pageObject["spells"][t]["level"][result.group(1)] = re.split(r', (?![^()]*\))', s[result.end(2):].strip()) # Use a special split to avoid splitting on commas inside parens
				skipBr(optional=True)
			elif (e[i].name == "br" and e[i+1].name == "br") or e[i].name == "h3": # Skip asterisk line if present, like in Magaambya Arcanist. Kinda hacky and not very tested, hopefully it won't break anything
				skipBr(optional=True)
				break
			else:
				raise Exception("Spell Line Regex failed for " + url)

		# Skip "D for Domain spell" chunk if present
		if e[i].name == "b" and e[i].get_text().strip() == "D":
			i += 1 # Skip "D"
			assert isinstance(e[i], NavigableString) and e[i].strip().lower() == "domain spell;", url
			i += 1 # Skip "Domain spell; "

		# Get domain if present (separate from the previous chunk because inquisitors get domains but no domain spells)
		if e[i].name == "b" and (e[i].get_text().strip() == "Domain" or e[i].get_text().strip() == "Domains"):
			i += 1
			pageObject["spells"][t]["domains"] = collectText(["br", "h3"]).lower().strip().split(", ") # collectText because there might be a superscript splitting the text tag, like in Usij Cabalist
			skipBr(optional=True)

		# Skip "S for spirit magic spell" chunk if present
		if e[i].name == "b" and e[i].get_text().strip() == "S":
			i += 1 # Skip "S"
			assert isinstance(e[i], NavigableString) and e[i].strip().lower() == "spirit magic spell;", url
			i += 1 # Skip "spirit magic spell; "

		# Get spirit if present (separate from the previous chunk just in case)
		if e[i].name == "b" and e[i].get_text().strip() == "Spirit":
			i += 1
			pageObject["spells"][t]["spirit"] = collectText(["br", "h3"]).lower().strip() # collectText in case of superscripts
			skipBr(optional=True)

		# Get bloodline if present
		if e[i].name == "b" and e[i].get_text().strip() == "Bloodline":
			i += 1
			pageObject["spells"][t]["bloodline"] = collectText(["br", "h3"]).lower().strip() # collectText in case of superscripts / italics, e.g. Kobold Guilecaster
			skipBr(optional=True)

		# Get opposition schools if present
		if e[i].name == "b" and (e[i].get_text().strip() == "Opposition Schools" or e[i].get_text().strip() == "Prohibited Schools"):
			i += 1
			assert isinstance(e[i], NavigableString), url
			pageObject["spells"][t]["opposition_schools"] = e[i].lower().strip().split(", ")
			i += 1
			skipBr(optional=True)

		# Get patron if present
		if e[i].name == "b" and e[i].get_text().strip() == "Patron":
			i += 1
			assert isinstance(e[i], NavigableString), url
			pageObject["spells"][t]["patron"] = e[i].lower().strip()
			i += 1
			skipBr(optional=True)

		# Get mystery if present
		if e[i].name == "b" and e[i].get_text().strip() == "Mystery":
			i += 1
			assert isinstance(e[i], NavigableString), url
			pageObject["spells"][t]["mystery"] = e[i].lower().strip()
			i += 1
			skipBr(optional=True)

		# Get psychic discipline if present
		if e[i].name == "b" and e[i].get_text().strip() == "Psychic Discipline":
			i += 1
			assert isinstance(e[i], NavigableString), url
			pageObject["spells"][t]["psychic_discipline"] = e[i].lower().strip()
			i += 1
			skipBr(optional=True)


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
	checkCounter = 0
	while e[i].name == "b":
		t = e[i].get_text().upper()
		i += 1
		v = cleanS(e[i], trailingChar=",")
		if v in "−—–-":
			v = None
		else:
			v = parseInt(v)
		pageObject[t] = v
		i += 1
		checkCounter += 1
	assert checkCounter == 6, "Incorrect amount of ability scores (" + checkCounter + ") found in " + url
	skipBr()

	# Get BAB, CMB, and CMD
	assert e[i].name == "b" and e[i].get_text() == "Base Atk", url
	i += 1
	pageObject["BAB"] = parseInt(cleanS(collectText(["b"])), stringIfFail=True)
	assert e[i].name == "b" and e[i].get_text() == "CMB", url
	i += 1
	pageObject["CMB"] = parseInt(cleanS(collectText(["b"])), stringIfFail=True)
	assert e[i].name == "b" and e[i].get_text() == "CMD", url
	i += 1
	pageObject["CMD"] = parseInt(cleanS(collectText(["br", "h1", "h2", "h3"])), stringIfFail=True)
	skipBr(optional=True)

	# Get feats if present
	if e[i].name == "b" and e[i].get_text() == "Feats":
		i += 1
		s = collectText(["br"]).strip()
		pageObject["feats"] = []
		while s is not None: # Complex ingestion process to deal with commas inside parentheses (e.g. "Spell Focus (conjuration, enchantment)") - breaks up into multiple feats
			result = re.search(r"^(.+?)(?: \((.+?)\))?(?:, (.+))?$", s)
			assert not result is None, "Feats Regex failed for " + url
			if result.group(2) is None:
				pageObject["feats"].append(result.group(1))
			else:
				pageObject["feats"].extend(result.group(1) + " (" + t + ")" for t in result.group(2).split(", "))
			s = result.group(3)
		skipBr(optional=True)

	# Get skills if present
	pageObject["skills"] = {}
	if e[i].name == "b" and e[i].get_text() == "Skills":
		i += 1
		s = cleanS(collectText(["br", "h1", "h2", "h3"])).strip()

		# Check for racial modifiers
		s_racial = None
		result = re.search(r"^(.+?);?\s*Racial +Modifiers?\s*(.+?)$", s)
		if not result is None:
			s = result.group(1).strip()
			s_racial = result.group(2).strip()

		# Handle the skills segment
		while s is not None and s.strip() != "": # Complex ingestion process to deal with commas inside parentheses (e.g. "Knowledge (arcana, religion)")
			result = re.search(r"^(.+?)(?: \((.+?)\))? ([+−—–-]\d+)(?: *\(([^,]+)\))?(?:, (.+)?)?$", s.strip())
			assert not result is None, "Skills Regex failed for " + url
			
			if result.group(2) is None:
				skillNames = [result.group(1).strip()]				
			else:
				skillNames = [result.group(1).strip() + " (" + t.strip() + ")" for t in result.group(2).split(", ")] # All the strip() calls here and in the other if branch handle strange whitespace in cases like Black Magga (probably caused by \r handling)

			pageObject["skills"].update({skillName: parseInt(result.group(3)) for skillName in skillNames})
			if result.group(4) is not None:
				pageObject["skills"].update({skillName + "_other": result.group(4) for skillName in skillNames})
			s = result.group(5)

		# Get racial modifiers if present
		if s_racial is not None:
			pageObject["skill_racial_mods"] = {}
			s = s_racial

			# Same logic as above, but need to handle 2 different formats ("+4 Perception" vs. "Perception +4")
			if s[0] in "+−—–-":
				while s is not None and s.strip() != "":
					result = re.search(r"^([+−—–-]\d+) ([^,]+)(?: \((.+?)\))?(?:, (.+)?)?", s.strip())
					if not result is None:
						if result.group(3) is None:
							pageObject["skill_racial_mods"][result.group(2)] = parseInt(result.group(1))
						else:
							pageObject["skill_racial_mods"].update({result.group(2) + " (" + t + ")": parseInt(result.group(1)) for t in result.group(3).split(", ")})
						s = result.group(4)
					else:
						pageObject["skill_racial_mods"]["other"] = s
						break
			else:
				while s is not None and s.strip() != "": # Complex ingestion process to deal with commas inside parentheses (e.g. "Knowledge (arcana, religion)")
					result = re.search(r"^(.+?)(?: \((.+?)\))? ([+−—–-]\d+)(?:, (.+)?)?", s.strip())
					if not result is None:
						if result.group(2) is None:
							pageObject["skill_racial_mods"][result.group(1)] = parseInt(result.group(3))
						else:
							pageObject["skill_racial_mods"].update({result.group(1) + " (" + t + ")": parseInt(result.group(3)) for t in result.group(2).split(", ")})
						s = result.group(4)
					else:
						pageObject["skill_racial_mods"]["other"] = s
						break

		skipBr(optional=True)

	# Add in perception skill from Senses if not already present
	if "Perception" in pageObject["skills"]:
		assert pageObject["skills"]["Perception"] == perceptionSkill, url
	else:
		pageObject["skills"]["Perception"] = perceptionSkill

	# Get languages if present
	if e[i].name == "b" and e[i].get_text() == "Languages":
		i += 1
		pageObject["languages"] = re.split(r', |; ', collectText(["h3", "br"]).strip()) # Skip leading space and handle both ", " and "; " separators
		pageObject["languages"] = [l.strip() for l in pageObject["languages"]] # Handles strange whitespace in cases like Black Magga (probably caused by \r handling)
		skipBr(optional=True)

	# Get special qualities if present
	if e[i].name == "b" and e[i].get_text() == "SQ":
		i += 1
		pageObject["special_qualities"] = re.split(r', (?![^()]*\))', collectText(["h3", "br"])[1:]) # Skip leading space and use a special split to avoid splitting on commas inside parens
		skipBr(optional=True)

	# Get gear if present (could be Combat Gear, Other Gear, or just Gear)
	if e[i].name == "b" and (e[i].get_text() == "Gear" or e[i].get_text() == "Combat Gear" or e[i].get_text() == "Other Gear"):
		pageObject["gear"] = collectText(["h3", "br"])
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
			skipBr()

			assert e[i].name == "b" and e[i].get_text() == "Treasure", url
			i += 1
			pageObject["ecology"]["treasure"] = collectText(["h3", "br"]).strip()

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
				if e[nextI].name in ["h1", "h2", "h3", "b"]:
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
		# Corrupted HTML
		if url in broken_urls:
			continue

		with open(sys.argv[1] + "/" + str(i) + ".html") as file:
			html = file.read()

		try:
			pageObjects[url] = parsePage(html)
		except Exception as e:
			print(url)
			_, _, tb = sys.exc_info()
			traceback.print_tb(tb)
			print(type(e).__name__ + ": " + str(e))

	with open(sys.argv[1] + '/data.json', 'w') as fp:
		json.dump(pageObjects, fp)