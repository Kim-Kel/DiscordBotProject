import os
import csv
import time
from datetime import datetime
import sys
from playwright.async_api import async_playwright, Browser, Page, Playwright
from discord import Embed
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional

altdata: Dict[str, List[str]] = {}
altheader = ['alert_id', 'gamename', 'iscompleted', 'time']

if getattr(sys, 'frozen', False):
    program_dir = os.path.dirname(sys.executable)
else:
    program_dir = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(program_dir, 'altdata.csv')
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
MABIMOURL = "https://mabinogimobile.nexon.com/News/notice/GetList"
BASE_DETAIL_URL = "https://mabinogimobile.nexon.com/News/Notice/"
RATE_LIMIT = 1

# 데이터 저장, 로드
def loaddata():
    global altdata
    global altheader
    
    if not os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(altheader)
            print(f"✅ {DATA_FILE} 파일이 새로 생성되었습니다.")
        except IOError as e:
            print(f"❌ 파일 생성 중 오류 발생: {e}")
        return
        
    try:
        with open(DATA_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            if header and header != altheader:
                print(f"⚠️ 경고: 파일 헤더가 예상과 다릅니다. 현재 헤더: {header}")
            
            altdata.clear()
            for row in reader:
                if len(row) == 4:
                    alert_id = row[0]
                    values = row[1:] 
                    altdata[alert_id] = values
                else:
                    print(f"⚠️ 경고: 데이터 행의 길이가 4가 아닙니다. 이 행을 건너뜠습니다: {row}")

        print(f"✅ {len(altdata)}개의 공지 데이터를 {DATA_FILE}에서 성공적으로 로드했습니다.")
        return altdata 
    
    except IOError as e:
        print(f"❌ 파일 로드 중 오류 발생: {e}")
        return {}
    except Exception as e:
        print(f"❌ 데이터 처리 중 알 수 없는 오류 발생: {e}")
        return {}
    

def savedata():
    global altdata
    global altheader
    try:
        with open(DATA_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(altheader)
            for alert_id, values in altdata.items():
                if len(values) == 3:
                    row = [str(alert_id)] + [str(v) for v in values]
                    writer.writerow(row)
                else:
                    print(f"⚠️ 경고: Alert ID {alert_id}의 데이터 길이가 올바르지 않아 건너뛰고 저장했습니다.")
        print(f"✅ {len(altdata)}개의 공지 데이터 저장됨")
    except IOError as e:
        print(f"❌ 파일 저장 중 오류 발생: {e}")

# playwright 브라우저, 봇 감지 회피용
class pwb:
    def __init__(self):
        self.p: Optional[Playwright] = None 
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def initialize(self):
        try:
            self.p = await async_playwright().start()
            self.browser = await self.p.chromium.launch(headless=True) 
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
        except Exception as e:
            print(f"❌ Playwright 초기화 중 오류 발생: {e}")
            
    async def gethtml(self, url: str) -> Optional[str]:
        if not self.page:
            print("⚠️ Playwright 페이지가 초기화되지 않았습니다.")
            return None
        
        try:
            await self.page.goto(url, wait_until='domcontentloaded') 
            return await self.page.content()

        except Exception as e:
            print(f"fetch - 오류 발생: {e}")
            return None

    async def runjs(self, script: str, arg: Any = None) -> Any:
        if not self.page:
            print("⚠️ Playwright 페이지가 초기화되지 않았습니다.")
            return None
        try:
            if arg is not None:
                result = await self.page.evaluate(script, arg) 
            else:
                result = await self.page.evaluate(script)
            return result

        except Exception as e:
            print(f"runjs - 오류 발생: {e}")
            return None

    async def close(self):
        if self.browser:
            await self.browser.close()
            print("브라우저 인스턴스 종료")
        if self.p:
            await self.p.stop()
            print("Playwright 정리됨")

# 모비 홈페이지 크롤링
async def mabimo_getnotice(pbrowser: pwb) -> Optional[List[Dict[str, Any]]]:
    await pbrowser.gethtml(MABIMOURL)
    content = await pbrowser.runjs("""
(async () => {
    try {
        const mmhome = 'https://mabinogimobile.nexon.com/News/notice/GetList';
        const formData = new FormData();
        formData.append('headlineId', '');
        formData.append('directionType', 'DEFAULT');
        formData.append('pageno', '1');
        
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': '*/*',
            'x-requested-with': 'XMLHttpRequest'
        };

        const response = await fetch(mmhome, {
            method: 'POST',
            headers: headers,
            body: formData
        });

        if (!response.ok) {
            console.error(`오류 발생: ${response.status} ${response.statusText}`);
            return null;
        }
        
        const responseText = await response.text();
        return responseText;

    } catch (error) {
        console.error("네트워크 요청 중 오류 발생:", error);
        return null;
    }
})();
""")
    # -----------------------------------------------------------

    if content is None:
        print("웹페이지 로드 중 오류 발생")
        return None
        
    try:
        wlist = BeautifulSoup(content, 'html.parser')
    except Exception as e:
        print(f"BeautifulSoup 초기화 중 오류 발생: {e}")
        return None

    if not wlist:
        print("ERROR: 웹페이지 파싱 중 오류 발생")
        return None

    titletags = wlist.find_all('a', class_='title')
    
    if titletags:
        rst = []
        for tag in titletags:
            isdone = False
            title = tag.get_text(strip=True)

            if title.find("점검") == -1:
                continue
            
            thread_id = tag.attrs.get('onclick', '')
            if thread_id.find('Thread.link(') != -1:
                try:
                    thread_id = thread_id.split('Thread.link(')[1].split(',')[0].strip().replace("'", "")
                except (IndexError, TypeError):
                    continue
            else:
                continue
            
            if title.find("(완료)") != -1:
                isdone = True

            turl = ""
            if thread_id:
                turl = f"{BASE_DETAIL_URL}{thread_id}"
            
            rst.append({'title': title, 'url': turl, 'isdone': isdone})
            
        return rst
    else:
        print("페이지에서 제목 태그를 찾을 수 없습니다.")
        return None

async def mabimo_checknotice(pbrowser: pwb) -> List[Any]:
    global altdata
    
    ulist = await mabimo_getnotice(pbrowser)
    newnot_found = False
    embed_to_send = None
    
    if ulist is None or len(ulist) == 0:
        return [False, None]
        
    timenow_str = str(int(time.time())) 
    
    for notice in ulist:
        title = notice['title']
        url = notice['url']
        is_done_ulist = notice['isdone'] # (True/False)
        
        try:
            notice_id = url.split('/')[-1]
            if not notice_id.isdigit():
                continue
        except (AttributeError, IndexError):
            continue
            
        if notice_id not in altdata:
            newnot_found = True
            
            embed_to_send = Embed(
                title="**점검 공지가 있습니다!**", 
                description=f"{title}", 
                url=url,
                color=0xfc6e00
            )
            
            print(f"신규 공지 발견됨: {title}")
            
            initial_is_completed = 'T' if is_done_ulist else 'F'
            altdata[notice_id] = [
                'mabimo', 
                initial_is_completed,
                timenow_str
            ]
            
            break
            
        else:
            altdata_is_completed = altdata[notice_id][1]
            
            if is_done_ulist is True and altdata_is_completed == 'F':
                newnot_found = True
                
                embed_to_send = Embed(
                    title="**점검이 끝났습니다!**", 
                    description=f"{title}", 
                    url=url,
                    color=0x00be80
                )
                
                print(f"완료된 공지 발견됨: {title}")
                
                altdata[notice_id][1] = 'T'
                altdata[notice_id][2] = timenow_str
                
                break 

    if newnot_found:
        savedata()
        
    return [newnot_found, embed_to_send]
