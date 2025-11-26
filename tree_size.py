import os

def get_size(path):
    """Verilen klasörün veya dosyanın toplam boyutunu (bayt olarak) döndürür."""
    total = 0

    if os.path.isfile(path):
        return os.path.getsize(path)

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

def print_sizes(base_path):
    print(f"\n📁 Klasördeki Alt Klasörlerin Boyutları:\n{base_path}\n")

    max_length = max(len(f.path) for f in os.scandir(base_path)) + 4    
    path_list = [f.path for f in os.scandir(base_path)]

    size_list = []
    for path in path_list:
        size_list.append((path, get_size(path)))

    sorted_size_list = sorted(size_list, key=lambda x: x[1], reverse=True)
    for path, size in sorted_size_list:
        print(f"{path} {'.' * (max_length - len(path))} {format_size(size)}")
    
    print("\n✓ İşlem tamamlandı.\n")

if __name__ == "__main__":
    args = os.sys.argv
    base_path = os.getcwd()  # Varsayılan olarak geçerli dizin
    if len(args) != 2:
        print("Kullanım: python dic_tree.py <klasör_yolu>")
        print(f"Varsayılan olarak geçerli dizin kullanılıyor: {base_path}")
    else:
        base_path = os.path.abspath(args[1])
        if not os.path.isdir(base_path):
            print(f"Hata: '{base_path}' geçerli bir klasör değil.")
            os.sys.exit(1)

    print_sizes(base_path)