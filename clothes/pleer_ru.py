import csv
import hashlib
import os
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common import exceptions

IN_DATA = {
    'name': 'pleer.ru',
    'host': 'https://www.pleer.ru/',
    'url': 'https://www.pleer.ru/list_kpk-i-kommunikatory.html',
    'path_images': '/www/u1165452/data/www/forta.market/images/thumbnails',
    'category_path': f'Доставка еды///Сыроварня///Красота и здоровье///ДУХИ.РФ',
    'qty_items': 20
}
PATH_ROOT = os.path.join('..', '_sites', IN_DATA["name"].replace(".", "_"))
PATH_DRIVER = os.path.join('chromedriver.exe')
HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,ro;q=0.6'
}


def get_items():
    # создаем каталог для этого сайта, если его нет
    if not os.path.exists(PATH_ROOT):
        os.makedirs(PATH_ROOT)
    path_results = os.path.join(PATH_ROOT, f'results_{IN_DATA["name"].replace(".", "_")}.csv')
    # Создаем csv файл для загрузки данных в базу, и пишем в него первую строку с обозначением колонок
    with open(path_results, 'w', newline="", encoding='UTF8') as f:
        f.write('Product code;Language;Status;Inventory tracking;Category;Price;Detailed image;Thumbnail;Product name;Description;Vendor\n')

    # Создаем каталог для изображений если его нет
    path_images = os.path.join(PATH_ROOT, 'images')
    if not os.path.exists(path_images):
        os.makedirs(path_images)

    # Запускаем сервис Chrome
    service = ChromeService(executable_path=PATH_DRIVER)

    # Скроем окно браузера
    options = Options()
    # options.add_argument('headless')
    with webdriver.Chrome(service=service, options=options) as driver:
        driver.maximize_window()

        # Соберем ссылки на товары со всех страниц, ограничение по количеству IN_DATA['qty_items']
        items_links = []
        url = IN_DATA['url']
        while len(items_links) < IN_DATA['qty_items'] and url:
            data = get_pages_link(url, driver)
            if data['links']:
                items_links.extend(data['links'])
            url = data['url']

        # Пройдем по всем элемента и соберем данные
        product_list = []
        reg = re.compile(r'[^\d]')
        for link in items_links:
            driver.get(link)
            WebDriverWait(driver, 60).until(lambda d: d.find_element(By.XPATH, '//span[@class="product_title"]'))
            product_name = driver.find_element(By.XPATH, '//span[@class="product_title"]')
            product_id = hashlib.sha256(f"{product_name.text}{link}".encode("utf-8")).hexdigest()
            product_price = driver.find_element(By.XPATH, '//div[contains(@class,"product_price_color1")]//div[@class="price"]')
            description = product_name
            img_url = driver.find_element(By.XPATH, '//td[@class="photo_self_section"]/a').get_attribute("href")

            # получаем картинку, проверяем нет ли ее еще, что бы при повторном запуске не качать снова
            try:
                image_ext = img_url.split('.')[-1]
                image_name = f'{product_id}.{image_ext}'
                path_image = os.path.join(path_images, image_name)
                if not os.path.isfile(path_image):
                    image = requests.get(img_url, headers=HEADERS)
                    with open(path_image, 'wb') as f:
                        f.write(image.content)

                # заполняем лист с товарами
                product_list.append((product_id,
                                     'ru',
                                     'A',
                                     'D',
                                     IN_DATA['category_path'],
                                     reg.sub('', product_price.text),
                                     image_name,
                                     image_name,
                                     product_name.text,
                                     description,
                                     IN_DATA['name']))

            # если пошло что то не так, просто проустим это товар
            except Exception as ex:
                print(ex)
                continue

        # пишем лист с товарами в csv файл
        with open(path_results, 'a', newline="", encoding='UTF8') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerows(product_list)
    return True


def get_pages_link(page_url, driver) -> dict:
    out = {'links': None, 'url': None}
    driver.get(page_url)
    WebDriverWait(driver, 120).until(lambda d: d.find_element(By.XPATH, '//div[@class="section_item"]'))
    try:
        # Найдем ссылку на следующую страницу если она есть
        url = driver.find_element(By.XPATH, '//div[@id="next_page"]//a')
        out['url'] = f'{IN_DATA["host"]}{url.get_attribute("href")}'
    except exceptions.NoSuchElementException:
        pass
    try:
        # Найдем ссылки на элементы если они есть
        links = driver.find_elements(By.XPATH, '//div[@class="section_item"]//span[@class="pad_r"]/a')
        out['links'] = [f'{IN_DATA["host"]}{link.get_attribute("href")}' for link in links]
    except exceptions.NoSuchElementException:
        pass
    return out


if __name__ == '__main__':
    print(get_items())
    # f"https://forta.market/images/thumbnails/{SITE['name']}/{translit(folder['name'], language_code='ru', reversed=True).replace(' ', '').lower()}/images/{product['image']}",
    # f"https://forta.market/images/thumbnails/{SITE['name']}/{translit(folder['name'], language_code='ru', reversed=True).replace(' ', '').lower()}/images/{product['image']}",
