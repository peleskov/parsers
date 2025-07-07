import json
import os
import random
import time
import requests
import re
import logging
from datetime import datetime
from kant_ru import handle_captcha_if_needed, HEADERS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Путь к файлу с результатами
RESULTS_FILE = '../_sites/kant_ru/outdoor/results_kant_ru.json'

def get_crumbs_from_url(session, url, max_retries=3):
    """Получает хлебные крошки с URL товара с повторными попытками"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Попытка {attempt + 1}/{max_retries} для {url}")
            response = session.get(url, timeout=30, allow_redirects=True)
            
            # Обрабатываем CAPTCHA если нужно
            response = handle_captcha_if_needed(session, response, url)
            if not response:
                logger.error(f"Не удалось обработать CAPTCHA для {url}")
                return []
            
            # Извлекаем JSON данные из __NEXT_DATA__
            json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', response.text, re.DOTALL)
            if not json_match:
                logger.warning(f"JSON не найден на странице {url}")
                return []
                
            json_data = json.loads(json_match.group(1))
            
            # Извлекаем данные из JSON
            page_props = json_data.get('props', {}).get('pageProps', {})
            initial_state = page_props.get('initialState', {})
            page_data = initial_state.get('page', {}).get('data', {})
            
            # Хлебные крошки из page->data->breadcrumbs
            crumbs = []
            breadcrumbs = page_data.get('breadcrumbs', [])
            if breadcrumbs:
                for crumb in breadcrumbs:
                    if isinstance(crumb, dict) and crumb.get('type') == 'breadcrumb':
                        crumb_name = crumb.get('name', '')
                        if crumb_name and crumb_name != 'Главная':
                            crumbs.append(crumb_name)
            
            return crumbs
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError) as ex:
            logger.warning(f"Ошибка соединения на попытке {attempt + 1}/{max_retries} для {url}: {ex}")
            if attempt < max_retries - 1:
                delay = (attempt + 1) * 2  # Увеличиваем задержку с каждой попыткой
                logger.info(f"Ожидание {delay} секунд перед следующей попыткой...")
                time.sleep(delay)
            else:
                logger.error(f"Все попытки исчерпаны для {url}")
                return []
        except Exception as ex:
            logger.error(f"Ошибка при получении крошек с {url}: {ex}")
            return []

def update_crumbs():
    """Обновляет хлебные крошки в файле результатов"""
    input_file = RESULTS_FILE
    tmp_file = RESULTS_FILE.replace('.json', '_tmp.json')
    output_file = RESULTS_FILE
    
    if not os.path.exists(input_file):
        logger.error(f"Файл {input_file} не найден")
        return
    
    # Переименовываем исходный файл в tmp
    os.rename(input_file, tmp_file)
    logger.info(f"Переименован {input_file} в {tmp_file}")
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    processed_count = 0
    updated_count = 0
    remaining_lines = []
    
    # Читаем все строки из tmp файла
    with open(tmp_file, 'r', encoding='utf-8') as f:
        remaining_lines = [line.strip() for line in f if line.strip()]
    
    total_lines = len(remaining_lines)
    logger.info(f"Всего строк для обработки: {total_lines}")
    
    # Обрабатываем каждую строку
    while remaining_lines:
        line = remaining_lines.pop(0)  # Удаляем первую строку из списка
        
        try:
            item_data = json.loads(line)
            processed_count += 1
            
            # Проверяем есть ли уже крошки
            if item_data.get('crumbs') and len(item_data['crumbs']) > 0:
                logger.info(f"Товар {processed_count} уже имеет крошки, пропускаем")
                # Сохраняем в выходной файл
                with open(output_file, 'a', encoding='utf-8') as f_out:
                    json.dump(item_data, f_out, ensure_ascii=False, separators=(',', ':'))
                    f_out.write('\n')
                continue
            
            url = item_data.get('url', '')
            if not url:
                logger.warning(f"Товар {processed_count} не имеет URL")
                # Сохраняем в выходной файл как есть
                with open(output_file, 'a', encoding='utf-8') as f_out:
                    json.dump(item_data, f_out, ensure_ascii=False, separators=(',', ':'))
                    f_out.write('\n')
                continue
            
            logger.info(f"Обрабатываем товар {processed_count}/{total_lines}: {url}")
            
            # Получаем крошки
            crumbs = get_crumbs_from_url(session, url)
            
            if crumbs:
                item_data['crumbs'] = crumbs
                updated_count += 1
                logger.info(f"Обновлены крошки для товара {processed_count}: {crumbs}")
            else:
                logger.warning(f"Крошки не найдены для товара {processed_count}")
            
            # Записываем обновленные данные в выходной файл
            with open(output_file, 'a', encoding='utf-8') as f_out:
                json.dump(item_data, f_out, ensure_ascii=False, separators=(',', ':'))
                f_out.write('\n')
            
            # Обновляем tmp файл - перезаписываем оставшиеся строки
            with open(tmp_file, 'w', encoding='utf-8') as f_tmp:
                for remaining_line in remaining_lines:
                    f_tmp.write(remaining_line + '\n')
            
            logger.info(f"Осталось строк: {len(remaining_lines)}")
            
            # Задержка между запросами
            time.sleep(random.randint(2, 5))
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в строке {processed_count}: {e}")
            continue
        except Exception as e:
            logger.error(f"Ошибка обработки товара {processed_count}: {e}")
            continue
    
    # Удаляем tmp файл если он пустой
    if os.path.exists(tmp_file):
        try:
            with open(tmp_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                os.remove(tmp_file)
                logger.info(f"Удален пустой tmp файл: {tmp_file}")
            else:
                logger.info(f"Tmp файл не пуст, оставляем: {tmp_file}")
        except:
            logger.info(f"Оставляем tmp файл: {tmp_file}")
    
    logger.info(f"Обработано товаров: {processed_count}")
    logger.info(f"Обновлено товаров: {updated_count}")
    logger.info(f"Результат сохранен в {output_file}")

if __name__ == '__main__':
    update_crumbs()