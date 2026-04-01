# chebubrya-memes-bot

<!-- настраиваем окружение -->
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

<!-- датасет -->
python scripts\inspect_dataset.py --dataset DATASET_PATH

<!-- индексация -->
$env:PYTHONPATH = "C:\Users\Lenovo\Desktop\chebubrya-memes-bot\src"
python scripts\index_memes.py `
  --dataset "c:\Users\Lenovo\Desktop\dataset\train\images\memes.csv.xlsx" `
  --image-column "meme_path" `
  --text-columns "text_on_image"

<!-- тест -->
  python scripts\query_memes.py --query "ПРИМЕР СООБЩЕНИЯ"