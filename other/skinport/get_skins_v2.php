<?php
/**
 * Сбор товаров с Skinport используя categories.json и веса
 */

// ========== КОНФИГУРАЦИЯ ==========
$TOTAL_ITEMS = 6000; // Общее количество товаров для сбора

// Загружаем куки из файла
$cookiesData = json_decode(file_get_contents('cookies.json'), true);
if (!$cookiesData) {
    die("Ошибка загрузки cookies.json\n");
}

function fetchViaCurl($url, $cookieData) {
    $cookies = $cookieData['cookies'];
    $userAgent = $cookieData['user_agent'];
    
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
        "-H 'user-agent: $userAgent' " .
        "--compressed 2>/dev/null";
    
    $response = shell_exec($command);
    return $response;
}

function fetchWithRetry($url, $cookieData, $maxRetries = 5) {
    for ($attempt = 1; $attempt <= $maxRetries; $attempt++) {
        $response = fetchViaCurl($url, $cookieData);
        
        if ($response) {
            $data = json_decode($response, true);
            
            // Проверка на лимит запросов
            if ($data && isset($data['success']) && $data['success'] === false && isset($data['message']) && $data['message'] === 'RATE_LIMIT_REACHED') {
                $sleepTime = $attempt * 60; // 1 минута, 2 минуты, 3 минуты и т.д.
                echo "  ⚠️ Лимит запросов (попытка $attempt/$maxRetries). Ожидание $sleepTime секунд...\\n";
                sleep($sleepTime);
                continue;
            }
            
            return $response;
        } else {
            echo "  ⚠️ Пустой ответ (попытка $attempt/$maxRetries)\\n";
            if ($attempt < $maxRetries) {
                sleep(30); // Ждем 30 секунд между попытками при пустом ответе
            }
        }
    }
    
    echo "  ❌ Превышено количество попыток ($maxRetries). Остановка.\\n";
    return false; // Возвращаем false вместо exit для корректного закрытия файла
}

function getItemDescription($appid, $url, $version, $cookieData) {
    $apiUrl = "https://skinport.com/api/item?appid=$appid&url=$url";
    if ($version) {
        $apiUrl .= "&version=" . urlencode($version);
    }
    
    $response = fetchWithRetry($apiUrl, $cookieData);
    if ($response) {
        $data = json_decode($response, true);
        if ($data && isset($data['data']['item']['description'])) {
            return $data['data']['item']['description'];
        }
    }
    return '';
}

function loadCategories() {
    $categoriesFile = 'categories.json';
    if (!file_exists($categoriesFile)) {
        die("Файл $categoriesFile не найден!\n");
    }
    
    $categories = json_decode(file_get_contents($categoriesFile), true);
    if (!$categories) {
        die("Ошибка чтения $categoriesFile\n");
    }
    
    return $categories;
}

function loadProgress($progressFile) {
    if (file_exists($progressFile)) {
        $progress = json_decode(file_get_contents($progressFile), true);
        if ($progress) {
            echo "✓ Загружен прогресс: категория {$progress['current_category']}, собрано {$progress['total_collected']} товаров\\n";
            return $progress;
        }
    }
    return [
        'current_category' => 0,
        'total_collected' => 0,
        'categories_progress' => []
    ];
}

function saveProgress($progressFile, $progress) {
    file_put_contents($progressFile, json_encode($progress, JSON_PRETTY_PRINT));
}

function getCategoryFileName($categoryInfo) {
    // Создаем директорию results если её нет
    $resultsDir = 'results';
    if (!is_dir($resultsDir)) {
        mkdir($resultsDir, 0755, true);
    }
    
    // Получаем чистое имя категории для файла
    $categoryName = $categoryInfo['category'];
    // Убираем недопустимые символы для имени файла
    $categoryName = preg_replace('/[^a-zA-Z0-9_-]/', '_', $categoryName);
    return "$resultsDir/result_{$categoryName}.json";
}

function calculateItemsPerCategory($categories, $totalItems) {
    $distribution = [];
    
    foreach ($categories as $category) {
        $itemsCount = (int)($totalItems * $category['weight']);
        if ($itemsCount > 0) {
            // Извлекаем параметры из URL
            $urlParts = parse_url($category['url']);
            parse_str($urlParts['query'], $params);
            
            $distribution[] = [
                'name' => $category['name'],
                'appid' => $params['appid'] ?? 730,
                'category' => $params['cat'] ?? '',
                'items_needed' => $itemsCount
            ];
        }
    }
    
    // Корректируем общее количество
    $currentTotal = array_sum(array_column($distribution, 'items_needed'));
    if ($currentTotal < $totalItems && !empty($distribution)) {
        $distribution[0]['items_needed'] += $totalItems - $currentTotal;
    }
    
    return $distribution;
}

// ========== ОСНОВНОЙ КОД ==========

echo "🚀 Сбор товаров с Skinport используя categories.json\n";
echo "Общее количество товаров: $TOTAL_ITEMS\n";
echo "Режим: БЕЗ прокси (прямое соединение)\n";

// Фильтруем только заполненные куки
$validCookies = array_values(array_filter($cookiesData, function($cookie) {
    return !empty($cookie['cookies']);
}));

if (empty($validCookies)) {
    die("❌ Нет заполненных куки в cookies.json! Добавьте куки из браузеров.\n");
}

// Используем первый рабочий набор куки
$currentCookie = $validCookies[0];
echo "Используем куки: {$currentCookie['name']}\n";
echo "User-Agent: " . substr($currentCookie['user_agent'], 0, 50) . "...\n\n";

// Загружаем категории
$categories = loadCategories();
echo "✓ Загружено категорий: " . count($categories) . "\n";

// Загружаем прогресс
$progressFile = 'progress.json';
$progress = loadProgress($progressFile);

// Рассчитываем распределение
$distribution = calculateItemsPerCategory($categories, $TOTAL_ITEMS);

echo "\nРаспределение товаров по категориям:\n";
foreach ($distribution as $item) {
    echo "  {$item['name']}: {$item['items_needed']} товаров\n";
}
echo "\n" . str_repeat("=", 60) . "\n\n";

echo "📄 Результаты будут сохраняться в отдельные файлы по категориям\n";
$totalProcessed = $progress['total_collected'];

// Обрабатываем каждую категорию начиная с текущей
foreach ($distribution as $categoryIndex => $categoryInfo) {
    // Пропускаем уже обработанные категории
    if ($categoryIndex < $progress['current_category']) {
        echo "⏭️ Пропускаем уже обработанную категорию: {$categoryInfo['name']}\n";
        continue;
    }
    
    echo "📂 Категория: {$categoryInfo['name']} (нужно: {$categoryInfo['items_needed']})\n";
    
    // Получаем имя файла для категории
    $categoryFile = getCategoryFileName($categoryInfo);
    echo "  💾 Файл: $categoryFile\n";
    
    // Восстанавливаем прогресс для текущей категории
    $collectedItems = 0;
    $skip = 0; // Начинаем с 0, первая страница без skip
    $isFirstItem = true;
    
    if ($categoryIndex == $progress['current_category'] && isset($progress['categories_progress'][$categoryIndex])) {
        $collectedItems = $progress['categories_progress'][$categoryIndex]['collected'];
        $skip = $progress['categories_progress'][$categoryIndex]['skip'];
        echo "  ↩️ Продолжаем с: собрано $collectedItems, skip $skip\n";
    }
    
    // Открываем файл для категории
    if ($collectedItems > 0 && file_exists($categoryFile)) {
        // Продолжаем дозапись в существующий файл
        $fileHandle = fopen($categoryFile, 'r+');
        if (!$fileHandle) {
            die("Не удалось открыть файл для дозаписи: $categoryFile\n");
        }
        // Перемещаемся в конец файла перед закрывающей скобкой
        fseek($fileHandle, -2, SEEK_END); // Убираем \n]
        $isFirstItem = false;
    } else {
        // Создаем новый файл
        $fileHandle = fopen($categoryFile, 'w');
        if (!$fileHandle) {
            die("Не удалось открыть файл для записи: $categoryFile\n");
        }
        // Записываем начало JSON массива
        fwrite($fileHandle, "[\n");
        $isFirstItem = true;
    }
    
    // Собираем товары пока не наберем нужное количество
    while ($collectedItems < $categoryInfo['items_needed']) {
        if ($skip == 0) {
            $url = "https://skinport.com/api/browse/{$categoryInfo['appid']}?cat={$categoryInfo['category']}";
        } else {
            $url = "https://skinport.com/api/browse/{$categoryInfo['appid']}?cat={$categoryInfo['category']}&skip=$skip";
        }
        echo "  Запрос: $url\n";
        
        $response = fetchWithRetry($url, $currentCookie);
        
        if ($response === false) {
            echo "  ❌ Критическая ошибка при запросе. Остановка.\\n";
            // Закрываем текущий файл категории
            fwrite($fileHandle, "\\n]");
            fclose($fileHandle);
            exit(1);
        }
        
        if ($response) {
            $data = json_decode($response, true);
            
            if ($data && isset($data['items']) && count($data['items']) > 0) {
                $items = $data['items'];
                $remainingNeeded = $categoryInfo['items_needed'] - $collectedItems;
                
                // Берем только нужное количество товаров
                $itemsToProcess = array_slice($items, 0, $remainingNeeded);
                
                echo "  ✓ Получено: " . count($items) . " товаров, обрабатываем: " . count($itemsToProcess) . "\n";
                
                // Обрабатываем каждый товар
                foreach ($itemsToProcess as $index => $item) {
                    echo "    Товар " . ($collectedItems + $index + 1) . "/{$categoryInfo['items_needed']}: " . ($item['name'] ?? 'Unknown') . "\n";
                    
                    // Получаем описание
                    $description = '';
                    if (!empty($item['url'])) {
                        $description = getItemDescription(
                            $item['appid'] ?? 730,
                            $item['url'],
                            $item['version'] ?? '',
                            $currentCookie
                        );
                        sleep(rand(5, 8)); // Задержка между запросами за описанием 5-8 сек
                    }
                    
                    // Формируем данные товара
                    $itemData = [
                        'market_hash_name' => $item['marketHashName'] ?? '',
                        'currency' => $item['currency'] ?? '',
                        'image_original_url' => !empty($item['image']) ? 'https://community.cloudflare.steamstatic.com/economy/image/' . $item['image'] : '',
                        'price' => ($item['salePrice'] ?? 0) / 100,
                        'source_url' => !empty($item['url']) ? 'https://skinport.com/ru/item/' . $item['url'] : '',
                        'category' => $item['category_localized'] ?? $item['category'] ?? '',
                        'name' => $item['family_localized'] ?? $item['name'] ?? '',
                        'text' => $item['text'] ?? '',
                        'description' => $description,
                        'crumbs' => [$item['category_localized'] ?? $item['category'] ?? ''],
                        'tags' => array_filter([
                            $item['exterior_localized'] ?? $item['exterior'] ?? '',
                            $item['category_localized'] ?? $item['category'] ?? '',
                            $item['rarity_localized'] ?? $item['rarity'] ?? '',
                            $item['type_localized'] ?? $item['type'] ?? ''
                        ]),
                        'id' => hash('sha256', json_encode($item))
                    ];
                    
                    // Записываем товар в файл
                    if (!$isFirstItem) {
                        fwrite($fileHandle, ",\n");
                    }
                    fwrite($fileHandle, json_encode($itemData, JSON_UNESCAPED_UNICODE));
                    $isFirstItem = false;
                    $totalProcessed++;
                }
                
                $collectedItems += count($itemsToProcess);
                
                // Сохраняем прогресс после каждой страницы
                $progress['current_category'] = $categoryIndex;
                $progress['total_collected'] = $totalProcessed;
                $progress['categories_progress'][$categoryIndex] = [
                    'collected' => $collectedItems,
                    'skip' => $skip + 1
                ];
                saveProgress($progressFile, $progress);
                
                // Если собрали достаточно товаров - переходим к следующей категории
                if ($collectedItems >= $categoryInfo['items_needed']) {
                    break;
                }
                
                // Если получили меньше 50 товаров - больше нет
                if (count($items) < 50) {
                    echo "  ⚠️ Достигнут конец категории\n";
                    break;
                }
                
                $skip += 1;
                // Задержка не нужна - описания товаров уже дают достаточную паузу
            } else {
                echo "  ⚠️ Нет товаров в ответе\n";
                // Показываем первые 200 символов ответа для диагностики
                if ($response) {
                    echo "  📄 Начало ответа: " . substr($response, 0, 200) . "...\n";
                } else {
                    echo "  📄 Ответ пустой\n";
                }
                break;
            }
        } else {
            echo "  ❌ Ошибка curl\n";
            break;
        }
    }
    
    // Закрываем файл категории
    fwrite($fileHandle, "\n]");
    fclose($fileHandle);
    
    echo "✅ Категория завершена: собрано $collectedItems товаров\n";
    echo "💾 Сохранено в $categoryFile\n\n";
}

// Удаляем файл прогресса при успешном завершении
if (file_exists($progressFile)) {
    unlink($progressFile);
    echo "✓ Файл прогресса удален\n";
}

echo "🎉 Сбор завершен! Всего обработано товаров: $totalProcessed\n";
echo "💾 Данные сохранены в отдельные файлы по категориям\n";
echo "🚀 Теперь можно запустить импорт для каждого файла\n";