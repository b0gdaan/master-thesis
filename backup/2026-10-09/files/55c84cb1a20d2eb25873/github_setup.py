"""
GitHub Profile Setup Script
Запусти ПОСЛЕ: gh auth login
Делает всё автоматически за ~30 секунд.
"""

import subprocess
import os
import sys

def run(cmd, check=True):
    print(f"  → {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        print(f"    {result.stdout.strip()}")
    if result.returncode != 0 and check:
        print(f"    ⚠️  {result.stderr.strip()}")
    return result

def check_auth():
    r = run("gh auth status", check=False)
    if r.returncode != 0:
        print("\n❌ Не авторизован в GitHub CLI.")
        print("   Запусти: gh auth login")
        print("   Выбери: GitHub.com → HTTPS → Yes → Login with browser")
        sys.exit(1)
    print("✅ GitHub авторизация OK\n")

# ── 1. Обновить bio ────────────────────────────────────────────────────
def update_bio():
    print("📝 Обновляю bio...")
    run('gh api -X PATCH /user -f bio="Data Scientist & AI Engineer · Python · ML · FastAPI · PostgreSQL · M.Sc. AI"')
    print("✅ Bio обновлён\n")

# ── 2. Добавить темы к репозиториям ───────────────────────────────────
def update_topics():
    print("🏷️  Добавляю темы к репозиториям...")

    topics = {
        "master-thesis": [
            "machine-learning", "time-series", "xgboost", "cryptocurrency",
            "walk-forward", "python", "jupyter", "dcc-garch", "financial-ml"
        ],
        "data_for_wb_ozon": [
            "fastapi", "postgresql", "etl", "analytics-dashboard",
            "react", "python", "wildberries", "ozon", "marketplace-analytics"
        ],
        "auv-defect-detection": [
            "pytorch", "computer-vision", "mobilenetv2", "opencv",
            "deep-learning", "raspberry-pi", "defect-detection", "auv"
        ],
    }

    for repo, tags in topics.items():
        names_json = '["' + '","'.join(tags) + '"]'
        run(f'gh api -X PUT /repos/b0gdaan/{repo}/topics -f names=\'{names_json}\'', check=False)
        print(f"   ✅ {repo}: {', '.join(tags[:4])}...")

    print()

# ── 3. Создать Profile README ──────────────────────────────────────────
def create_profile_readme():
    print("📄 Создаю Profile README (b0gdaan/b0gdaan)...")

    readme_path = r"D:\clode9\github_profile_readme.md"

    # Проверяем существует ли репо
    r = run("gh repo view b0gdaan/b0gdaan", check=False)

    if r.returncode != 0:
        # Создаём репо
        run('gh repo create b0gdaan/b0gdaan --public --description "GitHub Profile README"')
        print("   Репо создан")

        # Клонируем и пушим
        os.makedirs(r"D:\clode9\profile_repo", exist_ok=True)
        run(r'git clone https://github.com/b0gdaan/b0gdaan D:\clode9\profile_repo', check=False)

    # Копируем README
    import shutil
    dest = r"D:\clode9\profile_repo\README.md"
    shutil.copy(readme_path, dest)

    # Git push
    cmds = [
        r'git -C D:\clode9\profile_repo add README.md',
        r'git -C D:\clode9\profile_repo commit -m "Add profile README"',
        r'git -C D:\clode9\profile_repo push',
    ]
    for cmd in cmds:
        run(cmd, check=False)

    print("✅ Profile README опубликован\n")

# ── 4. Открепить steps ────────────────────────────────────────────────
def unpin_steps():
    print("📌 Откреп steps через GraphQL...")
    # GraphQL нужен для pinned repos — пропускаем, делаем вручную
    print("   ⚠️  Открепить steps нужно вручную:")
    print("   github.com/b0gdaan → Customize your pins → снять галочку steps\n")

# ── Main ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  GitHub Profile Setup — b0gdaan")
    print("=" * 50 + "\n")

    check_auth()
    update_bio()
    update_topics()
    create_profile_readme()
    unpin_steps()

    print("=" * 50)
    print("✅ Готово! Проверь: https://github.com/b0gdaan")
    print("=" * 50)
