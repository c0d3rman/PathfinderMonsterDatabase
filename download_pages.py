import requests
import time
import sys
import traceback
from tqdm import tqdm
import os
from pathlib import Path


MAX_REQUESTS_PER_SECOND = 5


if __name__ == "__main__":
	if len(sys.argv) > 1:
		urllistpath = sys.argv[1]
	else:
		urllistpath = "data/urls.txt"
	if len(sys.argv) > 2:
		outdir = sys.argv[2]
	else:
		outdir = "data/"


	urls = []
	with open(urllistpath) as file:
		for line in file:
			urls.append(line.rstrip())
	
	# Remove duplicates and sort
	urls = sorted(list(set(urls)))

	# Create output directory if it doesn't exist
	Path(outdir).mkdir(parents=True, exist_ok=True)

	# Write a copy of the URL list to the data folder if one does not exist
	if not os.path.isfile(os.path.join(outdir, "urls.txt")):
		with open(os.path.join(outdir, "urls.txt"), 'w') as fp:
			fp.write("\n".join(urls))

	for i, url in enumerate(tqdm(urls)):
		t = time.time()
		try:
			html = requests.get(url).text
		except requests.exceptions.RequestException as e:
			print(url)
			_, _, tb = sys.exc_info()
			traceback.print_tb(tb)
			print(type(e).__name__ + ": " + str(e))
		tSpent = time.time() - t

		with open(os.path.join(outdir, str(i) + '.html'), 'w') as fp:
			fp.write(html)

		# Avoid getting rate limited
		if tSpent < 1 / MAX_REQUESTS_PER_SECOND:
			time.sleep(1 / MAX_REQUESTS_PER_SECOND - tSpent)