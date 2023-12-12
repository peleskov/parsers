import json

import winsound
import csv
import hashlib
import os
import random
import time
import requests
import re
from lxml import html
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common import exceptions

IN_DATA = {
    'name': '21_shop_ru',
    'folder': 'catalog',
    'host': 'https://21-shop.ru/',
    'target_url': 'https://21-shop.ru/catalog/',
    'qty_items': 5000,
}
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"), IN_DATA["folder"])
PATH_DRIVER = os.path.join('chromedriver.exe')
PATH_IMAGES = os.path.join(PATH_ROOT, 'images')
HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,ro;q=0.6'
}


def get_items():
    # Запускаем сервис Chrome
    service = ChromeService(executable_path=PATH_DRIVER)

    options = Options()
    options.add_argument('headless') # Скроем окно браузера
    options.add_experimental_option( "prefs",{'profile.managed_default_content_settings.javascript': 2}) # Отключаем JavsScript
    with webdriver.Chrome(service=service, options=options) as driver:
        # driver.maximize_window()

        try:
            # Проверим доступен ли сайт
            driver.get(IN_DATA['host'])
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CLASS_NAME, 'main'))
            print('Сайт доступен продолжаем...')
        except Exception as ex:
            print('Сайт не доступен останавливаемся!')
            print(ex)
            return
        # создаем каталог для этого сайта, если его нет
        if not os.path.exists(PATH_ROOT):
            os.makedirs(PATH_ROOT)
        path_results = os.path.join(PATH_ROOT, f'results_{IN_DATA["name"].replace(".", "_")}.csv')
        # Создаем csv файл для загрузки данных в базу, и пишем в него первую строку с обозначением колонок
        with open(path_results, 'w', newline="", encoding='UTF8') as f:
            f.write('id;Crumbs;Title;Brand;Price;Sizes;Params;Description;Images;\n')

        # Создаем каталог для изображений если его нет
        if not os.path.exists(PATH_IMAGES):
            os.makedirs(PATH_IMAGES)

        # Соберем ссылки со всех страниц, ограничение по количеству IN_DATA['qty_items']
        items_list = get_links(driver)
        if not items_list:
            print('Not found links')
            return True
        print(f'Найдено {len(items_list)} ссылок на товары. Собираем инфо по каждому товару...')
        time.sleep(random.randint(1, 5))

        # Соберем данные
        get_data(driver, items_list, path_results)
    return True


def get_data(driver, items, path_results) -> bool:
    exp = ''
    for item in items[:IN_DATA['qty_items']]:
        try:
            # получаем каждую старницу и собираем данные
            driver.get(item['link'])
            WebDriverWait(driver, 20).until(lambda d: d.find_element(By.TAG_NAME, 'h1'))
            item_title = item['title']
            item_brand = item['brand']
            item_price = item['price']
            item_crumbs = item['crumbs'].replace('/', '||')
            item_desc = ''
            try:
                item_desc = driver.find_element(By.XPATH, '//div[@itemprop="description"]')
                item_desc = re.sub(r'<a.+?>(.+?)</a>', r'\1', item_desc.get_attribute('innerHTML')).replace('\r', '').replace('\n', '')
            except Exception as ex:
                pass
            sizes = driver.find_elements(By.XPATH, '//div[@data-code="RAZMER"]//div[not(contains(@class, "disabled"))]')
            item_sizes = '||'.join([s.get_attribute('data-text') for s in sizes])
            item_id = hashlib.sha256(f"{item_title}{item_brand}{item_price}{item['link']}".encode("utf-8")).hexdigest()
            item_params = ''
            try:
                params = driver.find_element(By.CLASS_NAME, 'col-features')
                item_params = re.sub(r'<a.+?>(.+?)</a>', r'\1', params.get_attribute('innerHTML')).replace('\r', '').replace('\n', '')
            except Exception as ex:
                pass

            images = driver.find_elements(By.XPATH, '//div[contains(@class,"img_block_big") and @style="display: block;"]//figure/a')
            k = 0
            images_urls = [i.get_attribute('href') for i in images]
            if len(images_urls) > 0:
                k = 0
                item_images_arr = []
                images_urls = set(images_urls)
                for item_image_url in images_urls:
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
                                item_images_arr.append(item_image_name)
                        except Exception as ex:
                            pass
                    else:
                        item_images_arr.append(item_image_name)
                item_images = '||'.join(item_images_arr)

            # пишем строку с товаром в csv файл
            with open(path_results, 'a', newline="", encoding='UTF8') as f:
                writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                writer.writerow([
                    item_id,
                    item_crumbs,
                    item_title,
                    item_brand,
                    item_price,
                    item_sizes,
                    item_params,
                    item_desc,
                    item_images,
                ])

        except Exception as ex:
            print(exp, ex)
            time.sleep(random.randint(1, 5))
            continue
        time.sleep(random.randint(1, 3))
    return True


def get_links(driver) -> list:
    items = []
    page_n = 1
    driver.get(IN_DATA['target_url'])

    while True:
        try:
            elements = driver.find_elements(By.CLASS_NAME, 'offer_item')
            for element in elements:
                items.append(
                    {
                        'link': element.find_element(By.CLASS_NAME, 'name').find_element(By.TAG_NAME, 'a').get_attribute('href'),
                        'title': element.get_attribute('data-name'),
                        'price': element.get_attribute('data-price'),
                        'brand': element.get_attribute('data-brand'),
                        'crumbs': element.get_attribute('data-nav-sections'),
                    }

                )
            driver.find_element(By.CLASS_NAME, 'modern-page-next')
            page_n += 1
            driver.get(f"{IN_DATA['target_url']}?PAGEN_1={page_n}")
        except Exception as ex:
            break
        if len(elements) >= IN_DATA['qty_items'] or len(items) >= IN_DATA['qty_items']:
            break
    return items


if __name__ == '__main__':
    get_items()
    winsound.Beep(500, 1000)
