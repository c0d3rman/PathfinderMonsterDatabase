import sys
import json
from copy import deepcopy


# For nice printing
def p(d):
	def set_default(obj):
		if isinstance(obj, set) or isinstance(obj, type({}.keys())):
			return sorted(list(obj))
		raise TypeError

	print(json.dumps(d, indent=2, default=set_default))

# For searching a nested dict for stuff
def contains(d, s, caseSensitive=True):
	if type(d) is dict:
		return any(contains(d2, s, caseSensitive=caseSensitive) for d2 in d.values()) or any(contains(d2, s, caseSensitive=caseSensitive) for d2 in d.keys())
	elif type(d) is list or type(d) is set:
		return any(contains(d2, s, caseSensitive=caseSensitive) for d2 in d)
	elif type(d) is str:
		if not caseSensitive:
			d = d.lower()
		return s in d
	else:
		return d == s

def search(d, s, caseSensitive=True):
	if type(d) is dict:
		out = {}
		for k, v in d.items():
			t = search(v, s, caseSensitive=caseSensitive)
			if t:
				out[k] = t
				continue
			t = search(k, s, caseSensitive=caseSensitive)
			if t:
				out[k] = t
				continue
		if len(out) > 0:
			return out
	elif type(d) is list or type(d) is set:
		out = []
		for d2 in d:
			t = search(d2, s, caseSensitive=caseSensitive)
			if t:
				out.append(t)
		if len(out) > 0:
			return out
	elif type(d) is str:
		d2 = d
		if not caseSensitive:
			d2 = d2.lower()
			s = s.lower()
		if s in d2:
			return d
	else:
		if d == s:
			return d



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
	
	def join_nested_dicts_of_sets(l): # l is a list of nested dicts, where all leaves are sets
		if len(l) == 0:
			return {}
		if type(l[0]) is set:
			return set().union(*[x for x in l])

		d1 = {}
		for k in set().union(*[set(d2.keys()) for d2 in l]):
			d1[k] = join_nested_dicts_of_sets([d2[k] for d2 in l if k in d2])
		return d1

	def generate_lookups(d, url=None): # url param is for internal use and should not be set by the caller
		if url is None: # We're at the top
			return join_nested_dicts_of_sets([generate_lookups(v, url=k) for k, v in d.items()])

		if type(d) is dict:
			return {k: generate_lookups(v, url=url) for k, v in d.items()}
		elif type(d) is list or type(d) is set:
			return join_nested_dicts_of_sets([generate_lookups(x, url=url) for x in d])
		else:
			return {d: set([url])}

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









