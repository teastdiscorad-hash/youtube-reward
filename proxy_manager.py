import re
import random
import logging
import requests
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("proxy_manager")
logger.setLevel(logging.INFO)

PROXY_SOURCES = [
    'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=3500&country=all&ssl=all&anonymity=all',
    'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all.txt',
    'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
    'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt',
    'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt',
    'https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt'
]

class ProxyManager:
    def __init__(self, max_proxies=150):
        self.working_proxies = []
        self.max_proxies = max_proxies
        self._lock = threading.Lock()
        self._is_fetching = False

    def validate_proxy(self, proxy_str: str) -> bool:
        """
        فحص البروكسي عن طريق إرسال طلب لـ Discord API
        """
        proxy_url = proxy_str if proxy_str.startswith('http') else f"http://{proxy_str}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        try:
            res = requests.get(
                'https://discord.com/api/v9/invites/test',
                proxies=proxies,
                timeout=2.5,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            # 200 (Success), 404 (Not Found but reached Discord), 429 (Rate Limited by Discord) - all mean proxy works
            if res.status_code in [200, 404, 429]:
                return True
        except Exception:
            return False
        return False

    def _fetch_and_filter(self):
        with self._lock:
            if self._is_fetching:
                return
            self._is_fetching = True

        candidate_proxies = []
        try:
            logger.info("جاري سحب البروكسيات من المصادر المفتوحة...")
            for source in PROXY_SOURCES:
                try:
                    res = requests.get(source, timeout=5)
                    if res.status_code == 200:
                        lines = [line.strip() for line in res.text.splitlines() if ':' in line]
                        candidate_proxies.extend(lines)
                except Exception as e:
                    logger.debug(f"Failed to fetch from {source}: {e}")

            # إزالة التكرار وخلط القائمة
            candidate_proxies = list(set(candidate_proxies))
            random.shuffle(candidate_proxies)

            logger.info(f"تم سحب {len(candidate_proxies)} بروكسي. جاري الفحص...")

            new_working = []
            with ThreadPoolExecutor(max_workers=25) as executor:
                # نفحص فقط أول 500 كحد أقصى لتوفير الوقت
                results = executor.map(self._test_and_return, candidate_proxies[:500])
                for proxy in results:
                    if proxy:
                        new_working.append(proxy)
                        if len(new_working) + len(self.working_proxies) >= self.max_proxies:
                            break

            with self._lock:
                # دمج البروكسيات الجديدة مع الشغالة سابقاً بدون تكرار
                current_set = set(self.working_proxies)
                for p in new_working:
                    if p not in current_set:
                        self.working_proxies.append(p)
                logger.info(f"تم فحص البروكسيات بنجاح. إجمالي البروكسيات الشغالة: {len(self.working_proxies)}")
        finally:
            with self._lock:
                self._is_fetching = False

    def _test_and_return(self, proxy_str):
        if self.validate_proxy(proxy_str):
            logger.info(f"✅ بروكسي شغال: {proxy_str}")
            return proxy_str
        return None

    def get_proxy(self):
        """
        الحصول على بروكسي عشوائي من القائمة. إذا كانت القائمة فارغة سيقوم بجلب المزيد.
        """
        with self._lock:
            count = len(self.working_proxies)
            is_fetching = self._is_fetching
            
        if count == 0:
            # إذا لم يكن هناك بروكسيات، نضطر للانتظار
            if not is_fetching:
                self._fetch_and_filter()
            else:
                # ننتظر قليلاً إذا كان الفحص جارياً
                import time
                for _ in range(30):
                    time.sleep(1)
                    if len(self.working_proxies) > 0:
                        break
        elif count < 5 and not is_fetching:
            # تشغيل الجلب في الخلفية إذا كان العدد قليل
            threading.Thread(target=self._fetch_and_filter, daemon=True).start()

        with self._lock:
            if not self.working_proxies:
                return None
            return random.choice(self.working_proxies)

    def remove_proxy(self, proxy_str: str):
        """
        إزالة البروكسي من القائمة إذا فشل
        """
        if not proxy_str:
            return
            
        # Clean protocol if added by yt-dlp config
        proxy_str = proxy_str.replace('http://', '').replace('https://', '')
        
        with self._lock:
            if proxy_str in self.working_proxies:
                self.working_proxies.remove(proxy_str)
                logger.warning(f"❌ تم حذف البروكسي المتعطل: {proxy_str}")

# Global instance
proxy_manager = ProxyManager()
