#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import random

def check_companies():
    # Читаем отфильтрованный файл компаний
    with open('companies.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    companies_with_games = []
    total_companies = 0
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if line and ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                company_id = parts[0].strip()
                company_name = parts[1].strip()
                total_companies += 1
                
                print(f"[{line_num}/{len(lines)}] Проверяем: {company_name} (ID: {company_id})")
                
                try:
                    # Формируем URL для API запроса
                    url = f"https://gabestore.ru/search/filter?ProductFilter%5Bdeveloper%5D%5B%5D={company_id}"
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            
                            # Ищем количество игр в JSON ответе
                            game_count = 0
                            
                            # Проверяем разные возможные структуры JSON
                            if isinstance(data, dict):
                                # Может быть в data.count, data.total, data.games, etc.
                                if 'count' in data:
                                    game_count = int(data['count'])
                                elif 'total' in data:
                                    game_count = int(data['total'])
                                elif 'games' in data and isinstance(data['games'], list):
                                    game_count = len(data['games'])
                                elif 'items' in data and isinstance(data['items'], list):
                                    game_count = len(data['items'])
                                elif 'products' in data and isinstance(data['products'], list):
                                    game_count = len(data['products'])
                            
                            if game_count > 0:
                                companies_with_games.append((company_id, company_name, game_count))
                                print(f"  ✓ Найдено игр: {game_count}")
                            else:
                                print(f"  - Игр не найдено")
                                
                        except json.JSONDecodeError:
                            print(f"  ! Ошибка парсинга JSON")
                    
                    else:
                        print(f"  ! HTTP ошибка: {response.status_code}")
                        
                except requests.RequestException as e:
                    print(f"  ! Ошибка запроса: {e}")
                
                # Задержка между запросами  
                time.sleep(random.uniform(0.5, 1.5))
    
    # Сохраняем результаты
    with open('companies_with_games.txt', 'w', encoding='utf-8') as f:
        for company_id, company_name, game_count in companies_with_games:
            f.write(f"{company_id}: {company_name} ({game_count} игр)\n")
    
    print(f"\nГотово!")
    print(f"Всего проверено компаний: {total_companies}")
    print(f"Компаний с играми: {len(companies_with_games)}")
    print(f"Результаты сохранены в companies_with_games.txt")
    
    if companies_with_games:
        print(f"\nТоп-10 компаний по количеству игр:")
        sorted_companies = sorted(companies_with_games, key=lambda x: x[2], reverse=True)
        for i, (company_id, company_name, game_count) in enumerate(sorted_companies[:10], 1):
            print(f"  {i}. {company_name}: {game_count} игр (ID: {company_id})")

if __name__ == '__main__':
    check_companies()