import json
import os
import time
import requests
import re
import logging
from datetime import datetime
from kant_ru import handle_captcha_if_needed

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
}

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_category_count(category_url, category_name):
    """Получает количество товаров в категории"""
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        
        logger.info(f"Проверяем категорию: {category_name}")
        
        # Получаем страницу
        response = session.get(category_url, timeout=30, allow_redirects=True)
        
        # Обрабатываем CAPTCHA если нужно
        response = handle_captcha_if_needed(session, response, category_url)
        if not response:
            logger.error(f"Не удалось обработать CAPTCHA для категории {category_name}")
            return None
            
        # Ищем JSON данные из __NEXT_DATA__
        json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', response.text, re.DOTALL)
        
        if not json_match:
            logger.warning(f"JSON не найден для категории {category_name}")
            return None
            
        json_data = json.loads(json_match.group(1))
        
        # Извлекаем данные из JSON: page->data->content->pager
        page_props = json_data.get('props', {}).get('pageProps', {})
        initial_state = page_props.get('initialState', {})
        page_data = initial_state.get('page', {}).get('data', {})
        content = page_data.get('content', {})
        pager_data = content.get('pager', {})
        
        total_items = pager_data.get('total', 0)
        total_pages = pager_data.get('lastPage', 0)
        
        logger.info(f"Категория {category_name}: {total_items} товаров, {total_pages} страниц")
        
        return {
            'name': category_name,
            'url': category_url,
            'total_items': total_items,
            'total_pages': total_pages,
            'check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"Ошибка при проверке категории {category_name}: {e}")
        return None

def load_categories():
    """Загружает список категорий из файла"""
    categories_file = 'categories_list.json'
    
    if not os.path.exists(categories_file):
        logger.error(f"Файл {categories_file} не найден!")
        return []
    
    try:
        with open(categories_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Преобразуем в список URL с параметром пагинации
        categories = []
        for url in data:
            url_with_filter = url + '?filter:perPage=96'
            categories.append(url_with_filter)
        
        logger.info(f"Загружено {len(categories)} категорий из файла {categories_file}")
        return categories
        
    except Exception as e:
        logger.error(f"Ошибка чтения файла {categories_file}: {e}")
        return []

def main():
    """Основная функция"""
    # Загружаем категории из файла
    categories = load_categories()
    
    if not categories:
        logger.error("Не удалось загрузить категории. Завершение работы.")
        return
    
    results = []
    
    logger.info("Начинаем проверку категорий...")
    
    for category_url in categories:
        # Извлекаем название из URL для отображения
        category_name = category_url.split('/')[-2] if category_url.split('/')[-2] else category_url.split('/')[-3]
        
        result = get_category_count(category_url, category_name)
        if result:
            results.append(result)
        
        # Пауза между запросами
        time.sleep(2)
    
    # Сохраняем результаты в файл
    output_file = f"kant_categories_count_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в файл: {output_file}")
    
    # Выводим сводку
    print("\n" + "="*50)
    print("СВОДКА ПО КАТЕГОРИЯМ:")
    print("="*50)
    
    total_all = 0
    for result in results:
        print(f"{result['name']}: {result['total_items']} товаров")
        total_all += result['total_items']
    
    print("="*50)
    print(f"ВСЕГО ТОВАРОВ: {total_all}")
    print("="*50)

if __name__ == '__main__':
    main()