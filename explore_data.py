import sys
import json
from functools import reduce
import operator
import copy
from tqdm import tqdm
import itertools


if __name__ == "__main__":
	with open(sys.argv[1]) as f:
		d = json.load(f)

	# Filter 3.5 entries
	d = {k: v for k, v in d.items() if "is_3.5" not in v}

	def recursive_leaf_finder(d, keylist=[], outset=set()):
		sub = reduce(operator.getitem, keylist, d)

		if type(sub) is not dict:
			outset.add(tuple(keylist[1:])) # Cut off first key because it's the unique URL. Tuple for hashability
			return

		for k in sub:
			keylist.append(k)
			recursive_leaf_finder(d, keylist, outset)
			keylist.pop()

		return outset

	print("Getting all leaf keys...", end="")
	leaf_keys = recursive_leaf_finder(d)
	print(" done")

	def get_from_dict(d, keylist):
		i = 0
		while i < len(keylist):
			if not keylist[i] in d:
				return False # Use this instead of None because there might be legitimate Nones in the data (check with "is False")
			d = d[keylist[i]]
			i += 1
		return d

	print("Getting all unique leaves...")
	unique_leaves = {}
	unique_leaves_lookup = {}
	unique_leaves_counts = {}
	for keylist in tqdm(leaf_keys):
		# Skip sources because dicts in lists is a headache
		if keylist[0] == "sources":
			continue

		subd = unique_leaves
		for subd in [unique_leaves, unique_leaves_lookup, unique_leaves_counts]:
			for key in keylist[:-1]:
				if not key in subd:
					subd[key] = {}
				subd = subd[key]
			
		get_from_dict(unique_leaves, keylist[:-1])[keylist[-1]] = set()
		get_from_dict(unique_leaves_lookup, keylist[:-1])[keylist[-1]] = {}
		get_from_dict(unique_leaves_counts, keylist[:-1])[keylist[-1]] = {}
		
		for k, v in d.items():
			val = get_from_dict(v, keylist)
			if val is not False:
				if type(val) is list and any(isinstance(x, list) or isinstance(x, set) for x in val): # Flatten lists of lists (e.g. attacks_melee)
					val = set(itertools.chain.from_iterable(val))
				elif type(val) is not set and type(val) is not list:
					val = set([val])

				get_from_dict(unique_leaves, keylist).update(val)

				for subval in val:
					d_lookup = get_from_dict(unique_leaves_lookup, keylist)
					if not subval in d_lookup:
						d_lookup[subval] = []
					d_lookup[subval].append(k)

					d_counts = get_from_dict(unique_leaves_counts, keylist)
					if not subval in d_counts:
						d_counts[subval] = 0
					d_counts[subval] += 1

# For nice printing
def p(d):
	print(json.dumps(d, indent=2))

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
