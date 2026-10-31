import sys, json, email.utils, xml.etree.ElementTree as ET
since = int(sys.argv[1])
items = []
try:
    root = ET.fromstring(sys.stdin.read())
    for item in root.iter("item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        when = email.utils.parsedate_to_datetime(item.findtext("pubDate", "")).timestamp()
        if when > since and "manual intervention" in title.lower():
            items.append({"title": title, "link": link})
except Exception:
    pass
print(json.dumps(items))
