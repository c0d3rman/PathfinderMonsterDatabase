from bs4 import BeautifulSoup
import requests
import sys
import traceback
from urllib.parse import quote


if __name__ == "__main__":
	url = sys.argv[1]
	outfile = sys.argv[2]

	# Download page
	try:
		html = requests.get(url).text
	except requests.exceptions.RequestException as e:
		print(url)
		_, _, tb = sys.exc_info()
		traceback.print_tb(tb)
		print(type(e).__name__ + ": " + str(e))

	# Parse page
	soup = BeautifulSoup(html, "html.parser")
	elems = soup.select("#main table tr td:first-child a")
	urls = [e['href'].split("=")[0] + "=" + quote(e['href'].split("=")[1], safe='/()') for e in elems]
	urls = [("" if u.startswith("https://aonprd.com/") else "https://aonprd.com/") + u for u in urls]
	
	# Remove duplicates
	urls = list(set(urls))

	# Write the URL list to disk
	with open(outfile, 'w') as fp:
		fp.write("\n".join(urls))