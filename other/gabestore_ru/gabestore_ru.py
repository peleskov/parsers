import json
import csv
import hashlib
import os
import random
import time
import requests
import re
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from webdriver_manager.firefox import GeckoDriverManager
from transliterate import translit

IN_DATA = {
    'name': 'gabestore',
    'folder': 'games',
    'host': 'https://gabestore.ru/',
    'target_url': 'https://gabestore.ru/search/next?series=&ProductFilter%5BsortName%5D=views&ProductFilter%5BpriceTo%5D=0&ProductFilter%5Bavailable%5D=0&ProductFilter%5Bavailable%5D=1',
    'qty_items': 10000,
}
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"), IN_DATA["folder"])
PATH_DRIVER = os.path.join('../clothes/chromedriver.exe')
PATH_IMAGES = os.path.join(PATH_ROOT, 'images')
HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/98.0.4758.102 Safari/537.36',
    'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,ro;q=0.6'
}


def get_items():
    # Используем webdriver-manager для автоматического управления драйвером Firefox
    service = Service(GeckoDriverManager().install())

    options = Options()
    options.add_argument('--headless')  # Скроем окно браузера
    # options.set_preference('javascript.enabled', False)  # Отключаем JavaScript если нужно

    with webdriver.Firefox(service=service, options=options) as driver:
        # driver.maximize_window()

        try:
            # Проверим доступен ли сайт
            driver.get(IN_DATA['host'])
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CLASS_NAME, 'b-promo'))
            print('Сайт доступен продолжаем...')
        except Exception as ex:
            print('Сайт не доступен останавливаемся!')
            print(ex)
            return
        # создаем каталог для этого сайта, если его нет
        if not os.path.exists(PATH_ROOT):
            os.makedirs(PATH_ROOT)
        path_results = os.path.join(PATH_ROOT, f'results_{IN_DATA["name"].replace(".", "_")}.jsonl')
        # Создаем JSONL файл для записи данных (JSON Lines - каждая строка отдельный JSON объект)
        print(f'Результаты будут записаны в: {path_results}')

        # Создаем каталог для изображений если его нет
        if not os.path.exists(PATH_IMAGES):
            os.makedirs(PATH_IMAGES)

        # Читаем ссылки из файла и фильтруем уже обработанные
        all_links = read_links_from_file()
        if not all_links:
            print('Не найдено ссылок в файле')
            return True
        
        # Получаем список уже обработанных ссылок
        processed_links = get_processed_links(path_results)
        print(f'Уже обработано товаров: {len(processed_links)}')
        
        # Фильтруем только новые ссылки
        items_list = [item for item in all_links if item['link'] not in processed_links]
        print(f'Загружено {len(all_links)} ссылок из файла, новых для обработки: {len(items_list)}')

        time.sleep(random.randint(1, 5))

        # Соберем данные
        get_data(driver, items_list, path_results)
    return True


def check_page_availability(driver, url, max_retries=3) -> bool:
    """Проверяет доступность страницы с повторными попытками"""
    retry_delays = [5*60, 10*60, 30*60]  # 5, 10, 30 минут в секундах
    
    for attempt in range(max_retries):
        try:
            driver.get(url)
            # Проверяем статус через JavaScript
            status_code = driver.execute_script("return document.readyState === 'complete' ? 200 : 0")
            
            # Проверяем наличие ожидаемого контента (заголовок h1)
            try:
                WebDriverWait(driver, 10).until(lambda d: d.find_element(By.TAG_NAME, 'h1'))
                print(f"Страница доступна: {url}")
                return True
            except:
                print(f"Ожидаемый контент не найден на странице: {url}")
                
        except Exception as ex:
            print(f"Ошибка при загрузке страницы (попытка {attempt + 1}): {ex}")
        
        if attempt < max_retries - 1:
            delay_minutes = retry_delays[attempt] // 60
            print(f"Ожидание {delay_minutes} минут перед следующей попыткой...")
            time.sleep(retry_delays[attempt])
    
    print(f"Страница недоступна после {max_retries} попыток: {url}")
    return False


def get_data(driver, items, path_results) -> bool:
    for item in items[:IN_DATA['qty_items']]:
        try:
            # Проверяем доступность страницы с повторными попытками
            url = f'{IN_DATA["host"][:-1]}{item["link"]}'
            if not check_page_availability(driver, url):
                print(f"Пропускаем товар из-за недоступности страницы: {item['link']}")
                continue
            
            # получаем каждую старницу и собираем данные
            item_title = driver.find_element(By.TAG_NAME, 'h1').text.replace('купить ', '').replace('КУПИТЬ ', '')
            
            # Цена всегда должна быть
            item_price = driver.find_element(By.CLASS_NAME, 'b-card__price-currentprice').text
            item_price = re.sub(r"[^\d.]", "", item_price)
            
            # Старая цена может отсутствовать (если нет скидки)
            item_old_price = ''
            try:
                item_old_price = driver.find_element(By.CLASS_NAME, 'b-card__price-oldprice').text
                item_old_price = re.sub(r"[^\d.]", "", item_old_price)
            except:
                pass
            item_params = {}
            try:
                prms = driver.find_elements(By.XPATH, '//div[@class="b-card__table"]//div[@class="b-card__table-item"]')
                for p in prms:
                    title = p.find_element(By.CLASS_NAME, 'b-card__table-title').text.lower()
                    title = translit(title, 'ru', reversed=True).replace(' ', '_')
                    value = p.find_element(By.CLASS_NAME, 'b-card__table-value').text
                    item_params[title] = value
            except Exception as ex:
                pass
            try:
                prms = driver.find_elements(By.CLASS_NAME, 'b-card__subinfo-item')
                for p in prms:
                    title = p.find_element(By.CLASS_NAME, 'b-card__subinfo-head').text.lower()
                    title = translit(title, 'ru', reversed=True).replace(' ', '_')
                    value = p.find_element(By.CLASS_NAME, 'b-card__subinfo-body').text
                    item_params[title] = value
            except Exception as ex:
                pass
            try:
                prms = driver.find_elements(By.CLASS_NAME, 'b-card__extendinfo-icon')
                item_params['extend'] = [p.get_attribute('data-title') for p in prms]
            except Exception as ex:
                pass
            item_params = json.dumps(item_params, ensure_ascii=False)
            item_desc = ''
            try:
                item_desc = driver.find_element(By.CLASS_NAME, 'b-card__tabdescription').get_attribute('innerHTML').replace('\r', '').replace('\n', '')
                item_desc = re.sub(r'<a.+?>(.+?)</a>', r'\1', item_desc)
            except Exception as ex:
                pass
            item_require = ''
            try:
                item_require = driver.find_element(By.CLASS_NAME, 'game-describe__tab').get_attribute('innerHTML').replace('\r', '').replace('\n', '')
                item_require = re.sub(r'<a.+?>(.+?)</a>', r'\1', item_require)
            except Exception as ex:
                pass

            item_id = hashlib.sha256(f"{item_title}{item_price}{item_old_price}{item['link']}".encode("utf-8")).hexdigest()
            item_image = ''
            try:
                item_image_url = driver.find_element(By.CLASS_NAME, 'js-img-bgcolro').get_attribute('src')
                item_image_ext = os.path.splitext(os.path.basename(item_image_url))[1].split('?')[0][1:]
                item_image_name = f'{item_id}.{item_image_ext}'
                item_image_path = os.path.join(PATH_IMAGES, item_image_name)
                # проверяем нет ли еще этой картинки, что бы при повторном запуске не качать снова
                if not os.path.isfile(item_image_path):
                    try:
                        image = requests.get(item_image_url, headers=HEADERS)
                        with open(item_image_path, 'wb') as f:
                            f.write(image.content)
                        item_image = item_image_name
                    except Exception as ex:
                        pass
                else:
                    item_image = item_image_name
            except Exception as ex:
                pass
            item_screenshots = ''
            try:
                screenshots = driver.find_elements(By.XPATH, '//div[@class="b-card__slider-image"]//img')
                screenshots_urls = [i.get_attribute('src') for i in screenshots]
                if len(screenshots_urls) > 0:
                    k = 0
                    item_screenshots_arr = []
                    screenshots_urls = set(screenshots_urls)
                    for item_image_url in screenshots_urls:
                        if k > 3:
                            break
                        k += 1
                        item_image_ext = os.path.splitext(os.path.basename(item_image_url))[1].split('?')[0][1:]
                        item_image_name = f'{item_id}_{k}.{item_image_ext}'
                        item_image_path = os.path.join(PATH_IMAGES, item_image_name)
                        # проверяем нет ли еще этой картинки, что бы при повторном запуске не качать снова
                        if not os.path.isfile(item_image_path):
                            try:
                                image = requests.get(item_image_url, headers=HEADERS)
                                with open(item_image_path, 'wb') as f:
                                    f.write(image.content)
                                    item_screenshots_arr.append(item_image_name)
                            except Exception as ex:
                                pass
                        else:
                            item_screenshots_arr.append(item_image_name)
                    item_screenshots = json.dumps(item_screenshots_arr, ensure_ascii=False)
            except Exception as ex:
                pass

            item_videos = []
            try:
                videos = driver.find_elements(By.XPATH, '//div[contains(@class,"b-card__slider-image b-card__slider-image--videopreview")]/a')
                for video in videos:
                    item_videos.append({
                        'video': video.get_attribute('href'),
                        'preview': video.find_element(By.TAG_NAME, 'img').get_attribute('src')
                    })

            except Exception as ex:
                pass
            # Создаем JSON объект с данными товара
            item_data = {
                'id': item_id,
                'title': item_title,
                'price': item_price,
                'old_price': item_old_price,
                'params': json.loads(item_params) if item_params else {},
                'desc': item_desc,
                'require': item_require,
                'image': item_image,
                'screenshots': json.loads(item_screenshots) if item_screenshots else [],
                'videos': item_videos,
                'link': item['link'],
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Записываем JSON объект в файл (одна строка = один товар)
            with open(path_results, 'a', encoding='UTF8') as f:
                f.write(json.dumps(item_data, ensure_ascii=False) + '\n')

        except Exception as ex:
            print(ex)
            time.sleep(random.randint(1, 5))
            continue
        time.sleep(random.randint(1, 3))
    return True


def get_processed_links(results_file) -> set:
    """Читает уже обработанные ссылки из JSONL файла"""
    if not os.path.exists(results_file):
        return set()
    
    processed = set()
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        if 'link' in data:
                            processed.add(data['link'])
                    except json.JSONDecodeError:
                        continue
        
        print(f'Найдено уже обработанных товаров в файле: {len(processed)}')
        return processed
        
    except Exception as e:
        print(f'Ошибка чтения файла результатов: {e}')
        return set()


def read_links_from_file() -> list:
    """Читает ссылки из файла game_links.txt"""
    links_file = os.path.join('..', '_sites', 'gabestore', 'game_links.txt')
    
    if not os.path.exists(links_file):
        print(f'Файл со ссылками не найден: {links_file}')
        return []
    
    items = []
    try:
        with open(links_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                link = line.strip()
                if link:
                    # Ссылки в файле относительные, добавляем полный путь
                    if not link.startswith('http'):
                        if not link.startswith('/'):
                            link = '/' + link
                    
                    items.append({'link': link})
                    
                    # Ограничиваем количество согласно настройкам
                    if len(items) >= IN_DATA['qty_items']:
                        break
        
        print(f'Прочитано ссылок из файла: {len(items)}')
        return items
        
    except Exception as e:
        print(f'Ошибка чтения файла со ссылками: {e}')
        return []




if __name__ == '__main__':
    get_items()
