import sys
import json


# For nice printing
def p(d):
	def set_default(obj):
		if isinstance(obj, set) or isinstance(obj, type({}.keys())):
			return list(obj)
		raise TypeError

	print(json.dumps(d, indent=2, default=set_default))

# For searching a nested dict for stuff
def search(d, s, caseSensitive=True):
	if type(d) is dict:
		return any(search(d2, s) for d2 in d.values()) or any(search(d2, s) for d2 in d.keys())
	elif type(d) is list or type(d) is set:
		return any(search(d2, s) for d2 in d)
	elif type(d) is str:
		if not caseSensitive:
			d = d.lower()
		return s in d
	else:
		return d == s



if __name__ == "__main__":
	print("Loading data...", end="", flush=True)
	with open(sys.argv[1]) as f:
		d = json.load(f)
	print(" done")

	# Filter 3.5 entries
	# print("Filtering 3.5 entries...", end="", flush=True)
	# d = {k: v for k, v in d.items() if "is_3.5" not in v}
	# print(" done")
	
	def join_nested_dicts_of_sets(l): # l is a nonempty list of nested dicts, where all leaves are sets
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
	print("Generating unique_leaves and unique_leaves_counts...", end="", flush=True)
	def generate_main_and_counts(unique_leaves_lookup, unique_leaves, unique_leaves_counts):
		for k, v in unique_leaves_lookup.items():
			if type(v[list(v.keys())[0]]) is dict: # Will break on empty sets, but those really shouldn't be in the data anyway
				unique_leaves[k] = {}
				unique_leaves_counts[k] = {}
				generate_main_and_counts(v, unique_leaves[k], unique_leaves_counts[k])
			else:
				unique_leaves[k] = set(v.keys())
				unique_leaves_counts[k] = {k2: len(v2) for k2, v2 in sorted(v.items(), key=lambda item: len(item[1]))} # Sort the counts dict for easier use
	unique_leaves = {}
	unique_leaves_counts = {}
	generate_main_and_counts(unique_leaves_lookup, unique_leaves, unique_leaves_counts)
	print(" done")









