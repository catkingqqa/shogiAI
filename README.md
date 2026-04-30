shogiAI 小筆記

這個專案把 CSA 將棋棋譜整理成之後可以拿去訓練模型的資料。

流程大概是：

CSA 棋譜 -> 用 cshogi 檢查能不能合法重播 -> 每一步切成一筆樣本 -> 存成 .npz

另外也有準備 Jupyter Notebook，可以直接把棋盤顯示出來，不用只看一堆數字。


先安裝

進到專案資料夾：

cd C:\Users\20050\OneDrive\桌面\code\shogiAI

裝需要的套件：

python -m pip install -r requirements.txt

主要會用到 cshogi、numpy、jupyter、ipython。


CSA 放哪裡

把棋譜放在 data 裡就好。

例如現在是：

data\game1.csa

如果之後有更多棋譜，也可以像這樣放：

data\game1.csa
data\game2.csa
data\game3.csa


把 CSA 轉成訓練資料

轉一個檔案：

python src\csa_preprocess.py --input data\game1.csa --output out\game1.npz --encoding utf-8 --keep-invalid-report out\game1_invalid.jsonl

這行的意思是：

讀 data\game1.csa。
用 cshogi 檢查每一步是否合法。
每一步下棋前都存成一筆訓練樣本。
最後輸出到 out\game1.npz。
如果有壞掉或不能重播的棋譜，原因會寫到 out\game1_invalid.jsonl。

如果一次要轉整個 data 資料夾：

python src\csa_preprocess.py --input data --output out\samples.npz --recursive --encoding utf-8 --keep-invalid-report out\invalid.jsonl

注意如果你的 game1.csa 是 UTF-8，所以記得加 --encoding utf-8。

成功時大概會看到：

parsed_games: 1
legal_games: 1
invalid_games: 0
samples: 119
output: out\game1.npz

可以這樣看：

parsed_games 是讀到幾局棋。
legal_games 是幾局可以完整合法重播。
invalid_games 是幾局有問題。
samples 是產生幾筆樣本，通常就是手數。
output 是輸出的檔案。

所以 samples: 119 就是這局棋產生了 119 筆訓練資料。


.npz 裡面是什麼

.npz 是 NumPy 的資料檔。它不是拿來直接用 Excel 開的，比較像是給 Python 或模型訓練程式讀的。

裡面有這幾個東西：

states
moves
values
meta
move_label_count


states

states 是棋盤狀態。

形狀是 (N, 43, 9, 9)。

N 是有幾筆樣本。
43 是每個局面用 43 張特徵平面表示。
9 x 9 是將棋盤。

可以想成：每一步下棋前，程式都把棋盤拍成一張模型看得懂的多層圖片。

43 層大概分成自己的盤上棋子、對手的盤上棋子、自己的持駒、對手的持駒、現在輪到誰。

預設會把後手的局面轉過來，所以模型永遠用現在要下的人角度看棋盤。


moves

moves 是下一手。

模型不能直接吃 7g7f 這種文字，所以程式會把每一步轉成一個數字 label。

例如 moves[0] 是某個整數，這個整數就代表那個局面下實戰下出的那一步。


values

values 是勝負結果，但不是單純先手贏或後手贏。

它是從現在輪到下棋的人角度看：

1.0 代表現在這個人最後贏了。
-1.0 代表現在這個人最後輸了。
0.0 代表和棋。

這樣訓練 value head 時會比較直覺。


meta

meta 是給人看的補充資訊。

裡面會記來源是哪個 CSA、第幾手、下棋前的 SFEN、下一手的 USI 表示。

除錯、看資料有沒有切對時很有用。


move_label_count

move_label_count 是 move label 的總數。

目前是 13689。

如果之後做 policy head，輸出大小就可以用這個數字。


想看 .npz 內容

可以用 Python 簡單印一下：

import json
import numpy as np

data = np.load("out/game1.npz")

print(data.files)
print(data["states"].shape)
print(data["moves"][:10])
print(data["values"][:10])
print(json.loads(str(data["meta"][0])))


用 Jupyter 看棋盤

先開 Jupyter：

jupyter notebook

然後打開：

notebooks\cshogi_jupyter_viewer.ipynb

cshogi 本來就支援在 Notebook 裡直接顯示棋盤，所以這樣就會看到棋盤：

import cshogi

board = cshogi.Board()
board

如果要看 CSA 的某一步：

from src.notebook_viewer import csa_boards, show

csa = csa_boards("data/game1.csa", encoding="utf-8")
show(csa[0])

如果要看轉好的 .npz 樣本：

from src.notebook_viewer import npz_samples, show, show_many

samples = npz_samples("out/game1.npz")
show(samples[0])
show_many(samples, limit=5)

show() 會把棋盤畫出來，也會順便顯示第幾手、下一手、move label、value、來源檔案和 SFEN。


目前最常用的兩行

轉資料：

python src\csa_preprocess.py --input data\game1.csa --output out\game1.npz --encoding utf-8 --keep-invalid-report out\game1_invalid.jsonl

開 Notebook 看棋盤：

jupyter notebook
