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
    'name': 'megacvet24_ru',
    'folder': 'folgirovannye-shary',
    'host': 'https://megacvet24.ru/',
    'target_url': 'https://megacvet24.ru/folgirovannye-shary/',
    'qty_items': 10000,
}
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"), IN_DATA["folder"])
PATH_DRIVER = os.path.join('../clothes/chromedriver.exe')
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
    # options.add_argument('headless') # Скроем окно браузера
    options.add_experimental_option( "prefs",{'profile.managed_default_content_settings.javascript': 2}) # Отключаем JavsScript

    with webdriver.Chrome(service=service, options=options) as driver:
        # driver.maximize_window()

        try:
            # Проверим доступен ли сайт
            driver.get(IN_DATA['host'])
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CLASS_NAME, 'common-home'))
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
    for item in items[:IN_DATA['qty_items']]:
        try:
            # получаем каждую старницу и собираем данные
            driver.get(item['link'])
            WebDriverWait(driver, 20).until(lambda d: d.find_element(By.TAG_NAME, 'h1'))
            item_title = driver.find_element(By.TAG_NAME, 'h1').text
            item_brand = IN_DATA['name']
            item_price = driver.find_element(By.XPATH, '//meta[@itemprop="price"]').get_attribute('content')
            crumbs = [el.get_attribute('innerHTML') for el in driver.find_elements(By.XPATH, '//ol[@class="breadcrumb"]//a/span[@itemprop="name"]')]
            item_crumbs = '||'.join(crumbs[1:])
            item_desc = ''
            item_images = ''
            item_sizes = ''
            colors = ''
            sizes = ''
            categories = ''
            old_price = 0
            try:
                old_price = re.sub(r"[^\d\.]", "", driver.find_element(By.CLASS_NAME, 'old-price').text)
            except Exception as ex:
                pass

            try:
                item_desc = driver.find_element(By.XPATH, '//div[@itemprop="description"]//span[@class="options-text"]')
                item_desc = re.sub(r'<a.+?>(.+?)</a>', r'\1', item_desc.get_attribute('innerHTML')).replace('\r', '').replace('\n', '')
            except Exception as ex:
                pass

            try:
                colors = '||'.join((driver.find_element(By.XPATH, '//h5[contains(text(), "Цвет")]/following::span[1]').text).replace(', ', ',').split(','))
            except Exception as ex:
                pass

            try:
                sizes = '||'.join([re.sub(r"[^\d\.]", "", driver.find_element(By.XPATH, '//span[@class="option-numbers height"]').text), re.sub(r"[^\d\.]", "", driver.find_element(By.XPATH, '//span[@class="option-numbers weight"]').text)])
            except Exception as ex:
                pass

            try:
                cats = []
                for el in driver.find_elements(By.XPATH, '//span[@class="options-text__link"]'):
                    if el.text not in ['Цены']:
                        cats.append(el.text)
                categories = '||'.join(cats)
            except Exception as ex:
                pass

            item_params = json.dumps({
                'colors': colors,
                'sizes': sizes,
                'categories': categories,
                'old_price': old_price,
            })

            item_id = hashlib.sha256(f"{item_title}{item_brand}{item_price}{item['link']}".encode("utf-8")).hexdigest()
            try:
                images = [driver.find_element(By.XPATH, '//img[@itemprop="image"]')]
                k = 0
                images_urls = [i.get_attribute('src') for i in images]
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
            except Exception as ex:
                pass

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
            print(ex)
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
            elements = driver.find_elements(By.CLASS_NAME, 'list-product__image-wrapper')
            for element in elements:
                items.append(
                    {
                        'link': element.get_attribute('href'),
                    }

                )
            driver.find_element(By.CLASS_NAME, 'load_more')
            page_n += 1
            driver.get(f"{IN_DATA['target_url']}?page={page_n}")
            time.sleep(random.randint(1, 3))
        except Exception as ex:
            break
        if len(elements) >= IN_DATA['qty_items'] or len(items) >= IN_DATA['qty_items']:
            break
    return items


if __name__ == '__main__':
    get_items()
    winsound.Beep(500, 1000)
