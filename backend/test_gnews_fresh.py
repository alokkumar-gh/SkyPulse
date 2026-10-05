import asyncio
import httpx
import urllib.parse
import xml.etree.ElementTree as ET
import email.utils

async def test_gnews_odisha():
    headers = {"User-Agent": "Mozilla/5.0"}
    query = "Odisha weather when:3d"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN%3Aen"
    print("Testing GNews RSS URL:", url)
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url, timeout=10.0)
        print("Status code:", resp.status_code)
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        print(f"Items found: {len(items)}")
        for item in items[:10]:
            title = item.findtext("title")
            pub_date = item.findtext("pubDate")
            source = item.find("source")
            pub = source.text if source is not None else ""
            print(f"- [{pub}] {title}")
            print(f"  Published: {pub_date}")

if __name__ == "__main__":
    asyncio.run(test_gnews_odisha())
