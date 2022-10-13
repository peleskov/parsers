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

'''
Собирает 3-4 товара потом сервер становится не доступен!!!
'''



IN_DATA = {
    'name': 'kns.ru',
    'host': 'https://www.kns.ru',
    'target_url': 'https://www.kns.ru/catalog/noutbuki/',
    'image_url': '/www/u1165452/data/www/forta.market/images/thumbnails',
    'category_path': f'Доставка еды///Сыроварня///Красота и здоровье///ДУХИ.РФ',
    'qty_items': 31
}
PATH_DRIVER = os.path.join('chromedriver.exe')
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"))
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
    # options.add_argument('headless')
    with webdriver.Chrome(service=service, options=options) as driver:
        driver.maximize_window()

        try:
            # Проверим доступен ли сайт
            driver.get(IN_DATA['host'])
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.TAG_NAME, 'main'))
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
            f.write('Product code;Language;Category;Status;Inventory tracking;Price;Product name;Description;Thumbnail;Detailed image;Image URL;Vendor\n')

        # Создаем каталог для изображений если его нет
        path_images = os.path.join(PATH_ROOT, 'images')
        if not os.path.exists(path_images):
            os.makedirs(path_images)

        # Соберем ссылки на товары со всех страниц, ограничение по количеству IN_DATA['qty_items']
        items_links = []
        url = IN_DATA['target_url']
        page_n = 1
        while len(items_links) < IN_DATA['qty_items'] and url:
            page_n += 1
            data = get_links(driver, url, page_n)
            if data['links']:
                items_links.extend(data['links'])
            url = data['target_url']
            time.sleep(random.randint(1, 5))

        # Пройдем по всем элемента и соберем данные
        product_list = []
        reg = re.compile(r'[^\d]')
        for link in items_links[:IN_DATA['qty_items']]:
            try:
                driver.get(link)
                WebDriverWait(driver, 60).until(lambda d: d.find_element(By.XPATH, '//div[@id="goodsinfo"]'))
                product_name = driver.find_element(By.TAG_NAME, 'h1')
                product_id = hashlib.sha256(f"{product_name.text}{link}".encode("utf-8")).hexdigest()
                product_price = driver.find_element(By.XPATH, '//span[@class="price-val"]')
                description = driver.find_element(By.XPATH, '//div[@id="goodsinfo"]/div[1]')
                images = driver.find_elements(By.XPATH, '//ul[@class="GoodsSlider"]//li')

                # получаем картинки
                images_list = []
                thumbs_list = []
                if len(images) > 0:
                    i = 0
                    for img in images:
                        i += 1
                        image_url = f'{IN_DATA["host"]}{img.get_attribute("data-url")}'
                        image_ext = image_url.split('.')[-1]
                        image_name = f'{product_id}_{i}.{image_ext}'
                        path_image = os.path.join(path_images, image_name)

                        thumb_url = f'{IN_DATA["host"]}{img.find_element(By.TAG_NAME, "img").get_attribute("src").replace(IN_DATA["host"], "")}'
                        thumb_ext = thumb_url.split('.')[-1]
                        thumb_name = f'{product_id}_thumb_{i}.{thumb_ext}'
                        path_thumb = os.path.join(path_images, thumb_name)

                        # проверяем нет ли еще этой картинки, что бы при повторном запуске не качать снова
                        if not os.path.isfile(path_image):
                            try:
                                image = requests.get(image_url, headers=HEADERS)
                                with open(path_image, 'wb') as f:
                                    f.write(image.content)
                                    images_list.append(image_name)
                                time.sleep(random.randint(1, 5))
                            except Exception as ex:
                                pass
                        else:
                            images_list.append(image_name)

                        # проверяем нет ли еще этой картинки, что бы при повторном запуске не качать снова
                        if not os.path.isfile(path_thumb):
                            try:
                                thumb = requests.get(thumb_url, headers=HEADERS)
                                with open(path_thumb, 'wb') as f:
                                    f.write(thumb.content)
                                    thumbs_list.append(thumb_name)
                                time.sleep(random.randint(1, 5))
                            except Exception as ex:
                                pass
                        else:
                            thumbs_list.append(thumb_name)

                image_str = '///'.join(images_list) if len(images_list) > 0 else ''
                thumb_str = '///'.join(thumbs_list) if len(images_list) > 0 else ''

                # заполняем лист с товарами
                product_list.append((product_id,
                                     'ru',
                                     IN_DATA['category_path'],
                                     'A',
                                     'D',
                                     reg.sub('', product_price.text),
                                     product_name.text,
                                     description.text,
                                     thumb_str,
                                     image_str,
                                     IN_DATA['image_url'],
                                     IN_DATA['name']))

            except Exception as ex:
                print(ex)
                continue
    if len(product_list) > 0:
        # пишем лист с товарами в csv файл
        with open(path_results, 'a', newline="", encoding='UTF8') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerows(product_list)
    return


def get_links(driver, page_url, n) -> dict:
    out_data = {'links': None, 'target_url': None}
    driver.get(page_url)
    try:
        WebDriverWait(driver, 120).until(lambda d: d.find_element(By.ID, 'glist'))

        # Выберем город если есть ссылка
        try:
            driver.find_element(By.XPATH, '//div[@id="modal_main"]//button[contains(@class, "city-ok")]').click()
        except exceptions.NoSuchElementException:
            pass

        out_data['target_url'] = f'{IN_DATA["target_url"]}page{n}/'
        g_list = driver.find_element(By.ID, 'glist')
        links = g_list.find_elements(By.XPATH, '//div[contains(@class, "image-info")]/a')
        out_data['links'] = [link.get_attribute("href") for link in links]
    except Exception as ex:
        print(ex)
    return out_data


if __name__ == '__main__':
    get_items()
    # f"https://forta.market/images/thumbnails/{SITE['name']}/{translit(folder['name'], language_code='ru', reversed=True).replace(' ', '').lower()}/images/{product['image']}",
    # f"https://forta.market/images/thumbnails/{SITE['name']}/{translit(folder['name'], language_code='ru', reversed=True).replace(' ', '').lower()}/images/{product['image']}",
