"""把 ArtSource/Props/*.png 导入到 /Game/Props（UE Python，在编辑器里跑）。"""
import unreal
SRC = "ArtSource/Props"          # 相对工程根
DEST = "/Game/Props"
# 文件名即资产名：Prop_WoodenChair.png -> /Game/Props/Prop_WoodenChair
