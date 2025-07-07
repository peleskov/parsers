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
    'name': 'mebel_v_kazani',
    'folder': 'aksessuary',
    'host': 'https://mebel-v-kazani.ru/',
    'target_url': 'https://mebel-v-kazani.ru/cat/aksessuary-dlya-interera',
    'qty_items': 800,
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
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CLASS_NAME, 'content'))
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
            data = driver.find_element(By.XPATH, '//div[contains(@class, "product-details")]//a[contains(@class,"btnToCart")]')
            item_brand = data.get_attribute('data-factory')
            item_price = data.get_attribute('data-price')
            item_price = re.sub(r"[^\d\.]", "", item_price)
            crumbs = [el.get_attribute('innerHTML') for el in driver.find_elements(By.XPATH, '//ul[contains(@class,"breadcrumb")]//a/span')]
            item_crumbs = '||'.join(crumbs[2:])
            item_desc = ''
            item_images = ''
            item_sizes = ''
            try:
                item_desc = driver.find_element(By.XPATH, '//div[contains(@class, "product-details")]//div[contains(@class, "mt-4")]').get_attribute('innerHTML')
                item_desc = re.sub(r'<a.+?>(.+?)</a>', r'\1', item_desc.get_attribute('innerHTML'))
            except Exception as ex:
                pass
            item_desc = item_desc.replace('\r', '').replace('\n', '').replace('\r\n', '')

            item_params = ''
            try:
                WebDriverWait(driver, 5).until(lambda d: d.find_element(By.XPATH, '//div[@itemprop="description"]//table'))
                prop_rows = driver.find_elements(By.XPATH, '//div[@itemprop="description"]//table//tr')
                props = []
                for row in prop_rows:
                    try:
                        properties = row.find_elements(By.TAG_NAME, 'td')
                        props.append({
                            'title': properties[0].text,
                            'value': properties[1].text,
                        })
                    except Exception as ex:
                        pass
                item_params = json.dumps(props)
            except Exception as ex:
                pass

            item_id = hashlib.sha256(f"{item_title}{item_brand}{item_price}{item['link']}".encode("utf-8")).hexdigest()
            try:
                images = driver.find_elements(By.XPATH, '//*[contains(@class, "tab-content")]//img')
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
                else:
                    print('Нет картинок')
                    print()
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
    driver.get(IN_DATA['target_url'])

    while True:
        try:
            elements = driver.find_elements(By.XPATH, '//div[contains(@class, "products-list")]//h3[contains(@class, "product-title")]/a')
            for element in elements:
                items.append(
                    {
                        'link': element.get_attribute('href'),
                    }

                )
            next_link = driver.find_element(By.XPATH, '//li[@class="page-item next"]//a')
        except Exception as ex:
            break
        if len(elements) >= IN_DATA['qty_items'] or len(items) >= IN_DATA['qty_items']:
            break
        driver.get(next_link.get_attribute('href'))
        time.sleep(random.randint(1, 3))
    return items


if __name__ == '__main__':
    get_items()
    winsound.Beep(500, 1000)
