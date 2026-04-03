# chebubrya-memes-bot

python src\scripts\evaluate_retrieval.py --dataset "C:\Users\Lenovo\Desktop\dataset\val_check_1.xlsx" --query-columns "user_messages" --top-k 1 3 5 
Evaluated queries: 270
Recall@1: 0.3148 (85/270)
Recall@3: 0.5074 (137/270)
Recall@5: 0.6000 (162/270)
MRR: 0.4182


python src\scripts\evaluate_retrieval_rerank.py --dataset "C:\Users\Lenovo\Desktop\dataset\val_check_1.xlsx" --query-columns "user_messages" --retrieve-k 5 --top-k 1 3 5 --show-failures 20
Evaluated queries: 270
Recall@1: 0.4407 (119/270)
Recall@3: 0.5741 (155/270)
Recall@5: 0.6000 (162/270)
MRR: 0.5053