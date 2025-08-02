#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time
import random
from bs4 import BeautifulSoup

def collect_game_links():
    # Читаем компании
    company_ids = []
    with open('companies.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ':' in line:
                company_id = line.split(':', 1)[0].strip()
                company_ids.append(company_id)
    
    print(f"Всего компаний: {len(company_ids)}")
    
    # Берем только первые 40 компаний для теста
    #company_ids = company_ids[:40]
    print(f"Тестируем на первых {len(company_ids)} компаниях")
    
    # Разбиваем на батчи по 20 компаний
    batch_size = 20
    batches = [company_ids[i:i + batch_size] for i in range(0, len(company_ids), batch_size)]
    
    print(f"Разбито на {len(batches)} батчей по {batch_size} компаний")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    all_links = set()  # Используем set чтобы избежать дублей
    
    # Создаем директорию для результатов
    import os
    results_dir = os.path.join('..', '_sites', 'gabestore')
    os.makedirs(results_dir, exist_ok=True)
    
    results_file = os.path.join(results_dir, 'game_links.txt')
    
    # Открываем файл для записи ссылок
    with open(results_file, 'w', encoding='utf-8') as output_file:
        
        for batch_num, batch in enumerate(batches, 1):
            print(f"\nОбработка батча {batch_num}/{len(batches)} ({len(batch)} компаний)")
            
            # Формируем URL для батча
            base_url = "https://gabestore.ru/search/next?series=&ProductFilter%5BsortName%5D=views&ProductFilter%5BpriceRange%5D=&ProductFilter%5BpriceFrom%5D=&ProductFilter%5BpriceTo%5D=&ProductFilter%5Bavailable%5D=0&ProductFilter%5Bavailable%5D=1"
            developer_params = [f"ProductFilter%5Bdeveloper%5D%5B%5D={cid}" for cid in batch]
            batch_url_base = base_url + "&" + "&".join(developer_params)
            
            print(f"Длина базового URL: {len(batch_url_base)} символов")
            
            # Проходим по страницам для этого батча
            page = 1
            batch_links = 0
            
            while True:
                url = f"{batch_url_base}&page={page}"
                
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        html_content = data.get("html", "")
                        
                        if not html_content:
                            print(f"  Страница {page}: нет HTML контента, завершаем батч")
                            break
                        
                        soup = BeautifulSoup(html_content, 'html.parser')
                        games = soup.find_all('div', class_='shop-item')
                        
                        if not games:
                            print(f"  Страница {page}: нет игр в HTML, завершаем батч")
                            break
                        
                        page_links = 0
                        for game in games:
                            name_tag = game.find('a', class_='shop-item__name')
                            if name_tag and name_tag.get('href'):
                                link = name_tag['href']
                                if link not in all_links:
                                    all_links.add(link)
                                    output_file.write(link + '\n')
                                    page_links += 1
                        
                        batch_links += page_links
                        print(f"  Страница {page}: найдено {len(games)} игр, новых ссылок: {page_links}")
                        
                        page += 1
                        
                        # Задержка между страницами
                        time.sleep(random.uniform(0.5, 1.5))
                        
                    elif response.status_code == 520:
                        print(f"  Ошибка 520 на странице {page}, повторяем через 5 сек...")
                        time.sleep(5)
                        continue
                    else:
                        print(f"  Ошибка {response.status_code} на странице {page}")
                        break
                        
                except Exception as e:
                    print(f"  Ошибка запроса на странице {page}: {e}")
                    time.sleep(2)
                    continue
            
            print(f"  Батч завершен: собрано {batch_links} новых ссылок")
            print(f"  Всего уникальных ссылок: {len(all_links)}")
            
            # Задержка между батчами
            delay = random.uniform(2, 4)
            print(f"  Задержка {delay:.1f}с перед следующим батчем...")
            time.sleep(delay)
    
    print(f"\n✓ Сбор завершен!")
    print(f"Всего собрано уникальных ссылок: {len(all_links)}")
    print(f"Ссылки записаны в файл: {results_file}")

if __name__ == '__main__':
    collect_game_links()