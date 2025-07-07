<?php
/**
 * Анализ категорий через browse API для расчета весов
 */

// Cookies (те же что и в get_skins_v2.php)
$cookies = 'i18n=ru; scid=eyJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwiYWxnIjoiQTE5MktXIn0.oGn-T0gomgwfyw1GWN998uvE0qyrv8iqScasPD59atAgs7s4hAH7ZA.BXDWzy2F7ZC79aT9BupN1g.BFyEN7Jyce_5-NvqBSCLqvJ9gaG-DOHmzAXKXC01DYjPDZaNNC_V75vGLvXT36XPc_JH1m3AB1zK9NK0oj-E29lPF3VbVkjvhrVGTUyESClOriM1xW3X7OreevG6ndw5s71Eoi5IiEQr679bVGDoyarGmDLlvlIBFvDqgAJSoVfPMhwmZoh6U2s9Eyd_5vuXaaqhvffSB3wKIV_Itu5eSr0HTzSi4ZnePJkvIYlkfzZbin0ntvrDLx0CaOqK35Q2O20XpDPdmcnKunhZwLb3ANuiw0c24TCJPj48jUYxItAgD5FUuqHZUxCKs8PmPMD2s4Sy6AN5v7hnzxHYzyesOA8WI7qGP3Ddt9cGJT3d0CjhAMf3C1YnPbgKdqntq8g9-DzbKnvlXXdwa7Z0EHDmcyUVAr1HvmdJTjPd9W_7RckhzB4K7-sOQJByKxAR5JMOu6zLSVel1yQf6FHL2k5Hnj0E781oOllVK6WAxYci30OHoHjp40_u2QbRO_N90eaMda52uPoRVF6mZXOUufyzYyLz5FTCL3ibuMEBMZnXb35BcYaMJ-LZKYBkt-3L162Tgx2mPQDqe4J5gKzZUjXk121IqHzVCJU7dY90wSxWQYEexiEGTnITqzbhaaxVW0C2UPdq8WdzgbjSERBhwFuGNB8ZCDKiuFpIkDorHq4azJMAZH_nq5-FyL6Obewd_QOI.1pzxV086assXxup4ZkPaFg; connect.sid=s%3Aw7q7iEHklOcLNEk-ekzQipaDLIwp9t0L.U8AgdL5OaTK24llyMXNmYy3yMELdRQIRqBrVRyCPmic; _csrf=feGx4eiqK1QZRq6tTYnFFjHp; cf_clearance=63Y6Mian0tZpJe.j0h4iBOXe6h1vXdqzvvrnaEWEJhQ-1751276882-1.2.1.1-ttCxzqlF6EXxAnBvGjE9fNg0dJw9G8osuVXDyKWzeySNSUWUbI6bHVdFpniR1u.IRoczE3qbzdynjsgT3Xn6usadT95OjbpVjFFb2wTqOFN76tP85RLxccYWZTmtSKTky0yRrCHMZl3PvFHOVr.wupnSVyMXU.WY2eKl5Ln8lbuY5lJ7GAhpPynx7oiP.OYmMIz2TewpcgvH9hFVwBYqeWfQ536n78ctAnGR0lNuAKtV3XRbanI0qbVOdcSnkbIkTyjicn36hTjFCEKDAR7SJW8hMF_2iQDZxxPTVMTPl7SRs.BH2YaeX9sJESGcSXNWIQG51GYOCAKushThqFXLUWIUuipVyNeNqM7BLaSCgec; __cf_bm=oe.FQeGKDAzayY3oYMIfR8Se91bhiFPZ7MrLAdB5gmU-1751279732-1.0.1.1-jhh6elxfvxUvBh7Kb045xCzBkxG5fxqrKI7owLOmBlX9L8_hvQ0sYAOKH1ndRsbfIDvXSZIcgTP1oosHUsiO8Ul4srX2q0YfFGpKE';

function fetchViaCurl($url, $cookies) {
    $command = "curl '$url' " .
        "-H 'accept: */*' " .
        "-H 'accept-language: ru-RU,ru;q=0.8' " .
        "-H 'cookie: $cookies' " .
        "-H 'priority: u=1, i' " .
        "-H 'referer: https://skinport.com/ru/market' " .
        "-H 'sec-ch-ua: \"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Brave\";v=\"138\"' " .
        "-H 'sec-ch-ua-mobile: ?0' " .
        "-H 'sec-ch-ua-platform: \"Windows\"' " .
        "-H 'sec-fetch-dest: empty' " .
        "-H 'sec-fetch-mode: cors' " .
        "-H 'sec-fetch-site: same-origin' " .
        "-H 'sec-gpc: 1' " .
        "-H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36' " .
        "--compressed 2>/dev/null";
    
    $response = shell_exec($command);
    return $response;
}

function fetchWithRetry($url, $cookies, $maxRetries = 5) {
    for ($attempt = 1; $attempt <= $maxRetries; $attempt++) {
        $response = fetchViaCurl($url, $cookies);
        
        if ($response) {
            $data = json_decode($response, true);
            
            // Проверка на лимит запросов
            if ($data && isset($data['success']) && $data['success'] === false && isset($data['message']) && $data['message'] === 'RATE_LIMIT_REACHED') {
                $sleepTime = $attempt * 60; // 1 минута, 2 минуты, 3 минуты и т.д.
                echo "⚠️ Лимит запросов (попытка $attempt/$maxRetries). Ожидание $sleepTime секунд...\\n";
                sleep($sleepTime);
                continue;
            }
            
            return $response;
        } else {
            echo "⚠️ Пустой ответ (попытка $attempt/$maxRetries)\\n";
            if ($attempt < $maxRetries) {
                sleep(30); // Ждем 30 секунд между попытками при пустом ответе
            }
        }
    }
    
    echo "❌ Превышено количество попыток ($maxRetries). Остановка.\\n";
    exit(1);
}

// Загружаем категории из файла
$categoriesFile = dirname(__FILE__) . '/categories.json';
$categories = json_decode(file_get_contents($categoriesFile), true);

if (!$categories) {
    die("Ошибка загрузки файла categories.json\n");
}

echo "Запуск анализа через browse API...\n";

$results = [];
$totalItems = 0;

echo "\nАнализ категорий через browse API...\n\n";

foreach ($categories as $key => $category) {
    echo "Проверяем: " . $category['name'] . "... ";
    
    try {
        // Используем готовый URL из конфига с повторными попытками
        $response = fetchWithRetry($category['url'], $cookies);
        
        if ($response) {
            $data = json_decode($response, true);
            
            // Ищем total в filter.total (новый формат browse API)
            if ($data && isset($data['filter']['total'])) {
                $count = $data['filter']['total'];
                $results[] = [
                    'name' => $category['name'],
                    'url' => $category['url'],
                    'count' => $count
                ];
                $totalItems += $count;
                echo $count . " товаров\n";
                
                // Пока сохраняем количество, вес пересчитаем в конце
                $categories[$key]['count'] = $count;
            } else {
                echo "Ошибка парсинга JSON или нет поля filter.total\n";
                if (strlen($response) < 500) {
                    echo "Ответ: " . $response . "\n";
                }
            }
        } else {
            echo "Пустой ответ от curl\n";
        }
        
    } catch (Exception $e) {
        echo "Ошибка: " . $e->getMessage() . "\n";
    }
    
    // Случайная задержка между запросами
    sleep(rand(1, 3));
}

echo "\n\nРЕЗУЛЬТАТЫ:\n";
echo "Всего товаров: $totalItems\n\n";

if ($totalItems > 0) {
    // Расчет процентов
    echo "Распределение товаров по весам:\n\n";
    
    foreach ($results as $result) {
        $percentage = ($result['count'] / $totalItems) * 100;
        
        printf("%-25s: %6d товаров (%.2f%%)\n", 
            $result['name'], 
            $result['count'], 
            $percentage
        );
    }
    
    // Пересчитываем веса как проценты и очищаем временное поле count
    foreach ($categories as &$category) {
        if (isset($category['count'])) {
            $category['weight'] = round(($category['count'] / $totalItems), 4);
            unset($category['count']); // Удаляем временное поле
        }
    }
    
    // Сохранение обновленных категорий с весами
    file_put_contents($categoriesFile, json_encode($categories, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    echo "\n\nОбновленные категории с весами сохранены в: $categoriesFile\n";
} else {
    echo "Не удалось получить данные ни из одной категории.\n";
}
?>