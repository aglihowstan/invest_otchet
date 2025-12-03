import asyncio, json, httpx
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", 0)
STATE_FILE = "report_state.json"


# --- УТИЛИТЫ И ПАРСИНГ ---
def get_state():
    try:
        return json.load(open(STATE_FILE, 'r', encoding='utf-8'))
    except:
        return {}


def save_state(data):
    json.dump(data, open(STATE_FILE, 'w', encoding='utf-8'), indent=2)


def fetch_page(url):
    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            return client.get(url, headers={"User-Agent": "Mozilla/5.0"}).text
    except Exception as e:
        print(f"[!] Ошибка {url}: {e}")


def parse_yandex(html):
    if not html: return None
    try:
        soup = BeautifulSoup(html, 'lxml')
        art = soup.find('article', class_='financials-list__item')
        if not art: return None

        # Данные
        title = art.find('a', class_='financials-list__title-link').get_text(strip=True)
        date = art.find('span', class_='date').get_text(strip=True)
        files = [{"name": s.get_text(strip=True), "url": a['href']}
                 for a in art.find_all('a', class_='doc')
                 if (s := a.find('span', class_='doc__name')) and a.get('href')]

        if not files: return None
        return {"title": f"{title} ({date})", "id": files[0]['url'], "files": files}
    except:
        return None


COMPANIES = {
    "yandex": {"name": "Яндекс", "url": "https://ir.yandex.ru/", "parser": parse_yandex},
}


# --- ЛОГИКА ОТПРАВКИ И ЗАПУСКА ---
async def send_files(bot, report, name):
    """Шлёт уведомление и файлы."""
    await bot.send_message(ADMIN_ID, f"🔔 <b>Новый отчет: {name}</b>\n{report['title']}", parse_mode=ParseMode.HTML)

    for f in report['files']:
        try:
            if f['url'].endswith(('.pdf', '.jpg')):
                with httpx.Client(timeout=15) as c:
                    content = c.get(f['url']).content
                await bot.send_document(ADMIN_ID, content, filename=f['url'].split('/')[-1], caption=f['name'])
            else:
                raise Exception("Not a PDF/JPG")
        except:
            await bot.send_message(ADMIN_ID, f"📄 {f['name']}\n{f['url']}")


async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    state = get_state()
    has_changes = False

    print("--- Cron запущен ---")
    for key, cfg in COMPANIES.items():
        if (report := cfg['parser'](fetch_page(cfg['url']))) and report['id'] != state.get(key):
            print(f"[+] Найден новый отчет: {cfg['name']}")
            await send_files(bot, report, cfg['name'])
            state[key] = report['id']
            has_changes = True
        else:
            print(f"[.] {cfg['name']}: изменений нет")

    if has_changes: save_state(state)
    print("--- Работа завершена ---")


if __name__ == "__main__":
    asyncio.run(main())