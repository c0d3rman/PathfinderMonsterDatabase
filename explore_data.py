import sys
import json
from functools import reduce
import operator
import copy
from tqdm import tqdm


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
	for keylist in tqdm(leaf_keys):
		# Skip sources because dicts in lists is a headache
		if keylist[0] == "sources":
			continue

		subd = unique_leaves
		for key in keylist[:-1]:
			if not key in subd:
				subd[key] = {}
			subd = subd[key]
		subd[keylist[-1]] = set()
		
		for d2 in d.values():
			if get_from_dict(d2, keylist) is not False:
				val = get_from_dict(d2, keylist)
				if type(val) is not list:
					val = [val]
				get_from_dict(unique_leaves, keylist).update(set(val))

	print("Constructing reverse lookup map and count map...")
	unique_leaf_value_lookup = copy.deepcopy(unique_leaves)
	unique_leaf_value_counts = copy.deepcopy(unique_leaves)
	for keylist in tqdm(leaf_keys):
		leafset = get_from_dict(unique_leaves, keylist)
		if leafset is False: # For sources
			continue
		subd = {}
		subd2 = {}
		get_from_dict(unique_leaf_value_lookup, keylist[:-1])[keylist[-1]] = subd
		get_from_dict(unique_leaf_value_counts, keylist[:-1])[keylist[-1]] = subd2

		for val in leafset:
			subd[val] = []
			subd2[val] = 0
			for k, v in d.items():
				candidate = get_from_dict(v, keylist)
				if ((type(candidate) is list or type(candidate) is set) and val in candidate) or candidate == val:
					subd[val].append(k)
					subd2[val] += 1