import json
import hashlib
import os
import random
import time
import requests
import re
import logging
import base64
from datetime import datetime
from urllib.parse import urljoin

IN_DATA = {
    'name': 'kant_ru',
    'folder': 'bags-backpacks',
    'host': 'https://www.kant.ru/',
    'target_url': 'https://www.kant.ru/catalog/bags-backpacks/?filter:perPage=96',
    'qty_items': 690,
}
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"), IN_DATA["folder"])
PATH_IMAGES = os.path.join(PATH_ROOT, 'images')
PATH_LOGS = os.path.join(PATH_ROOT, 'logs')
HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,ro;q=0.6'
}

# Настройка логирования
if not os.path.exists(PATH_ROOT):
    os.makedirs(PATH_ROOT)
if not os.path.exists(PATH_LOGS):
    os.makedirs(PATH_LOGS)

log_filename = os.path.join(PATH_LOGS, f'kant_ru_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()  # Дублируем в консоль
    ]
)
logger = logging.getLogger(__name__)

logger.info(f'Каталог: {IN_DATA["folder"]}')
print(f'Каталог: {IN_DATA["folder"]}')

def handle_captcha_if_needed(session, response, url):
    """Обрабатывает CAPTCHA если она есть на странице"""
    if response.status_code != 200:
        logger.error(f"Ошибка запроса: {response.status_code}")
        return None
        
    content = response.text
    
    # Проверяем есть ли CAPTCHA
    if 'captcha' in content.lower() or 'challenge' in content.lower() or 'iwaf' in content.lower():
        logger.warning("Обнаружена CAPTCHA/защита!")
        
        # Сохраняем HTML для анализа
        with open('captcha_page.html', 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info("Страница с CAPTCHA сохранена в captcha_page.html")
        
        # Ищем изображение CAPTCHA (ищем любое img с data:image в src)
        captcha_img_match = re.search(r'<img[^>]*src="(data:image/[^"]*)"', content, re.IGNORECASE)
        if captcha_img_match:
            captcha_img_src = captcha_img_match.group(1)
            logger.info(f"Найдено изображение CAPTCHA: {captcha_img_src[:100]}...")
            
            # Сохраняем изображение CAPTCHA
            try:
                if captcha_img_src.startswith('data:image/'):
                    # Base64 изображение
                    header, data = captcha_img_src.split(',', 1)
                    image_data = base64.b64decode(data)
                    with open('captcha_image.png', 'wb') as f:
                        f.write(image_data)
                    logger.info("Base64 изображение CAPTCHA сохранено в captcha_image.png")
                else:
                    # URL изображения
                    if captcha_img_src.startswith('/'):
                        captcha_img_src = urljoin(url, captcha_img_src)
                    img_response = session.get(captcha_img_src, timeout=30)
                    if img_response.status_code == 200:
                        with open('captcha_image.png', 'wb') as f:
                            f.write(img_response.content)
                        logger.info("Изображение CAPTCHA сохранено в captcha_image.png")
            except Exception as e:
                logger.error(f"Ошибка сохранения изображения CAPTCHA: {e}")
            
            # URL для отправки CAPTCHA всегда один и тот же
            action_url = 'https://www.kant.ru/iwaf/captcha'
            logger.info(f"URL для отправки CAPTCHA: {action_url}")
            
            # Ищем поле ввода CAPTCHA (name="captcha")
            captcha_input_match = re.search(r'<input[^>]*name="captcha"', content, re.IGNORECASE)
            
            if captcha_input_match:
                captcha_field_name = "captcha"  # Мы знаем что поле называется "captcha"
                logger.info(f"Найдено поле CAPTCHA: {captcha_field_name}")
                
                # Запрашиваем решение у пользователя
                print("\n" + "="*50)
                print("ТРЕБУЕТСЯ РЕШЕНИЕ CAPTCHA!")
                print("Откройте файл captcha_image.png")
                print("="*50)
                
                captcha_solution = input("Введите решение CAPTCHA (или 'skip' для пропуска): ").strip()
                
                if captcha_solution.lower() == 'skip':
                    logger.warning("CAPTCHA пропущена пользователем")
                    return None
                
                # Отправляем решение CAPTCHA
                captcha_data = {captcha_field_name: captcha_solution}
                
                # Ищем дополнительные скрытые поля
                hidden_fields = re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', content)
                for field_name, field_value in hidden_fields:
                    captcha_data[field_name] = field_value
                
                logger.info(f"Отправляем решение CAPTCHA: {captcha_data}")
                captcha_response = session.post(action_url, data=captcha_data, timeout=30, allow_redirects=True)
                
                logger.info(f"Ответ сервера CAPTCHA: {captcha_response.status_code}")
                if captcha_response.status_code in [200, 302, 301]:
                    logger.info("CAPTCHA отправлена, пробуем еще раз получить страницу...")
                    time.sleep(2)
                    new_response = session.get(url, timeout=30, allow_redirects=True)
                    
                    # Проверяем, не получили ли мы снова CAPTCHA
                    if 'captcha' in new_response.text.lower() or 'challenge' in new_response.text.lower() or 'iwaf' in new_response.text.lower():
                        logger.warning("НЕВЕРНАЯ CAPTCHA! Получена новая CAPTCHA.")
                        return handle_captcha_if_needed(session, new_response, url)  # Рекурсивно обрабатываем новую CAPTCHA
                    else:
                        logger.info("CAPTCHA прошла успешно!")
                        return new_response
                else:
                    logger.error(f"Ошибка отправки CAPTCHA: {captcha_response.status_code}")
                    return None
            else:
                logger.error("Не найдено поле ввода CAPTCHA")
                return None
        else:
            logger.error("Не найдено изображение CAPTCHA")
            return None
    
    return response

def get_items():
    # создаем каталог для этого сайта, если его нет
    if not os.path.exists(PATH_ROOT):
        os.makedirs(PATH_ROOT)
    path_results = os.path.join(PATH_ROOT, f'results_{IN_DATA["name"].replace(".", "_")}.json')

    # Создаем каталог для изображений если его нет
    if not os.path.exists(PATH_IMAGES):
        os.makedirs(PATH_IMAGES)

    # Соберем ссылки со всех страниц через requests
    items_list = get_links_with_requests()
    
    if not items_list:
        logger.warning('Not found links')
        return True
    logger.info(f'Найдено {len(items_list)} ссылок на товары. Собираем инфо по каждому товару...')

    time.sleep(random.randint(1, 5))
    # Соберем данные
    get_data_with_requests(items_list, path_results)
    return True

def load_existing_results(path_results):
    """Загружает существующие результаты и возвращает set URL товаров"""
    existing_urls = set()
    if os.path.exists(path_results):
        try:
            with open(path_results, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        item_data = json.loads(line)
                        url = item_data.get('url', '')
                        if url:
                            existing_urls.add(url)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Ошибка загрузки существующих результатов: {e}")
    return existing_urls

def download_images(images_urls, item_id, session, first_image_url=None):
    """Скачивает картинки товара с проверкой на существование"""
    downloaded_images = []
    
    if not images_urls:
        return downloaded_images
    
    # Убираем дубли
    images_urls = list(set(images_urls))
    
    # Если есть первая картинка из списка, скачиваем её первой
    if first_image_url and first_image_url in images_urls:
        images_urls.remove(first_image_url)
        images_urls.insert(0, first_image_url)
    elif first_image_url:
        # Если первая картинка не в списке деталей, добавляем её
        images_urls.insert(0, first_image_url)
    
    for k, image_url in enumerate(images_urls[:4], 1):  # Максимум 4 картинки
        try:
            # Определяем расширение
            if '.webp' in image_url.lower():
                ext = 'webp'
            elif '.jpg' in image_url.lower() or '.jpeg' in image_url.lower():
                ext = 'jpg'
            elif '.png' in image_url.lower():
                ext = 'png'
            else:
                ext = 'jpg'
            
            image_name = f'{item_id}_{k}.{ext}'
            image_path = os.path.join(PATH_IMAGES, image_name)
            
            # Проверяем существует ли файл
            if os.path.exists(image_path):
                downloaded_images.append(image_name)
                continue
            
            # Скачиваем картинку
            img_response = session.get(image_url, headers=HEADERS, timeout=30)
            if img_response.status_code == 200:
                with open(image_path, 'wb') as f:
                    f.write(img_response.content)
                downloaded_images.append(image_name)
            else:
                logger.error(f"Ошибка скачивания картинки {image_url}: {img_response.status_code}")
                
        except Exception as e:
            logger.error(f"Ошибка при скачивании картинки {image_url}: {e}")
            continue
    
    return downloaded_images

def save_item_to_file(item_data, path_results):
    """Сохраняет один товар в JSON файл (одна строка - один товар)"""
    with open(path_results, 'a', encoding='utf-8') as f:
        json.dump(item_data, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    

def get_data_with_requests(items, path_results) -> bool:
    """Собирает данные о товарах через requests"""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Загружаем существующие результаты
    existing_urls = load_existing_results(path_results)
    
    flag_try = 0
    row_count = 0
    total_items = len(items[:IN_DATA['qty_items']])
    processed_count = 0
    
    for item in items[:IN_DATA['qty_items']]:
        try:
            flag_try = 0
            processed_count += 1
            
            # Проверяем, не обрабатывали ли мы уже этот товар
            if item['link'] in existing_urls:
                logger.info(f"Товар {processed_count}/{total_items} уже обработан, пропускаем: {item['link']}")
                continue
            
            logger.info(f"Обрабатываем товар {processed_count}/{total_items}: {item['link']}")
            
            # получаем каждую страницу через requests
            response = session.get(item['link'], timeout=30, allow_redirects=True)
            
            # Обрабатываем CAPTCHA если нужно
            response = handle_captcha_if_needed(session, response, item['link'])
            if not response:
                logger.error("Не удалось обработать CAPTCHA для товара")
                continue
            
            # Извлекаем JSON данные из __NEXT_DATA__
            try:
                flag_try = 1
                json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', response.text, re.DOTALL)
                if not json_match:
                    logger.warning("JSON не найден на странице товара")
                    continue
                    
                json_data = json.loads(json_match.group(1))
                
                # Извлекаем данные из JSON согласно структуре: props.pageProps.initialState.page.data.content.product
                page_props = json_data.get('props', {}).get('pageProps', {})
                initial_state = page_props.get('initialState', {})
                page_data = initial_state.get('page', {}).get('data', {})
                content = page_data.get('content', {})
                product_data = content.get('product', {})
                
                
                # Название товара
                item_title = product_data.get('name', '')
                if not item_title:
                    logger.warning("Название товара не найдено в JSON")
                    continue
                item_title = item_title.replace('{', "").replace('}', "")
                
                # Цвет товара
                item_color = product_data.get('color', '')
                
                # Цена из prices.base или prices.old если base = 0
                item_price = 0
                prices_data = product_data.get('prices', {})
                if isinstance(prices_data, dict):
                    base_price = prices_data.get('base', 0)
                    old_price = prices_data.get('old', 0)
                    item_price = base_price if base_price > 0 else old_price
                
                # Бренд
                brand_data = product_data.get('brand', {})
                if isinstance(brand_data, dict):
                    item_brand = brand_data.get('name', '') or brand_data.get('title', '') or "KANT"
                else:
                    item_brand = str(brand_data) if brand_data else "KANT"
                
                # Характеристики из attributes.key и attributes.all.attributes
                item_params = {}
                attributes_data = product_data.get('attributes', {})
                if isinstance(attributes_data, dict):
                    # Основные атрибуты из ключа 'key'
                    key_attributes = attributes_data.get('key', [])
                    if key_attributes:
                        for attr in key_attributes:
                            if isinstance(attr, dict):
                                name = attr.get('name', '')
                                values = attr.get('values', [])
                                
                                # Собираем значения
                                if name and values:
                                    # Объединяем все значения через запятую
                                    value_list = []
                                    for val in values:
                                        if isinstance(val, dict):
                                            value_list.append(val.get('value', ''))
                                        elif isinstance(val, str):
                                            value_list.append(val)
                                    
                                    if value_list:
                                        item_params[name] = ', '.join(value_list)
                    
                    # Дополнительные атрибуты из attributes.all (массив групп)
                    all_attributes = attributes_data.get('all', [])
                    if isinstance(all_attributes, list):
                        for group in all_attributes:
                            if isinstance(group, dict):
                                group_attrs = group.get('attributes', [])
                                if group_attrs:
                                    for attr in group_attrs:
                                        if isinstance(attr, dict):
                                            name = attr.get('name', '')
                                            values = attr.get('values', [])
                                            
                                            # Собираем значения
                                            if name and values:
                                                # Объединяем все значения через запятую
                                                value_list = []
                                                for val in values:
                                                    if isinstance(val, dict):
                                                        value_list.append(val.get('value', ''))
                                                    elif isinstance(val, str):
                                                        value_list.append(val)
                                                
                                                if value_list:
                                                    item_params[name] = ', '.join(value_list)
                        
                    if not item_params:
                        logger.warning("Атрибуты не найдены в JSON")
                else:
                    logger.warning("Блок 'attributes' не найден в JSON")
                
                # Описание
                item_desc = product_data.get('description', '')
                if item_desc:
                    item_desc = item_desc.replace('"', "'").replace('{', "").replace('}', "")
                    # Удаляем HTML ссылки
                    item_desc = re.sub(r'<a[^>]*href[^>]*>(.*?)</a>', r'\1', item_desc, flags=re.IGNORECASE | re.DOTALL)
                
                # Хлебные крошки из page->data->breadcrumbs
                crumbs = []
                breadcrumbs = page_data.get('breadcrumbs', [])
                if breadcrumbs:
                    for crumb in breadcrumbs:
                        if isinstance(crumb, dict) and crumb.get('type') == 'breadcrumb':
                            crumb_name = crumb.get('name', '')
                            if crumb_name and crumb_name != 'Главная':
                                crumbs.append(crumb_name)
                
                # Изображения - собираем URL
                images_urls = []
                images_data = product_data.get('images', [])
                if images_data:
                    for img in images_data:
                        if isinstance(img, dict):
                            # Используем original для полного размера
                            url = img.get('original', '') or img.get('full', '') or img.get('preview', '')
                            if url:
                                # Добавляем домен если нужно
                                if url.startswith('/'):
                                    url = 'https://www.kant.ru' + url
                                images_urls.append(url)
                
                # Размеры из product->offers
                item_sizes = []
                offers_data = product_data.get('offers', [])
                if offers_data:
                    for offer in offers_data:
                        if isinstance(offer, dict):
                            sizes_obj = offer.get('sizes', {})
                            if isinstance(sizes_obj, dict):
                                us_size = sizes_obj.get('us', '')
                                if us_size:
                                    item_sizes.append(us_size)
                
                item_id = hashlib.sha256(f"{item_title}{item_brand}{item_price}{item['link']}".encode("utf-8")).hexdigest()
                
                # Скачиваем картинки
                downloaded_images = download_images(images_urls, item_id, session, item.get('first_image'))
                
            except Exception as ex:
                logger.error(f"Ошибка при парсинге JSON данных: {ex}")
                logger.error(f"Пропускаем товар: {item['link']}")
                continue

            # Создаем объект товара
            item_data = {
                'id': item_id,
                'crumbs': crumbs,
                'title': item_title,
                'color': item_color,
                'brand': item_brand,
                'price': item_price,
                'sizes': item_sizes,
                'params': item_params,
                'description': item_desc,
                'images': downloaded_images,
                'url': item['link']
            }
            
            # Сохраняем товар сразу в файл
            save_item_to_file(item_data, path_results)
            row_count += 1

        except Exception as ex:
            logger.error(f'Error {flag_try} при обработке {item["link"]}')
            logger.error(f'Ошибка: {ex}')
            time.sleep(random.randint(1, 5))
            continue
        time.sleep(random.randint(1, 3))
    
    logger.info(f'Собрано информации по {row_count} товаров.')
    return True

def get_links_with_requests() -> list:
    """Получает ссылки на товары через requests"""
    items = []
    page_n = 1
    total_items = None
    
    # Создаем сессию
    session = requests.Session()
    session.headers.update(HEADERS)
    
    while True:
        if len(items) >= IN_DATA['qty_items']:
            break
        
        # Формируем URL с номером страницы
        if page_n > 1:
            current_url = f"{IN_DATA['target_url']}&page={page_n}"
        else:
            current_url = IN_DATA['target_url']
        
        logger.info(f"Обрабатываем страницу {page_n}: {current_url}")
        
        try:
            # Получаем страницу
            response = session.get(current_url, timeout=30, allow_redirects=True)
            
            # Обрабатываем CAPTCHA если нужно
            response = handle_captcha_if_needed(session, response, current_url)
            if not response:
                logger.error("Не удалось обработать CAPTCHA")
                break
            
            # Ищем JSON данные из __NEXT_DATA__
            json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', response.text, re.DOTALL)
            
            if json_match:
                logger.info("Найден __NEXT_DATA__ JSON!")
                try:
                    json_data = json.loads(json_match.group(1))
                    
                    # Извлекаем данные из JSON: page->data->content->items,pager
                    page_props = json_data.get('props', {}).get('pageProps', {})
                    initial_state = page_props.get('initialState', {})
                    page_data = initial_state.get('page', {}).get('data', {})
                    content = page_data.get('content', {})
                    
                    page_items = content.get('items', [])
                    pager_data = content.get('pager', {})
                    
                    logger.info(f"Найдено товаров в JSON на странице {page_n}: {len(page_items)}")
                    
                    if page_n == 1 and pager_data:
                        total_items = pager_data.get('total', 0)
                        total_pages = pager_data.get('lastPage', 0)
                        logger.info(f"Общее количество товаров: {total_items}, страниц: {total_pages}")
                    
                    if len(page_items) == 0:
                        logger.warning("Товары не найдены в JSON")
                        break
                    
                    # Собираем ссылки из JSON
                    for item in page_items:
                        item_url = item.get('url', '')
                        if item_url:
                            # Добавляем домен если нужно
                            if item_url.startswith('/'):
                                item_url = 'https://www.kant.ru' + item_url
                            
                            # Получаем первую картинку из списка
                            first_image_url = None
                            image_data = item.get('image', {})
                            if isinstance(image_data, dict):
                                first_image_url = image_data.get('full', '')
                                if first_image_url and first_image_url.startswith('/'):
                                    first_image_url = 'https://www.kant.ru' + first_image_url
                            
                            items.append({
                                'link': item_url,
                                'first_image': first_image_url
                            })
                    
                    # Проверяем пагинацию из JSON
                    current_page = pager_data.get('page', page_n)
                    total_pages = pager_data.get('lastPage', 0)
                    
                    # Если lastPage = 0, вычисляем количество страниц по общему количеству товаров
                    if total_pages == 0 and total_items > 0:
                        total_pages = (total_items + 95) // 96  # Округляем вверх для 96 товаров на странице
                    
                    if current_page >= total_pages:
                        logger.info(f"Достигнута последняя страница: {current_page}/{total_pages}")
                        break
                    else:
                        page_n += 1
                        
                except json.JSONDecodeError as ex:
                    logger.error(f"Ошибка парсинга JSON: {ex}")
                    break
            else:
                logger.error("JSON не найден в HTML")
                break
                
        except Exception as ex:
            logger.error(f"Ошибка при сборе ссылок на странице {page_n}: {ex}")
            break
            
    return items


if __name__ == '__main__':
    get_items()
    logger.info(f'Каталог: {IN_DATA["folder"]}')