import sys
import json
import csv
from explore_data import generate_lookups, generate_main_and_counts
from copy import deepcopy



if __name__ == "__main__":
	if len(sys.argv) > 1:
		datapath = sys.argv[1]
	else:
		datapath = "data/data.json"

	print("Loading data...", end="", flush=True)
	with open(datapath) as f:
		d = json.load(f)
	print(" done")

	# Filter 3.5 entries
	# print("Filtering 3.5 entries...", end="", flush=True)
	# d = {k: v for k, v in d.items() if "is_3.5" not in v}
	# print(" done")

	print("Generating unique_leaves_lookup...", end="", flush=True)
	unique_leaves_lookup = generate_lookups(d)
	print(" done")

	# Use lookups to generate counts and the main dict
	# Will break on empty dicts or lists, but those really shouldn't be in the data anyway
	print("Generating unique_leaves and unique_leaves_counts...", end="", flush=True)
	unique_leaves = deepcopy(unique_leaves_lookup)
	unique_leaves_counts = deepcopy(unique_leaves_lookup)
	def generate_main_and_counts(d1, d2):
		assert type(d1) is dict

		# Base case: dict with set values
		if type(d1[list(d1.keys())[0]]) is set: # Assume d1 and d2 synced
			return True

		for k in d1:
			if generate_main_and_counts(d1[k], d2[k]):
				d1[k] = list(d1[k].keys())
				d2[k] = {k2: len(v2) for k2, v2 in d2[k].items()}

		return False

	generate_main_and_counts(unique_leaves, unique_leaves_counts)
	print(" done")




	# Edit the data a bit
	for k in d:
		if "special_abilities" in d[k]:
			d[k]["special_abilities"] = [k + ": " + v for k, v in d[k]["special_abilities"].items()]

		if "skills" in d[k] and "_racial_mods" in d[k]["skills"]:
			d[k]["racial_mods"] = str(d[k]["skills"]["_racial_mods"])
			del d[k]["skills"]["_racial_mods"]

		if "skills" in d[k]:
			keys = list(d[k]["skills"].keys())
			for skill in keys:
				for cat in d[k]["skills"][skill]:
					if cat != "_":
						if not "other" in d[k]["skills"]:
							d[k]["skills"]["other"] = {}
						d[k]["skills"]["other"][skill + "_" + cat] = d[k]["skills"][skill][cat]
				if "_" in d[k]["skills"][skill]:
					d[k]["skills"][skill] = d[k]["skills"][skill]["_"]
				else:
					del d[k]["skills"][skill]
			if "other" in d[k]["skills"]:
				d[k]["skills"]["other"] = str(d[k]["skills"]["other"])

		if "senses" in d[k]:
			keys = list(d[k]["senses"].keys())
			for sense in keys:
				if sum(unique_leaves_counts["senses"][sense].values()) > 10:
					continue

				if not "other" in d[k]["senses"]:
					d[k]["senses"]["other"] = {}
				d[k]["senses"]["other"][sense] = d[k]["senses"][sense]
				del d[k]["senses"][sense]
			if "other" in d[k]["senses"]:
				d[k]["senses"]["other"] = str(d[k]["senses"]["other"])

		if "feats" in d[k]:
			d[k]["feats"] = ", ".join(f["name"] for f in d[k]["feats"])

		if "languages" in d[k]:
			d[k]["languages"] = ", ".join(d[k]["languages"])

		if "immunities" in d[k]:
			d[k]["immunities"] = ", ".join(d[k]["immunities"])

		if "other" in d[k]["initiative"]:
			d[k]["initiative"]["other"] = str(d[k]["initiative"]["other"])

		if "kineticist_wild_talents" in d[k]:
			d[k]["kineticist_wild_talents"] = str(d[k]["kineticist_wild_talents"])

	def getListCounts(d, out, key=""):
		if type(d) is dict:
			for k, v in d.items():
				getListCounts(v, out, key=key + "/" + k)
		elif type(d) is list or type(d) is set:
			if not key in out:
				out[key] = -1
			out[key] = max(out[key], len(d))
		else:
			pass

	def flatten(d, listCounts, key=""):
		out = {}
		if type(d) is dict:
			for k, v in d.items():
				out.update(flatten(v, listCounts, key=key + "/" + k))
		elif type(d) is list or type(d) is set:
			if not key in listCounts or listCounts[key] >= 10:
				out[key] = str(d)
			else:
				for i in range(len(d)):
					out.update(flatten(d[i], listCounts, key=key + "_" + str(i + 1)))
		else:
			out[key] = d
		return out

	print("Generating csv...", end="", flush=True)
	listCounts = {}
	for v in d.values():
		getListCounts(v, listCounts)
	l = []
	for k in d:
		row = flatten(d[k], listCounts)
		row = {k[1:]: v for k, v in row.items()} # Strip starting slash
		row["URL"] = k
		l.append(row)
	print(" done")

	l = sorted(l, key=lambda row: row["title2"])

	print("Writing csv...", end="", flush=True)
	a_file = open("data/output.csv", "w")
	keys = sorted(list(set().union(*[set(d.keys()) for d in l])))
	manual_first_keys = ["title2", "CR", "type", "URL"]
	for i in range(len(manual_first_keys)):
		keys.pop(keys.index(manual_first_keys[i]))
	keys = manual_first_keys + keys
	dict_writer = csv.DictWriter(a_file, keys)
	dict_writer.writeheader()
	dict_writer.writerows(l)
	print(" done")