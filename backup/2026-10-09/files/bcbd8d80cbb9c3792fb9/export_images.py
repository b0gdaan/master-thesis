"""
Конвертация SVG → PNG через браузер (Playwright или cairosvg).
Пробуем cairosvg, если не установлен — даём инструкцию.
"""
import subprocess, sys, os

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

# Попробуем cairosvg
try:
    import cairosvg
except ImportError:
    print("Устанавливаю cairosvg...")
    try:
        install("cairosvg")
        import cairosvg
    except Exception:
        cairosvg = None

if cairosvg:
    print("✅ cairosvg найден, конвертирую...")

    # LinkedIn banner: 1584 × 396 px
    cairosvg.svg2png(
        url=r"D:\clode9\linkedin_banner.svg",
        write_to=r"D:\clode9\linkedin_banner.png",
        output_width=1584,
        output_height=396,
    )
    print("✅ linkedin_banner.png сохранён (1584×396)")

    # GitHub avatar: 500 × 500 px
    cairosvg.svg2png(
        url=r"D:\clode9\github_avatar.svg",
        write_to=r"D:\clode9\github_avatar.png",
        output_width=500,
        output_height=500,
    )
    print("✅ github_avatar.png сохранён (500×500)")

    print("\nФайлы готовы:")
    print("  D:\\clode9\\linkedin_banner.png  ← загрузи как фон LinkedIn")
    print("  D:\\clode9\\github_avatar.png    ← загрузи как аватар GitHub")

else:
    print("\n⚠️  cairosvg не установился (требует библиотеку Cairo).")
    print("\nАльтернатива — открой SVG в Chrome и сохрани как PNG:")
    print()
    print("LinkedIn banner:")
    print("  1. Открой: D:\\clode9\\linkedin_banner.svg в Chrome")
    print("  2. Нажми Ctrl+Shift+I → Console → введи:")
    print('     let a=document.querySelector("svg");')
    print("     a.style.display='block'")
    print("  3. Или просто правый клик на странице → 'Сохранить как' .html,")
    print("     потом используй расширение SVG-Export или online-конвертер:")
    print("     https://svgtopng.com/")
    print()
    print("GitHub avatar:")
    print("  Аналогично: D:\\clode9\\github_avatar.svg → svgtopng.com")
    print()
    print("Нужный размер:")
    print("  linkedin_banner.png : 1584 × 396 пикселей")
    print("  github_avatar.png   : 500 × 500 пикселей")
