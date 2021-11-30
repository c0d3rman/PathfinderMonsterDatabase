import sys
import json
from functools import reduce
import operator
import copy
from tqdm import tqdm
import itertools


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

	# def process_unique_leaves_recursively(d, unique_leaves, unique_leaves_lookup, unique_leaves_counts):
	# 	if type(d) is dict:
	# 		for k, v in d.items():
	# 			for subd in [unique_leaves, unique_leaves_lookup, unique_leaves_counts]:
	# 				if not k in subd:
	# 					subd[k] = {}

	# 			o = process_unique_leaves_recursively(v, unique_leaves[k], unique_leaves_lookup[k], unique_leaves_counts[k])
	# 			if type(o) is set: # It's a leaf
	# 				if not type(unique_leaves[k]) is set:
	# 					assert len(unique_leaves[k]) == 0
	# 					unique_leaves[k] = set()
	# 				unique_leaves[k].update(o)
	# 			else:
	# 				assert type(o) is dict
	# 	elif type(d) is list or type(d) is set:

	# 		for v in d.items():
	# 			o = process_unique_leaves_recursively(v, unique_leaves, unique_leaves_lookup, unique_leaves_counts)
	# 			if type(o) is set: # It's a leaf

	def join_nested_dicts_of_sets(l): # l is a nonempty list of nested dicts, where all leaves are sets
		if type(l[0]) is set:
			return set().union(*[x for x in l])

		d1 = {}
		for k in set().union(*[set(d2.keys()) for d2 in l]):
			d1[k] = join_nested_dicts_of_sets([d2[k] for d2 in l if k in d2])
		return d1
	
	# d1 = {
	# 	"a": {
	# 		"X": {
	# 			"o1": set([1, 2, 3]),
	# 			"o2": set([3, 5])
	# 		},
	# 		"Y": set([99])
	# 	},
	# 	"b": set([10, 5]),
	# 	"d": {}
	# }
	# d2 = {
	# 	"a": {
	# 		"X": {
	# 			"o1": set([3, 91, 92]),
	# 			"o3": set([9, 100])
	# 		},
	# 		"Z": {
	# 			"k1": set([3]),
	# 			"k2": set([-1, -2])
	# 		}
	# 	},
	# 	"b": set([11, 55]),
	# 	"c": set([88]),
	# 	"d": {}
	# }
	# print(join_nested_dicts_of_sets([d1, d2]))

	def semi_flatten_nested_data(d, url=None):
		if url is None: # We're at the top
			return join_nested_dicts_of_sets([semi_flatten_nested_data(v, url=k) for k, v in d.items()])

		if type(d) is dict:
			return {k: semi_flatten_nested_data(v, url=url) for k, v in d.items()}
		elif type(d) is list or type(d) is set:
			return join_nested_dicts_of_sets([semi_flatten_nested_data(x, url=url) for x in d])
		else:
			return {d: set([url])}

	# testd = [
	# 	{
	# 		"a": [
	# 			{
	# 				"X": [1, 2, 3]
	# 			},
	# 			{
	# 				"Y": [4, 5, 6]
	# 			}
	# 		],
	# 		"b": 10,
	# 	},
	# 	{
	# 		"a": [
	# 			{
	# 				"X": [2, 5]
	# 			},
	# 			{
	# 				"Z": [3, 4]
	# 			}
	# 		],
	# 		"b": 5,
	# 	}
	# ]

	unique_leaves_lookup = semi_flatten_nested_data(d)