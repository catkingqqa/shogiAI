import os
#更名用
#把game1.csa ==> game00001.csa
FOLDER = "data"

files = [
    f for f in os.listdir(FOLDER)
    if f.endswith(".csa")
]

files.sort()

for idx, old_name in enumerate(files, start=1):

    old_path = os.path.join(FOLDER, old_name)
   
    new_name = f"game{idx:05d}.csa" #改名
    
    new_path = os.path.join(FOLDER, new_name)

    os.rename(old_path, new_path)

    print(f"{old_name} -> {new_name}")

print("完成")