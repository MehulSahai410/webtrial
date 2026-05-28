# import asyncio
# from requests_html import HTMLSession
# asyncio.set_event_loop(asyncio.new_event_loop())
# session=HTMLSession()
# url='https://news.google.com/foryou?hl=en-IN&gl=IN&ceid=IN%3Aen'
# r=session.get(url)
# r.html.render(sleep=1, scrolldown=5 )
# articles=r.html.find('article')
# print(articles)
from playwright.sync_api import sync_playwright

def scrape_google_news():
    with sync_playwright() as p:
        # 1. Launch the Playwright browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 2. Go to your target URL (Google News)
        print("Loading Google News...")
        page.goto('https://news.google.com/foryou?hl=en-IN&gl=IN&ceid=IN%3Aen')
        
        # 3. Replicate your "scrolldown=5" and "sleep=1"
        # Google News uses infinite scroll, so we scroll down 5 times, waiting 1 second each time
        print("Scrolling down to load articles...")
        for _ in range(5):
            page.mouse.wheel(0, 2000) # Scroll down
            page.wait_for_timeout(1000) # Wait 1 second (1000 ms)
        
        # 4. Extract all the links on the page
        # This grabs the 'href' attribute from every 'a' (anchor) tag
        all_links = page.locator('a').evaluate_all("elements => elements.map(e => e.href)")
        
        # requests_html automatically removed duplicates, so we use set() to do the same!
        unique_links = set(all_links)
        
        print(f"\nIt worked! Found {len(unique_links)} unique links.")
        print("Here are the first 15 links (so it doesn't flood your terminal):")
        
        # Print just the first 15 links
        for link in list(unique_links)[:15]:
            print(link)
            
        browser.close()

# Run the function
scrape_google_news()