import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json
import re
from colorama import init, Fore, Back, Style

MAX_CONCURRENT_REQUESTS = 2



init()  # Initialize Colorama




async def fetch(session, url, retries=3):
    for attempt in range(retries):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:
                    await asyncio.sleep(5)
                else:
                    print(f"Ошибка при запросе {url}: статус {response.status}")
                    break
        except Exception as e:
            print(f"Попытка {attempt + 1} не удалась для {url}: {e}")
            await asyncio.sleep(2)
    return None

async def parse_item(session, item, semaphore):
    link = item.get('href')
    node_ids = []
    detailed_description_text = None  
    detailed_description_text_ru = None  

    if link:
        async with semaphore:  
            respo = await fetch(session, link)
        
        if respo and 'ошибка' not in respo.lower():
            soup_ru = BeautifulSoup(respo, 'html.parser')
            
            if soup_ru:
                await asyncio.sleep(2)
                
                node_elements = soup_ru.find_all(class_='back-link')
                
                for n in node_elements:
                    linkd = n.find('a')['href']
                    match = re.search(r'lots/(\d+)', linkd)
                    if match:
                        node_ids.append(match.group(1))
                    else:
                        print("Совпадение не найдено для:", linkd)

                param_items = soup_ru.find_all(class_='param-item')
               
                for param in param_items:
                    if "Detailed description" in param.get_text(strip=True):
                        detailed_description_text = param.get_text(strip=True).replace("Detailed description", "").strip()
                        
                        link = link.replace("funpay.com/en/", "funpay.com/ru/")
                 

                        respo_ru = await fetch(session, link)

                        if respo_ru and 'ошибка' not in respo_ru.lower():
                            soup_ru_new = BeautifulSoup(respo_ru, 'html.parser')
                            param_items_ru = soup_ru_new.find_all(class_='param-item')

                            for param in param_items_ru:
                                if "Подробное описание" in param.get_text(strip=True):
                                    detailed_description_text_ru = param.get_text(strip=True).replace("Подробное описание", "").strip()
                                    
                            break 

    return node_ids, detailed_description_text, detailed_description_text_ru  

async def main():
    linkd = input(Fore.YELLOW + 'Введите ссылку на профиль Funpay: ' + Style.RESET_ALL)
    l_ru = linkd
  
    if "funpay.com/" in linkd:
        linkd = linkd.replace("funpay.com/", "funpay.com/en/")
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    async with aiohttp.ClientSession() as session:
        response = await fetch(session, linkd)
        
        if response:
            soup = BeautifulSoup(response, 'html.parser')
            tc_items = soup.find_all(class_='tc-item')
            descriptions = []

            tasks = [parse_item(session, item, semaphore) for item in tc_items]
            results = await asyncio.gather(*tasks)
            
            for i, item in enumerate(tc_items):
                tc_desc_text_en = item.find(class_='tc-desc-text')
                amount_element = item.find(class_='tc-amount hidden-xxs')
                amount = amount_element.get_text(strip=True) if amount_element else "Не ограничено"
                
                node_ids_list, detailed_description_text, detailed_description_text_ru = results[i]
                
                if tc_desc_text_en:
                    description_entry = {
                        "fields[summary][en]": tc_desc_text_en.get_text(strip=True),
                        "fields[summary][ru]": "",
                        "price": "",
                        "amount": amount,
                        "node_id": node_ids_list[0] if node_ids_list else "",
                        "detailed_description[en]": detailed_description_text or "",
                        "detailed_description[ru]": detailed_description_text_ru
                        
                    }
                    descriptions.append(description_entry)

            
            with open("funpay.json", "w", encoding="utf-8") as json_file:
                json.dump(descriptions, json_file, ensure_ascii=False, indent=4)

            

           
            response_ru = await fetch(session, l_ru)
            
            if response_ru:
                soup_ru = BeautifulSoup(response_ru, 'html.parser')
                tc_items_ru = soup_ru.find_all(class_='tc-item')

                
                with open("funpay.json", "r", encoding="utf-8") as json_file:
                    existing_descriptions = json.load(json_file)

                for i, item in enumerate(tc_items_ru):
                    tc_desc_text_ru = item.find(class_='tc-desc-text')
                    price = item.find(class_="tc-price")
                    
                    if tc_desc_text_ru and i < len(existing_descriptions):
                        existing_descriptions[i]["fields[summary][ru]"] = tc_desc_text_ru.get_text(strip=True)
                        if price:
                            existing_descriptions[i]["price"] = price.get_text(strip=True)  

                
                with open("funpay.json", "w", encoding="utf-8") as json_file:
                    json.dump(existing_descriptions, json_file, ensure_ascii=False, indent=4)
                print(Fore.GREEN + 'Успешно спаршено и сохранено в файл funpay.json' + Style.RESET_ALL)

                
            else:
                print(f"Не удалось получить русскую страницу.")
        else:
            print(f"Не удалось получить английскую страницу.")

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())