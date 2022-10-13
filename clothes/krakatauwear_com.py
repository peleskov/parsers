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
    'name': 'krakatauwear.com',
    'host': 'https://krakatauwear.com',
    'target_url': 'https://krakatauwear.com/collections/men',
    'qty_items': 1,
}
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"))
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

    # Скроем окно браузера
    options = Options()
    options.add_argument('headless')
    with webdriver.Chrome(service=service, options=options) as driver:
        driver.maximize_window()

        try:
            # Проверим доступен ли сайт
            driver.get(IN_DATA['host'])
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, 'main-wrap'))
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
            f.write('id;Title;Brand;Price;Sizes;Description;Images\n')

        # Создаем каталог для изображений если его нет
        if not os.path.exists(PATH_IMAGES):
            os.makedirs(PATH_IMAGES)

        # Соберем ссылки со всех страниц, ограничение по количеству IN_DATA['qty_items']
        items_list = []
        url = IN_DATA['target_url']
        page_n = 1
        while len(items_list) < IN_DATA['qty_items'] and url:
            page_n += 1
            data = get_links(driver, url, page_n)
            if data['items']:
                items_list.extend(data['items'])
            url = data['target_url']
            time.sleep(random.randint(1, 5))
        # Соберем данные
        results = get_data(driver, items_list)
        if len(results) > 0:
            # пишем лист с товарами в csv файл
            with open(path_results, 'a', newline="", encoding='UTF8') as f:
                writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                writer.writerows(results)
    return True


def get_data(driver, items) -> list:
    items_list = []
    for item in items[:IN_DATA['qty_items']]:
        try:
            # получаем каждую старницу и собираем данные
            # 'id;Title;Brand;Price;Sizes;Description;Images\n'
            driver.get(item[0])
            WebDriverWait(driver, 60).until(lambda d: d.find_element(By.CLASS_NAME, 'product-wrapper'))
            item_title = driver.find_element(By.XPATH, '//h1[@class="page-row-heading"]').text
            item_brand = driver.find_element(By.XPATH, '//meta[@itemprop="brand"]').get_attribute('content')
            item_price = driver.find_element(By.ID, 'current_variant_price').text
            item_id = hashlib.sha256(f"{item_title}{item_brand}{item_price}{item[0]}".encode("utf-8")).hexdigest()
            item_desc = driver.find_element(By.XPATH, '//meta[@itemprop="description"]').get_attribute('content') \
                .replace('\r', '').replace('\n', '')
            sizes = driver.find_elements(By.XPATH, '//p[@class="sizes"]//a')
            sizes_list = []
            for size in sizes:
                sizes_list.append(size.text)
            item_sizes = '||'.join(sizes_list)
            item_desc = driver.find_element(By.CLASS_NAME, 'desc').get_attribute('innerHTML') \
                .replace('\r', '').replace('\n', '')

            images = driver.find_elements(By.XPATH, '//div[@class="swiper-slide"]/a[@data-fancybox]')
            k = 0
            item_images_arr = []
            for image in images:
                k += 1
                item_image_url = image.get_attribute("href")
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
            # заполняем лист с товарами
            items_list.append((
                item_id,
                item_title,
                item_brand,
                item_price,
                item_sizes,
                item_desc,
                item_images,
            ))

        except Exception as ex:
            print(ex)
            continue
    return items_list


def get_links(driver, page_url, n) -> dict:
    out_data = {'items': None, 'target_url': None}
    driver.get(page_url)
    try:
        WebDriverWait(driver, 30).until(lambda d: d.find_element(By.CLASS_NAME, 'page-row-content'))
        # out_data['target_url'] = f'{IN_DATA["target_url"]}?page={n}&recordsPageCount=100'
        elements = driver.find_elements(By.CLASS_NAME, 'product-image')
        items = []
        for element in elements:
            items.append([
                element.get_attribute("href"),
            ])
        out_data['items'] = items
    except Exception as ex:
        print(ex)
    return out_data


if __name__ == '__main__':
    get_items()

