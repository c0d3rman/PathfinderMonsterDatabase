import requests
import time
import sys
import traceback
from tqdm import tqdm
import os


if __name__ == "__main__":
	urls = []
	with open(sys.argv[1]) as file:
		for line in file:
			urls.append(line.rstrip())
	
	# Remove duplicates
	urls = list(set(urls))

	if not os.path.exists("data"):
		os.makedirs("data")

	# Write a copy of the URL list to the data folder
	with open('data/urls.txt', 'w') as fp:
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

		with open('data/' + str(i) + '.html', 'w') as fp:
			fp.write(html)


		# Avoid getting rate limited
		if tSpent < 0.2:
			print("Sleeping " + str(0.2 - tSpent) + "s")
			time.sleep(0.2 - tSpent)