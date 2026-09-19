import os
import httpx
import json

# --- CONFIG ---
CATEGORIES = ["pets", "eggs", "petwear", "strollers", "food", "vehicles", "toys", "gifts", "stickers"]
TOKEN = "" # Your Token
KEYS_TO_DELETE = {"id", "lastUpdatedAt", "origin"}

# --- HYBRID EXTRACTOR ---
def find_all_items(data):
    """Рекурсивно ищет все объекты предметов на любом уровне вложенности RSC ответа."""
    items = []
    if isinstance(data, dict):
        if "name" in data and ("regularValue" in data or "value" in data or "id" in data):
            items.append(data)
        else:
            for val in data.values():
                items.extend(find_all_items(val))
    elif isinstance(data, list):
        for item in data:
            items.extend(find_all_items(item))
    return items

# --- PIPELINE ---
def main():
    save_path = "amvgg_local_test.json"
    
    final_data = {cat: [] for cat in CATEGORIES}
    
    url = f"https://amvgg.com/trades?_rsc={TOKEN}"

    with httpx.Client(timeout=15.0) as client:
        try:
            print(f"[*] Скачиваем единую базу данных...")
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            
            all_raw_items = []

            # RSC
            for line in resp.text.splitlines():
                if '{"id":"' in line and '"name":"' in line:
                    try:
                        json_str = line.split(':', 1)[1] if ':' in line else line
                        parsed_chunk = json.loads(json_str)
                        
                        extracted = find_all_items(parsed_chunk)
                        all_raw_items.extend(extracted)
                    except json.JSONDecodeError:
                        continue

            if not all_raw_items:
                print("[-] Не удалось найти предметы. Возможно, токен устарел.")
                return
            
            print(f"[+] Найдено {len(all_raw_items)} сырых предметов. Начинаем распределение...")

            processed_names = set()
            
            for item in all_raw_items:
                name = item.get("name")
                if not name or name in processed_names:
                    continue
                    
                cat = str(item.get("category", "")).lower()
                
                if cat + "s" in CATEGORIES:
                    cat += "s"
                elif "pet" in cat:
                    cat = "pets"
                    
                if cat not in CATEGORIES:
                    cat = "pets" 

                cleaned_item = {}
                for k, v in item.items():
                    if k in KEYS_TO_DELETE:
                        continue
                    if isinstance(v, str):
                        try:
                            cleaned_item[k] = float(v) if '.' in v else int(v)
                        except ValueError:
                            cleaned_item[k] = v
                    else:
                        cleaned_item[k] = v

                final_data[cat].append(cleaned_item)
                processed_names.add(name)

            for cat in list(final_data.keys()):
                if not final_data[cat]:
                    del final_data[cat] 
                    continue
                    
                sort_key = "regularValue" if cat == "pets" else "value"
                def get_val(x):
                    val = x.get(sort_key, 0)
                    return float(val) if val is not None else 0.0
                
                final_data[cat].sort(key=get_val, reverse=True)
                print(f"[+] {cat.upper()}: обработано {len(final_data[cat])} шт.")

        except Exception as e:
            print(f"[-] Критическая ошибка: {e}")
            return

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n[+] Готово! База сохранена локально: {save_path}")

if __name__ == "__main__":
    main()
