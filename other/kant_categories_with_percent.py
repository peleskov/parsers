import json

# Читаем файл с данными категорий
with open('kant_categories_count_20250707_125251.json', 'r', encoding='utf-8') as f:
    categories = json.load(f)

# Считаем общее количество товаров
total_items = sum(category['total_items'] for category in categories)

# Добавляем процент для каждой категории
for category in categories:
    percent = (category['total_items'] / total_items) * 100
    category['percent'] = round(percent, 2)

# Добавляем общую информацию
result = {
    'total_items': total_items,
    'total_categories': len(categories),
    'categories': categories
}

# Сохраняем обновленный файл
with open('kant_categories_count_with_percent.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# Выводим результат
print(f"Общее количество товаров: {total_items}")
print(f"Количество категорий: {len(categories)}")
print("\nПроцент по категориям:")
print("-" * 50)

for category in sorted(categories, key=lambda x: x['total_items'], reverse=True):
    print(f"{category['name']}: {category['total_items']} товаров ({category['percent']}%)")

print("-" * 50)
print(f"ИТОГО: {total_items} товаров (100%)")