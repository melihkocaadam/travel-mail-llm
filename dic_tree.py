import os

def get_folder_size(path):
    """Verilen klasörün toplam boyutunu (bayt olarak) döndürür."""
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
            except Exception:
                pass  # erişilemeyen dosyalar varsa atla
    return total

def format_size(size_bytes):
    """Boyutu okunabilir formata çevirir."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def print_folder_sizes(base_path):
    print(f"\n📁 Klasördeki Alt Klasörlerin Boyutları:\n{base_path}\n")
    
    folders = [f.path for f in os.scandir(base_path) if f.is_dir()]

    for folder in folders:
        size = get_folder_size(folder)
        print(f"{folder} => {format_size(size)}")

    print("\n✓ İşlem tamamlandı.\n")

# ----------------------------------------------------------------
# Kullanım:
# ----------------------------------------------------------------
# base_path = "C:/python_scripts/travel-mail-llm"  # kendi klasörünüz
print_folder_sizes(os.getcwd())  # mevcut çalışma dizinini kullanır
