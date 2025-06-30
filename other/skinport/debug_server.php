<?php
/**
 * Отладка проблемы с сервером
 */

echo "🔍 Диагностика сервера\n";
echo "=====================\n\n";

// Проверяем файлы
echo "1️⃣ Проверка файлов:\n";
$files = ['categories.json', 'cookies.json'];
foreach ($files as $file) {
    if (file_exists($file)) {
        echo "✅ $file существует\n";
    } else {
        echo "❌ $file НЕ НАЙДЕН!\n";
    }
}

// Проверяем categories.json
echo "\n2️⃣ Содержимое categories.json:\n";
if (file_exists('categories.json')) {
    $categories = json_decode(file_get_contents('categories.json'), true);
    if ($categories) {
        echo "✅ JSON валиден, категорий: " . count($categories) . "\n";
        foreach ($categories as $cat) {
            echo "  - {$cat['name']} (вес: {$cat['weight']})\n";
        }
    } else {
        echo "❌ Ошибка парсинга JSON!\n";
    }
} else {
    echo "❌ Файл не найден!\n";
}

// Проверяем cookies.json
echo "\n3️⃣ Проверка куки:\n";
if (file_exists('cookies.json')) {
    $cookiesData = json_decode(file_get_contents('cookies.json'), true);
    if ($cookiesData) {
        $validCookies = array_filter($cookiesData, function($cookie) {
            return !empty($cookie['cookies']);
        });
        echo "✅ Куки файл валиден\n";
        echo "Всего наборов: " . count($cookiesData) . "\n";
        echo "Заполненных: " . count($validCookies) . "\n";
        
        if (!empty($validCookies)) {
            $testCookie = array_values($validCookies)[0];
            echo "Тестируем куки: {$testCookie['name']}\n";
            
            // Тестовый запрос
            echo "\n4️⃣ Тестовый запрос:\n";
            $url = "https://skinport.com/api/browse/730?cat=Knife";
            $command = "curl '$url' " .
                "-H 'accept: */*' " .
                "-H 'cookie: {$testCookie['cookies']}' " .
                "-H 'user-agent: {$testCookie['user_agent']}' " .
                "--compressed -s";
            
            $response = shell_exec($command);
            if ($response) {
                $data = json_decode($response, true);
                if ($data && isset($data['items'])) {
                    echo "✅ API работает! Получено " . count($data['items']) . " товаров\n";
                } else {
                    echo "❌ API ошибка: " . substr($response, 0, 200) . "\n";
                }
            } else {
                echo "❌ Пустой ответ от API\n";
            }
        } else {
            echo "❌ Нет заполненных куки!\n";
        }
    } else {
        echo "❌ Ошибка парсинга cookies.json!\n";
    }
} else {
    echo "❌ cookies.json не найден!\n";
}

echo "\n🎯 Рекомендации:\n";
echo "1. Убедитесь что cookies.json скопирован с рабочего сервера\n";
echo "2. Проверьте что куки свежие (не старше 1-2 часов)\n";
echo "3. Убедитесь что IP сервера не заблокирован\n";
?>