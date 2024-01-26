import json
import math

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
    'name': 'kns_ru',
    'folder': 'noutbuki',
    'host': 'https://www.kns.ru/',
    'target_url': 'https://kns.ru/multi/catalog/noutbuki/_v-nalichii/',
    'qty_items': 1000,
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
    options.add_argument('headless') # Скроем окно браузера
    # options.add_experimental_option( "prefs",{'profile.managed_default_content_settings.javascript': 2}) # Отключаем JavsScript
    with webdriver.Chrome(service=service, options=options) as driver:
        # driver.maximize_window()

        try:
            # Проверим доступен ли сайт
            driver.get(IN_DATA['host'])
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CLASS_NAME, 'header-main'))
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
    flag_try = 0
    row_count = 0
    for item in items[:IN_DATA['qty_items']]:
        try:
            flag_try = 0
            # получаем каждую старницу и собираем данные
            driver.get(item['link'])
            WebDriverWait(driver, 20).until(lambda d: d.find_element(By.TAG_NAME, 'h1'))
            item_title = driver.find_element(By.TAG_NAME, 'h1').text
            item_price = driver.find_element(By.CLASS_NAME, 'price-val').text
            item_price = round(float(re.sub(r"[^\d\.]", "", item_price)))

            driver.find_element(By.ID, 'aextFields').click()
            item_params = ''
            item_brand = IN_DATA['name']
            try:
                flag_try = 1
                WebDriverWait(driver, 60).until(lambda d: d.find_element(By.XPATH, '//div[@id="extFields"]//div[@class="afterHTech"]'))
                prop_rows = driver.find_elements(By.XPATH, '//div[@id="extFields"]//div[@class="afterHTech"]/following::div[1]//div[contains(@class,"row no-gutters")]')
                props = []
                prop = {}
                for row in prop_rows:
                    try:
                        flag_try = 2
                        if 'title' in row.get_attribute('class'):
                            if len(prop) > 0:
                                props.append(prop)
                            prop = {
                                'title': row.find_element(By.TAG_NAME, 'div').text,
                                'items': []
                            }
                        else:
                            p = row.find_elements(By.TAG_NAME, 'div')
                            prop['items'].append({p[0].text: p[1].text})
                    except Exception as ex:
                        pass
                item_brand = props[0]['items'][0]['Производитель'] if 'Производитель' in props[0]['items'][0] else ''
                item_params = json.dumps(props)
            except Exception as ex:
                pass
            crumbs = []
            for cr in driver.find_elements(By.XPATH, '//ol[@class="breadcrumb"]//span[@itemprop="name"]'):
                crumbs.append(cr.text)
            item_crumbs = json.dumps(crumbs[1:-1])

            try:
                flag_try = 3
                WebDriverWait(driver, 2).until(lambda d: d.find_element(By.CLASS_NAME, 'description'))
                description = driver.find_element(By.CLASS_NAME, 'description')
                item_desc = description.get_attribute('innerHTML')
            except Exception as ex:
                item_desc = ''
            item_sizes = ''
            item_id = hashlib.sha256(f"{item_title}{item_brand}{item_price}{item['link']}".encode("utf-8")).hexdigest()

            item_images = ''
            images = driver.find_elements(By.XPATH, '//ul[@class="GoodsSlider"]//li')
            k = 0
            images_urls = [f"{IN_DATA['host'][:-1]}{i.get_attribute('data-url')}" for i in images]
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
                            flag_try = 4
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
                row_count += 1

        except Exception as ex:
            # print(exp, ex)
            print('Error ', flag_try, item['link'])
            time.sleep(random.randint(1, 5))
            continue
        time.sleep(random.randint(1, 3))
    print(f'Собрано информации по {row_count} товаров.')
    return True


def get_links(driver) -> list:
    items = []
    page_n = 1
    driver.get(IN_DATA['target_url'])
    max_page = 1
    try:
        # WebDriverWait(driver, 20).until(lambda d: d.find_element(By.ID, 'TotalGoodsCount'))
        total_goods = driver.find_element(By.ID, 'TotalGoodsCount')
        max_page = math.ceil(int(total_goods.get_attribute('innerHTML'))/30)
    except Exception as ex:
        pass
    while True:
        if len(items) >= IN_DATA['qty_items']:
            break
        if page_n > max_page:
            break
        try:
            elements = driver.find_elements(By.XPATH, '//a[contains(@class, "name")]')
            if len(elements) == 0:
                break
            for element in elements:
                items.append(
                    {
                        'link': element.get_attribute('href'),
                    }

                )
            page_n += 1
            driver.get(f"{IN_DATA['target_url']}page{page_n}/")
        except Exception as ex:
            break
    return items


if __name__ == '__main__':
    get_items()
    winsound.Beep(500, 1000)
