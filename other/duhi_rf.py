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
    'name': 'duhi_rf',
    'host': 'https://xn--d1ai6ai.xn--p1ai/',
    'target_url': 'https://xn--d1ai6ai.xn--p1ai/index.php?filter_search=1&section=6&price_from=0&price_to=99000&volume_from=0&volume_to=1000&new_pr=&sale=&vint_pr=&aviable_pr=1&cmd=show_items',
    'qty_items': 100000,
}
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"))
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

    # Скроем окно браузера
    options = Options()
    options.add_argument('headless')
    with webdriver.Chrome(service=service, options=options) as driver:
        # driver.maximize_window()

        try:
            # Проверим доступен ли сайт
            driver.get(IN_DATA['host'])
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.CLASS_NAME, 'controller_main_page'))
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


def get_data(driver, items, path_results) -> list:
    for item in items[:IN_DATA['qty_items']]:
        try:
            # получаем каждую старницу и собираем данные
            # 'id;Title;Brand;Price;Sizes;Description;Images;\n'
            driver.get(item)
            WebDriverWait(driver, 20).until(lambda d: d.find_element(By.TAG_NAME, 'h1'))
            item_title = driver.find_element(By.TAG_NAME, 'h1').text
            elemets_crumbs = driver.find_elements(By.XPATH, '//ul[contains(@class, "crumbs")]//li/a/span')
            crumbs = [cr.text for cr in elemets_crumbs]
            item_crumbs = '||'.join(crumbs[1:])
            item_brand = IN_DATA['name']
            offers = driver.find_elements(By.XPATH, '//tr[@itemprop="offers"]')
            item_volume = ''
            for offer in offers:
                volume = re.sub(r"[^\d\.]", "", offer.find_element(By.CLASS_NAME, 'table_volume').text)
                item_volume = volume
                item_price = offer.find_element(By.CLASS_NAME, 'table_price').find_element(By.TAG_NAME, 'span').get_attribute('innerHTML')
                if round(float(volume)) >= 50:
                    item_volume = volume
                    item_price = offer.find_element(By.CLASS_NAME, 'table_price').find_element(By.TAG_NAME, 'span').get_attribute('innerHTML')
                    break
            item_price = round(float(re.sub(r"[^\d\.]", "", item_price)))
            item_id = hashlib.sha256(f"{item_title}{item_brand}{item_price}{item[0]}".encode("utf-8")).hexdigest()
            item_sizes = item_volume
            item_desc = ''
            try:
                WebDriverWait(driver, 1).until(lambda d: d.find_element(By.ID, 'description'))
                item_desc = driver.find_element(By.ID, 'description').get_attribute('innerHTML') \
                    .replace('\r', '').replace('\n', '')
            except:
                pass
            item_params = driver.find_element(By.XPATH, '//h1/following::div[@class="d-flex justify-content-between"]/div').get_attribute('innerHTML') \
                .replace('\r', '').replace('\n', '')

            images_urls = []
            try:
                WebDriverWait(driver, 20).until(lambda d: d.find_element(By.XPATH, '//img[@itemprop="image"]'))
                images = driver.find_elements(By.XPATH, '//img[@itemprop="image"]')
                for image in images[:1]:
                    images_urls.append(image.get_attribute('src'))
            except:
                pass
            item_images = ''
            if len(images_urls) > 0:
                k = 0
                item_images_arr = []
                for item_image_url in set(images_urls):
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
            print(ex)
            time.sleep(random.randint(1, 5))
            continue
        time.sleep(random.randint(1, 3))
    return True


def get_links(driver) -> list:
    driver.get(IN_DATA['target_url'])
    items = []
    while True:
        try:
            all_showed = driver.find_element(By.XPATH, '//div[@id="product_tab"]//div[@class="all_showed d-none"]')
            btn_more = driver.find_element(By.XPATH, '//div[@id="product_tab"]//div[@data-page="more_search_product"]')
            elements = driver.find_elements(By.CLASS_NAME, 'products_wrap')
        except Exception as ex:
            break
        if len(elements) >= IN_DATA['qty_items']:
            break
        if not btn_more:
            break
        elif not all_showed:
            break
        btn_more.click()
        time.sleep(random.randint(1, 5))
    try:
        elements = driver.find_elements(By.CLASS_NAME, 'products_wrap')
        for element in elements:
            items.append(
                element.find_element(By.TAG_NAME, 'a').get_attribute('href')
            )
    except Exception as ex:
        print(ex)
    return items


if __name__ == '__main__':
    get_items()
    winsound.Beep(500, 1000)
