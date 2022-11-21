import sys
import json
from copy import deepcopy
import regex as re
from pprint import pprint # Alternative printing option that sorts dicts


# For nice printing
def sort_lists(item):
	if isinstance(item, set) or isinstance(item, type({}.keys())):
		return sorted(list(item))
	elif isinstance(item, list):
		try:
			return sorted(sort_lists(i) for i in item)
		except TypeError: # This handles cases like a list of dicts, where the dicts can't be compared against each other to sort them
			return [sort_lists(i) for i in item]
	elif isinstance(item, dict):
		return {k: sort_lists(v) for k, v in item.items()}
	else:
		return item
class SortedListEncoder(json.JSONEncoder):
	def encode(self, obj):
		return super(SortedListEncoder, self).encode(sort_lists(obj))
def p(d):
	print(json.dumps(d, indent=2, cls=SortedListEncoder))

# For searching a nested dict for stuff
def search(d, s, caseSensitive=True, regex=False):
	if type(d) is dict:
		out = {}
		for k, v in d.items():
			t = search(v, s, caseSensitive=caseSensitive, regex=regex)
			if t:
				out[k] = t
				continue
			t = search(k, s, caseSensitive=caseSensitive, regex=regex)
			if t:
				out[k] = t
				continue
		if len(out) > 0:
			return out
	elif type(d) is list or type(d) is set:
		out = []
		for d2 in d:
			t = search(d2, s, caseSensitive=caseSensitive, regex=regex)
			if t:
				out.append(t)
		if len(out) > 0:
			return out
	elif type(d) is str:
		if not regex:
			d2 = d
			if not caseSensitive:
				d2 = d2.lower()
				s = s.lower()
			if s in d2:
				return d
		else:
			if re.search(s, d, (0 if caseSensitive else re.I)):
				return d
	else:
		if d == s:
			return d


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

	generate_main_and_counts(unique_leaves, unique_leaves_counts)
	print(" done")









